# Detailed Step-by-Step Plan

## Phase 0 — Environment & Hardware Setup

### 0.1 ESP32 Dev Environment
- Install Arduino IDE (or PlatformIO in VS Code)
- Add ESP32 board URL to Arduino IDE:
  `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
- Install ESP32 boards via Boards Manager
- Select board: `ESP32 Dev Module`
- Test: upload Blink example

### 0.2 Python Environment (PC side) — Conda

Conda lives at `~/miniconda3` (binary: `~/miniconda3/bin/conda`). Initialize once if not already:

```bash
~/miniconda3/bin/conda init bash
exec $SHELL
```

Create a dedicated env from a file (keeps it reproducible and easy to recreate):

`environment.yml`:
```yaml
name: ssi
channels:
  - conda-forge
dependencies:
  - python=3.11
  - numpy
  - scipy
  - scikit-learn
  - pandas
  - pyserial
  - matplotlib
  - jupyter
  - pip
  - pip:
      - pyqtgraph   # faster live plotting than matplotlib, optional
```

Create and activate:

```bash
cd "~/Documents/Projects/Silent Speach Interface"
conda env create -f environment.yml
conda activate ssi
python -c "import numpy, scipy, sklearn, serial, matplotlib; print('OK')"
```

Daily workflow:
```bash
conda activate ssi
# ... run scripts ...
conda deactivate
```

Later: if you add new packages, regenerate the lockfile:
```bash
conda env export > environment.yml
```

Notes:
- Use `conda install` for packages that exist on conda-forge (numpy, scipy, scikit-learn, etc.) — they're pre-compiled and faster.
- Use `pip` only inside the env for things conda doesn't have (e.g. `pyqtgraph`).
- For ESP32 serial later, `pyserial` is enough; you don't need any extra USB driver on Linux if the ESP shows up as `/dev/ttyUSB0`.

### 0.3 Wiring — ADS1293 to ESP32
Connect between ADS1293 (or ADS1293 evaluation board) and ESP32:

| ADS1293 Pin | ESP32 Pin |
|-------------|-----------|
| SCLK        | GPIO 18   |
| DIN (MOSI)  | GPIO 23   |
| DOUT (MISO) | GPIO 19   |
| CS          | GPIO 5    |
| DRDY        | GPIO 4    |
| VCC (3.3V)  | 3.3V      |
| GND         | GND       |

Note: ADS1293 runs on 3.3V logic — safe for ESP32.

For ECG (Lead I, 3 electrodes):
- IN1 (positive) → left side of chest, just below the collarbone
- IN2 (negative) → right side of chest, just below the collarbone
- IN3 / RLD (right leg drive) → lower-left ribcage or left hip (driven reference for common-mode rejection — strongly recommended for ECG to cancel 50/60 Hz mains pickup)
- Reference: use the RLD electrode above; alternatively place on bony area (clavicle) if RLD not connected

ECG signal: ~0.5–5 mV amplitude, dominant QRS complex (R-peak) at ~1 mV, T-wave at ~0.3 mV. Main frequency content 0.5–40 Hz; the QRS spike has energy up to ~50 Hz.

> Note: ADS1293 supports ECG natively (it was designed for it). For silent speech later, you will move the same three electrodes to the face and re-purpose channels for EMG.

### 0.4 Verify SPI Communication
Write a minimal Arduino sketch that:
- Initializes SPI at ~4 MHz (mode 0 or 1 — check ADS1293 datasheet)
- Sets CS high
- Reads ADS1293 register `0x00` (device ID) — expected value per datasheet
- Prints register value to Serial Monitor

Success criteria: you see the correct device ID (0x90 per datasheet).

---

## Phase 1 — Raw EMG Streaming

### 1.1 Configure ADS1293 Registers
Write firmware to configure:
- **Sampling rate**: set to 500 SPS (sufficient for ECG — Nyquist is ~250 Hz, but QRS is well under 50 Hz; 500 SPS leaves headroom for filtering and is easy on bandwidth)
- **Gain**: set to 6 or 12 (ECG R-peak is ~1 mV, gain ×6 → 6 mV full-scale at the ADC; gain ×12 if you want more resolution on smaller features)
- **Channel mapping**: IN1–IN2 differential → CH1 (Lead I); IN3 unused or used as a second lead
- **Lead-off detection**: ON (DC lead-off current on each input) — alerts if an electrode falls off
- **RLD (right leg drive)**: ENABLED — drives the body to reduce common-mode 50/60 Hz noise. Strongly recommended for ECG.
- **Continuous conversion mode**: start continuous data output
- **Data ready interrupt**: configure DRDY pin to pulse when new data is available

Reference registers to configure (consult datasheet for exact addresses):
- CONFIG (0x01): sample rate
- CHn_CN (channel n control): gain, PD, channel on/off
- RLD_CN (0x0C): RLD amplifier settings
- WILSON (0x0E): reference configuration
- LOFF (0x04): lead-off control
- START (0x05): start conversions

### 1.2 Read Data from ADS1293
In the ESP32 loop:
- Wait for DRDY pin to go LOW (new data ready)
- Set CS LOW
- Read 9 bytes (3 channels × 24 bits = 72 bits = 9 bytes)
  - SPI.transfer(0x00) for each byte (ADS1293 outputs data on MISO when clocked)
- Set CS HIGH
- Convert 3-byte signed 24-bit values to int32 (sign-extend if bit 23 is set)
- Store in a struct {int32_t ch1, ch2, ch3; uint32_t timestamp;}

### 1.3 Stream to PC over WiFi/UDP
- Connect ESP32 to WiFi station mode
- Create UDP socket, send packets to PC IP (port 5000)
- Packet format (binary, packed struct):
  ```
  [0xAA 0xBB]  [timestamp: 4 bytes]  [ch1: 3 bytes]  [ch2: 3 bytes]  [ch3: 3 bytes]  [checksum: 1 byte]
  ```
  Total: 16 bytes per packet
- Send at each data ready interrupt (500 Hz → 500 packets/sec → ~8 KB/s — trivial for WiFi)

### 1.4 PC Receiver
Write `pc/receiver.py`:
```python
import socket, struct, time, csv, threading
import numpy as np

