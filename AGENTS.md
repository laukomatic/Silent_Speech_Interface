# Silent Speech Interface — Agent Notes

## State of this repo

- **No code yet.** Only docs: `README.md` (overview), `PLAN.md` (detailed step-by-step), `environment.yml` (conda env spec).
- Repo is on `master` with no commits. Anything added is fair game; nothing is sacred yet.
- The plan and README are the **source of truth** for what to build. Read them before suggesting architecture.

## Canonical plan location

- **Authoritative spec**: `PLAN.md` in this repo.
- **Mirror in Anytype**: the "Silent Speech Interface" object in the **Personal** space.
  - `objectId: bafyreidvcsd6a7f347t3cfwkl24iynkp2vpksic4jsd3smftnbmdacx2ye`
  - `spaceId:  bafyreigrow6e4gfrkowor4zl3lobn7q6d27cldmzxbedl4jqkhbi66gisi.18unpclyorm2i`
  - When the user says "update the plan" without specifying which, update **both** `PLAN.md` and the Anytype object. Anytype API is documented in `../Server/AGENTS.md`.
- When `PLAN.md` and Anytype drift, `PLAN.md` wins (it is what gets committed; Anytype is a read mirror).

## Project shape (planned, per `PLAN.md`)

- `firmware/` — ESP32 Arduino code (ADS1293 driver, WiFi/UDP streaming)
- `pc/` — Python pipeline (UDP receiver, ECG preprocessing, R-peak detection, BPM, HRV, later EMG/silent-speech classifiers)
- `data/` — gitignored, raw CSV + processed features
- `experiments/` — Jupyter notebooks for EDA / tuning
- `environment.yml` — conda env `ssi` (Python 3.11, conda-forge, `neurokit2` via pip)

## Toolchain

- **Python**: conda env `ssi`, defined in `environment.yml`. **Do not** create a venv — the user explicitly rejected venv in favor of conda (miniconda at `~/miniconda3`).
  ```bash
  conda env create -f environment.yml    # first time
  conda activate ssi                      # every session
  ```
- **ESP32**: Arduino IDE or PlatformIO. SPI at ~4 MHz, mode per ADS1293 datasheet. Pinout is in `PLAN.md` §0.3 / "Quick Reference" section.
- **ADS1293**: 3-channel 24-bit biopotential ADC. Datasheet: https://www.ti.com/lit/ds/symlink/ads1293.pdf — when configuring registers, check the datasheet, not memory.

## Project conventions established by the user

- **First test is ECG heart-beat detection (R-peak + BPM), NOT arm extension / EMG.** The original arm-extension plan was rejected. The repo went straight from planning to ECG. Do not propose EMG/EMG-classification work until Phase 4 ("Silent Speech") in `PLAN.md`.
- **Electrode placement**: 3-lead ECG (Lead I) — left chest, right chest, lower-left rib as RLD. RLD is strongly recommended for ECG; missing RLD is the most common source of noise.
- **Sampling rate**: 500 SPS. Higher rates are allowed but waste bandwidth.
- **Gain**: ×6 or ×12 for ECG. Don't crank higher — R-peak is ~1 mV.
- **Anytype API version**: `2025-11-08`. The value `2026-07-01` in `~/.config/opencode/opencode.jsonc` is a placeholder and does not work against the self-hosted server.

## When implementing

- `pc/` scripts should stream from UDP, not TCP, at least for the streaming pipeline (per `PLAN.md` §1.3). Keep the binary packet format `[0xAA 0xBB][ts:4][ch1:3][ch2:3][ch3:3][csum:1]` = 16 bytes.
- For real-time plots, prefer `pyqtgraph` over `matplotlib` (already in `environment.yml`). `matplotlib` is fine for notebooks.
- For R-peak detection, use `scipy.signal.find_peaks` first; reach for `neurokit2` only if you need a more robust offline analysis. The plan asks for a Pan-Tompkins implementation too — keep it as a learning exercise, not the production path.
- Save raw CSV per session with a unix-timestamped filename; do not overwrite on session start.

## What is NOT decided yet

- No code style / formatter / linter is configured. **Ask before introducing one** (black? ruff? something else?). The user has not expressed a preference.
- No test framework is set up. The repo has no executable code yet, so there is nothing to test.
- No pre-commit hooks. No CI.

## Commit & push workflow

- **Commit at the end of every session (or after each logical chunk of work)** — this is the user's standing rule, not optional.
- Remote: `https://github.com/laukomatic/Silent_Speech_Interface.git` (configured as `origin`).
- The user will provide a GitHub PAT on request for pushing. Do not store the token in any file in the repo; use it inline in the push command and let it be forgotten.
- Standard commit flow:
  ```bash
  git add <files>
  git commit -m "<message>"
  # when remote push is needed:
  git push https://<TOKEN>@github.com/laukomatic/Silent_Speech_Interface.git master
  ```
- After a push, drop the in-memory token reference and do not log it.
- **Never commit**: anything in `data/`, `*.pyc`, `__pycache__/`, `.venv/`, `venv/`, `*.egg-info/`, `.ipynb_checkpoints/`, `.env`, `*.pem`, `*.key`. The `.gitignore` already covers these.

## Things that look generic but aren't

- "Use venv" — wrong. Use conda (`environment.yml`).
- "Add gitignore for node_modules" — there's no Node in this project.
- "Configure CI with GitHub Actions" — repo has no commits and no code yet; CI is premature.
- "Use a separate branch per phase" — there's no branching convention. Use `master` until told otherwise.
- "You should squash-merge with a conventional commit prefix" — no convention yet, plain messages are fine.
