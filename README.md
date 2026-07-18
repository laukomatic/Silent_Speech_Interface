# Silent Speech Interface

**Goal:** Replicate MIT AlterEgo-like system using ADS1293 + ESP for real-time biopotential acquisition and machine learning analysis. **First test: ECG heart-beat detection (R-peak + BPM).** Final goal: silent speech recognition.

## Hardware

- **ADS1293** — 3-channel, 24-bit biopotential ADC (SPI interface). Designed for ECG, also used here for facial EMG in later phases.
- **ESP32** — WiFi + BLE microcontroller, receives SPI data from ADS1293, streams to PC.
- **Electrodes** — 3× Ag/AgCl gel electrodes (reused for ECG first, then relocated to face for EMG).
- **PC** — Receives stream, runs preprocessing + algorithm.

## Software Stack (PC side)

- **Data acquisition** — Python UDP receiver
- **Preprocessing (ECG)** — bandpass 0.5–40 Hz, 50 Hz notch
- **Preprocessing (EMG, later)** — bandpass 20–450 Hz, 50 Hz notch
- **Analysis (Phase 2–3)** — R-peak detection (scipy / NeuroKit2), HRV features, BPM
- **Classification (Phase 5+)** — scikit-learn (SVM, Random Forest) → eventually PyTorch (CNN, LSTM)
- **Visualization** — matplotlib for live dashboards

---

## Roadmap

### Phase 0: Environment Setup
- [ ] Set up ESP32 development environment (Arduino IDE / PlatformIO)
- [ ] Set up conda env `ssi` from `environment.yml` (`conda env create -f environment.yml`)
- [ ] Wire ADS1293 to ESP32 (SPI: MOSI, MISO, SCK, CS, DRDY)
- [ ] Verify SPI communication: read ADS1293 register IDs

### Phase 1: Data Pipeline (Raw Streaming)
- [ ] Configure ADS1293: 500 SPS, gain ×6–12, RLD enabled, lead-off detection on
- [ ] ESP32 firmware: read ADC via SPI, pack into binary frames, stream over WiFi/UDP
- [ ] PC receiver: parse UDP packets, buffer samples, save to CSV
- [ ] Visualize raw ECG in real time — verify clear QRS spikes
- [ ] Validate signal: spikes should align with wrist pulse

### Phase 2: Heart Beat Detection (R-peak + BPM)
- [ ] Preprocess: bandpass 0.5–40 Hz, 50 Hz notch
- [ ] Detect R-peaks with `scipy.signal.find_peaks` and/or NeuroKit2
- [ ] (Optional) Implement Pan-Tompkins detector from scratch
- [ ] Compute BPM from R-R intervals
- [ ] Real-time BPM display: refresh ≥ 2 Hz, within ±5 of wrist pulse
- [ ] Save annotated dataset (raw + R-peak indices) for Phase 3

### Phase 3: HRV & Robustness
- [ ] Time-domain HRV: mean RR, SDNN, RMSSD, pNN50
- [ ] Frequency-domain HRV: VLF / LF / HF power via Welch on interpolated RR
- [ ] Robustness: motion artifacts, electrode swap, long recording (5+ min)
- [ ] (Optional) Beat classification using MIT-BIH Arrhythmia Database

### Phase 4: Silent Speech — Data Collection
- [ ] Relocate electrodes to facial muscles (zygomaticus, masseter, digastric, tongue base)
- [ ] Design experimental protocol: subvocalize digits / vowels / words in timed prompts
- [ ] Collect multi-session dataset with synchronized audio (optional reference)

### Phase 5: Silent Speech — Classification
- [ ] Classify vowel phonemes (/a/, /i/, /u/, /e/, /o/) from facial EMG
- [ ] Classify short words (digits 0–9, yes/no)
- [ ] Experiment with deeper models: 1D CNN, LSTM, or Transformer on raw signal
- [ ] Evaluate leave-one-session-out cross-validation

### Phase 6: Real-Time Silent Speech
- [ ] Optimize model for low-latency inference (< 100 ms)
- [ ] Streaming pipeline: read → preprocess → infer → display predicted word
- [ ] Closed-loop demo: type predicted word to screen

---

## Project Structure

```
silent-speech-interface/
├── firmware/              # ESP32 Arduino code
│   ├── ads1293/           # ADS1293 driver library
│   ├── streaming/         # WiFi/UDP streaming logic
│   └── main.ino
├── pc/                    # Python PC-side code
│   ├── receiver.py        # UDP receiver + CSV logger
│   ├── preprocess_ecg.py  # ECG filtering
│   ├── pan_tompkins.py    # R-peak detector (DIY)
│   ├── realtime_bpm.py    # Live BPM display
│   ├── hrv.py             # HRV features
│   ├── visualize.py       # Live plotting
│   └── utils.py
├── tests/                 # pytest (one test file per pc/ module)
│   └── test_smoke.py
├── data/                  # Collected datasets (gitignored)
│   ├── raw/               # Raw CSV per session
│   └── processed/         # Annotated R-peaks, features
├── experiments/           # Jupyter notebooks
│   ├── 01_eda.ipynb
│   ├── 02_rpeak_tuning.ipynb
│   └── 03_hrv_analysis.ipynb
├── .pre-commit-config.yaml
├── environment.yml
├── pyproject.toml         # ruff + mypy strict + pytest config
├── PLAN.md
├── AGENTS.md
└── README.md
```