UDP_IP = "0.0.0.0"
UDP_PORT = 5000
CHUNK_SIZE = 16

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

buffer = []  # list of (timestamp, ch1, ch2, ch3)
running = True

def parse_packet(data):
    if data[0] != 0xAA or data[1] != 0xBB:
        return None
    ts = struct.unpack('>I', data[2:6])[0]
    ch1 = int.from_bytes(data[6:9], 'big', signed=True)
    ch2 = int.from_bytes(data[9:12], 'big', signed=True)
    ch3 = int.from_bytes(data[12:15], 'big', signed=True)
    return (ts, ch1, ch2, ch3)

def save_csv():
    with open(f"data/raw/session_{int(time.time())}.csv", "w") as f:
        f.write("timestamp,ch1,ch2,ch3\n")
        for row in buffer:
            f.write(f"{row[0]},{row[1]},{row[2]},{row[3]}\n")

# Main loop
start = time.time()
while running:
    data, addr = sock.recvfrom(CHUNK_SIZE)
    packet = parse_packet(data)
    if packet:
        buffer.append(packet)
    # Save every 10 seconds
    if time.time() - start > 10:
        save_csv()
        start = time.time()
```

### 1.5 Visualize Raw ECG
Build a simple real-time scroll plot in `pc/visualize.py`:
- Read latest samples from buffer
- Plot the active channel (CH1)
- 5-second rolling window, update every 50 ms
- Use matplotlib `FuncAnimation` or just redraw

You should see a clean P-QRS-T waveform repeating ~60–100 times per minute. If you see only 50 Hz sine, the electrodes are not making good contact or RLD is misconfigured.

### 1.6 Validate Signal Quality
- Place electrodes as in §0.3 (left chest, right chest, lower-left rib)
- Sit still, breathe normally
- You should see clear QRS spikes roughly once per second
- Cross-check by feeling your pulse on the wrist — spikes should line up with pulse beats
- If signal is noisy / no QRS visible:
  - Add 50 Hz notch filter in PC (very common ECG noise source)
  - Check electrode contact (use gel, shave chest hair, wait 30 s for gel to stabilize)
  - Verify RLD connection — most ECG problems come from missing RLD
  - Try switching the IN1/IN2 leads (the R-peak polarity is reversed)
  - Lower the gain if signal clips, raise it if QRS is small

---

## Phase 2 — Heart Beat Detection (R-peak + BPM)

Goal: detect each QRS complex in real time and compute beats-per-minute. This validates the full pipeline (electrodes → ADC → ESP32 → PC → algorithm) end-to-end.

**Why this is a good first test:** ECG has a very clean, well-defined morphology (P-QRS-T). The R-peak is sharp, periodic, and easy to find with classic DSP. Success or failure is visually obvious and easy to cross-check against your wrist pulse. Much simpler than EMG classification, but exercises every part of the stack.

### 2.1 Preprocessing Pipeline
Write `pc/preprocess_ecg.py`:

**Filtering (in this order):**
1. **Bandpass 0.5–40 Hz**, 4th-order Butterworth, applied forward-backward (`filtfilt`) for zero phase
   - Removes baseline wander (breathing, movement) and high-frequency noise
2. **50 Hz notch** (or 60 Hz if you're in the US) — IIR, quality factor Q = 30
3. (Optional) **Derivative + square + moving-average** — Pan-Tompkins style, see §2.3

```python
from scipy.signal import butter, filtfilt, iirnotch

def preprocess_ecg(x, fs=500):
    # Bandpass 0.5–40 Hz
    b, a = butter(4, [0.5, 40], btype='band', fs=fs)
    x = filtfilt(b, a, x)
    # Notch 50 Hz
    b, a = iirnotch(50, Q=30, fs=fs)
    x = filtfilt(b, a, x)
    return x
```

### 2.2 Offline R-Peak Detection (scipy / NeuroKit2)
The fastest path to a working R-peak detector: use a library. Then later we can write our own.

**Option A — scipy (DIY):**
```python
import numpy as np
from scipy.signal import find_peaks

def detect_r_peaks(ecg, fs=500, min_bpm=40, max_bpm=200):
    # find_peaks wants a 1D array of peak heights
    # R-peaks are local maxima; minimum distance between beats:
    min_dist = int(60 / max_bpm * fs)   # shortest plausible R-R
    peaks, props = find_peaks(ecg, distance=min_dist, height=np.std(ecg)*0.5)
    return peaks
```

**Option B — NeuroKit2 (recommended, more robust):**
```python
# pip install neurokit2
import neurokit2 as nk

ecg_clean = nk.ecg_clean(ecg, sampling_rate=500)
_, rpeaks = nk.ecg_peaks(ecg_clean, sampling_rate=500)
# rpeaks['ECG_R_Peaks'] is an array of sample indices
```

### 2.3 Pan-Tompkins (DIY, optional)
A classic real-time R-peak detector. Useful learning exercise; matches what real Holter monitors do.

Steps:
1. Bandpass 5–15 Hz (isolates QRS)
2. Differentiate (sharpens rising edge of R)
3. Square (makes everything positive, emphasizes large slopes)
4. Moving-average integrate (window ~150 ms)
5. Adaptive thresholding on the integrated signal + find_peaks
6. Refractory period: ignore peaks < 200 ms after the previous one

Reference: Pan & Tompkins, 1985. Code in `pc/pan_tompkins.py`.

### 2.4 Compute BPM
```python
def compute_bpm(r_peak_indices, fs=500):
    if len(r_peak_indices) < 2:
        return 0.0
    rr_intervals = np.diff(r_peak_indices) / fs   # seconds between beats
    bpm = 60.0 / np.mean(rr_intervals)
    return bpm
```

### 2.5 Validation
Run on 60 seconds of recorded ECG. Check:
- **R-peak count** ≈ 60–100 (depending on your heart rate)
- **BPM** matches what you'd get from a pulse oximeter or wrist pulse
- **R-R intervals** are stable when sitting still; vary when moving / breathing deeply
- Plot the detected peaks overlaid on the raw signal — they should sit on top of the QRS spikes

If detection is off:
- Tune `min_dist` (too short → duplicate R-peaks; too long → missed beats)
- Tune the `height` threshold in `find_peaks`
- Re-examine filtering — baseline wander can fool peak finders
- Check lead-off / electrode quality first

### 2.6 Real-Time BPM Display
Write `pc/realtime_bpm.py`:
- Stream in via UDP
- Maintain a rolling 10-second window of samples
- Run the detector on the window every 250 ms
- Print current BPM and last R-peak timestamp
- Optional: live plot of raw ECG with detected R-peaks marked

**Acceptance criteria:**
- BPM is within ±5 of wrist pulse
- Refresh rate ≥ 2 Hz
- Stable for at least 60 seconds with no false peak detections

### 2.7 Save Annotated Dataset
Save the raw ECG + detected R-peak indices to:
```
data/raw/ecg_session_1.csv     # raw, columns: timestamp, ch1
data/processed/ecg_session_1_rpeaks.json   # R-peak sample indices
```
This dataset is reused in Phase 3 for HRV analysis, and in Phase 4 to validate electrode placement is still good when you move leads to the face.

---

## Phase 3 — Heart Rate Variability (HRV) & Robustness

Builds on Phase 2. The same pipeline (electrodes → ADC → ESP → R-peaks) is now used to extract more sophisticated cardiac metrics.

### 3.1 Time-Domain HRV Features
From the R-R interval series:
- **Mean RR**, **SDNN** (std dev of RR) — overall HRV
- **RMSSD** (root mean square of successive differences) — parasympathetic activity
- **pNN50** (fraction of successive RR differences > 50 ms)
- **Min/Max HR**

```python
rr = np.diff(r_peak_indices) / fs   # seconds
sdnn = np.std(rr)
rmssd = np.sqrt(np.mean(np.diff(rr)**2))
pnn50 = np.mean(np.abs(np.diff(rr)) > 0.050)
```

### 3.2 Frequency-Domain HRV
- Interpolate RR series to uniform 4 Hz
- Compute PSD via Welch's method
- Power in bands:
  - **VLF**: 0.003–0.04 Hz
  - **LF**: 0.04–0.15 Hz (sympathetic + parasympathetic)
  - **HF**: 0.15–0.4 Hz (parasympathetic / breathing)
- Ratio LF/HF

```python
from scipy.interpolate import interp1d
from scipy.signal import welch

t_rr = np.cumsum(rr)
f_interp = interp1d(t_rr, rr, kind='cubic', fill_value='extrapolate')
t_uniform = np.arange(t_rr[0], t_rr[-1], 0.25)
rr_uniform = f_interp(t_uniform)
f, psd = welch(rr_uniform, fs=4, nperseg=256)
lf = np.trapz(psd[(f >= 0.04) & (f < 0.15)], f[(f >= 0.04) & (f < 0.15)])
hf = np.trapz(psd[(f >= 0.15) & (f < 0.4)],  f[(f >= 0.15) & (f < 0.4)])
```

### 3.3 Robustness Checks
- **Motion artifacts**: shake the cable / walk around — verify the detector either ignores them or flags low-confidence output
- **Electrode swap**: flip IN1 and IN2 — verify R-peak polarity flips and detector still works (or you can use abs() in preprocessing)
- **Long recording**: record 5+ minutes, check BPM trend and HRV are physiologically reasonable (HR ~50–100 at rest, SDNN ~50–150 ms for healthy adult)
- **Compare against ground truth**: take a few minutes of pulse-oximeter data alongside ECG; check BPM and SDNN match

### 3.4 (Optional) Beat Classification
If you want a step beyond BPM:
- Detect each QRS, segment a window around it (e.g. ±200 ms)
- Classify as normal beat / PVC / artifact
- Requires labeled data — easiest is to use the [MIT-BIH Arrhythmia Database](https://physionet.org/content/mitdb/) (48 half-hour recordings, 110k+ annotated beats) for training, then validate on your own recordings
- Models: Random Forest on morphological features, or 1D CNN on raw beats

---

## Phase 4 — Silent Speech: Electrode Placement & Data Collection

### 4.1 Electrode Positioning for Facial EMG
Reposition electrodes to capture subvocalization muscle activity:

| Channel | Muscle | Placement |
|---------|--------|-----------|
| CH1 (IN1–IN2) | Zygomaticus major | Cheek area, active during lip movement |
| CH2 (IN2–IN3) | Masseter | Jaw clench area |
| CH3 (optional) | Digastric / suprahyoid | Under chin, active during tongue movement |
| REF | Mastoid (behind ear) or bony area | Reference |

Note: For silent speech, tongue and larynx muscles are key — the submental (under chin) area is most important.

### 4.2 Data Collection Protocol for Silent Speech
Write a guided collection script `pc/collect_speech_dataset.py`:

**Session structure:**
1. **Rest** — 30 sec (eyes closed, relaxed face, no subvocalization)
2. **Prompted subvocalization** — show word on screen for 3 sec, subject "thinks" the word without moving lips or vocalizing
3. **Break** — 5 sec rest between words

**Vocabulary (start small):**
- Vowels: /a/, /e/, /i/, /o/, /u/ (subvocalized)
- Digits: "one", "two", "three", "four", "five"
- Commands: "yes", "no", "left", "right", "stop"

**Repetitions:** Each word 20 times per session, 3+ sessions on different days.

### 4.3 Synchronization
- For ground truth: display word + timestamp on screen, record alongside EMG
- Optionally record audio from microphone (even silent — to detect if subject accidentally vocalizes)

### 4.4 Data Quality Checks
- Visual inspection: do different words produce different EMG patterns?
- Check that EMG bursts are timed with prompts (cross-correlation)
- Discard trials where no visible EMG activity is present (subject not actually subvocalizing)

---

## Phase 5 — Silent Speech Classification

### 5.1 Preprocessing for Speech EMG
- Bandpass: 20–400 Hz (facial EMG has slightly lower frequency content than limb)
- Window: 500 ms to 1 second (speech gestures are slower)
- Trial-based (not sliding window): extract one window per prompted trial

### 5.2 Feature Extraction (same as Phase 2, but now per trial)
- Add spectral features:
  - Power in bands: 20–50, 50–100, 100–200, 200–400 Hz
  - Median frequency
  - Spectral entropy
- Add time-domain: RMS, MAV, WL, ZC, SSC (same as before)

### 5.3 Model Training (Vowel Classification)
Start with 5-class vowel classification:
- Train/test split (per session, leave-one-session-out for generalization test)
- Models to try:
  1. Random Forest
  2. SVM (RBF)
  3. XGBoost
  4. 1D CNN on raw signal (skip feature extraction)

**Expected baseline:** ~40–50% for 5-class (random = 20%). Good result: > 70%.

### 5.4 Deep Learning (if classical ML plateaus)
1D CNN architecture:
```
Input: (750 samples × 3 channels) for 1.5 sec window
↓
Conv1D(32, kernel=3) → ReLU → MaxPool1D(2)
↓
Conv1D(64, kernel=3) → ReLU → MaxPool1D(2)
↓
Conv1D(128, kernel=3) → ReLU → MaxPool1D(2)
↓
Flatten → Dense(128) → Dropout(0.5) → Dense(n_classes)
```

### 5.5 Word Classification
- If vowels work, move to word classification (5–10 word vocabulary)
- Use LSTM or Transformer to capture temporal dynamics of longer words

---

## Phase 6 — Real-Time Silent Speech

### 6.1 Model Optimization
- Quantize model (int8 for TensorFlow Lite or ONNX quantization)
- Reduce window size to minimize latency
- Target: inference < 100 ms on PC (trivial if using CPU for small models)

### 6.2 Streaming Pipeline
```
ESP32 → WiFi/UDP → PC buffer (1.5 sec ring buffer)
                    ↓ every 200 ms
                feature extraction on latest window
                    ↓
                model prediction
                    ↓
                display predicted word (or "no speech")
```

### 6.3 Evaluation
- Live accuracy over 100 trials
- False activation rate (predicting speech when resting)
- Latency from intended speech to prediction output

### 6.4 Final Demo
- Real-time display showing predicted word
- Optionally: text-to-speech output (play audio of the predicted word)
- Alternatively: type predicted word to a text field

---

## Quick Reference: Pinout Summary

```
ADS1293          ESP32
───────          ─────
SCLK      →      GPIO 18 (SCK)
DIN/MOSI  →      GPIO 23 (MOSI)
DOUT/MISO →      GPIO 19 (MISO)
CS        →      GPIO 5
DRDY      →      GPIO 4
VCC       →      3.3V
GND       →      GND
```

## Quick Reference: Key ADS1293 Registers

| Addr | Name | Purpose |
|------|------|---------|
| 0x00 | ID | Device ID (read-only, 0x90) |
| 0x01 | CONFIG1 | Sample rate, conversion mode |
| 0x02 | CONFIG2 | Test signals, lead-off |
| 0x03 | CONFIG3 | RLD settings |
| 0x04 | LOFF | Lead-off control |
| 0x05 | START | Start/stop conversions |
| 0x06–0x0B | CH1_CN–CH3_CN | Per-channel gain, enable, polarity |
| 0x0C | RLD_CN | RLD amplifier settings |
| 0x0E | WILSON | Wilson terminal config |
| 0x11 | ERROR_FLAGS | Check for errors |

Consult the [ADS1293 datasheet](https://www.ti.com/lit/ds/symlink/ads1293.pdf) for exact bit fields.
