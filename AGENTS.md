# Silent Speech Interface — Agent Notes

## State of this repo

- **No application code yet.** Files: `README.md` (overview), `PLAN.md` (detailed step-by-step), `AGENTS.md` (this file), `environment.yml` (conda env), `pyproject.toml` (ruff/mypy/pytest config), `.pre-commit-config.yaml`, `.gitignore`, `tests/test_smoke.py` (env-validation).
- Anything added is fair game; nothing is sacred yet.
- The plan and README are the **source of truth** for what to build. Read them before suggesting architecture.

## Canonical plan location

- **Authoritative spec**: `PLAN.md` in this repo.
- **Mirror in Anytype**: the "Silent Speech Interface" object in the **Personal** space.
  - Anytype object/space IDs live in `.private/anytype.json` (gitignored). Read that file when you need to make API calls; do not paste the IDs into committed docs, AGENTS.md, or code comments.
  - When the user says "update the plan" without specifying which, update **both** `PLAN.md` and the Anytype object. Anytype API is documented in `../Server/AGENTS.md`.
  - API version: `2025-11-08` (also in `.private/anytype.json`). The string `2026-07-01` in `~/.config/opencode/opencode.jsonc` is a known-broken placeholder.
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

## Linters, formatters, type checks, pre-commit, tests

**Linter / formatter / type checker — installed in the `ssi` conda env:**
- **ruff** — single tool for both lint and format. Catches unused imports, undefined names, common bugs (rules: `E`, `F`, `W`, `I`, `B`, `UP`, `SIM`, `C4`, `PIE`, `RUF`; see `pyproject.toml`). Run with `ruff check .` and `ruff format .`.
- **mypy** — static type checker in **strict mode** from day one. Run with `mypy .`. Catches type errors before runtime — vital for signal-processing code where unit mismatches (samples vs ms vs seconds) are easy to get wrong.

**Order of operations** (so the chain doesn't fight itself):
1. `ruff format .`
2. `ruff check . --fix` (apply safe auto-fixes)
3. `mypy .`

**Tests** — `pytest`, configured in `pyproject.toml`. Run with `pytest tests/`.
- `tests/test_smoke.py` is the env-validation smoke test (Python version, all deps importable).
- Add focused tests alongside new modules: `tests/test_<module>.py` per `pc/<module>.py`. Strict mode + `--strict-markers` + warnings as errors — keep tests clean.

**What are pre-commit hooks?**
Git has a feature where scripts in `.git/hooks/` (or `.husky/`) run automatically before/after certain git actions. The most common one is `pre-commit` — a Python tool (`pre-commit.com`) that runs *before* each `git commit`. If any hook fails, the commit is blocked until you fix the issue.

This project's hooks (`.pre-commit-config.yaml`):
- `ruff check --fix` + `ruff format` on staged files
- `mypy` on staged files (strict, scoped to `pc/` and `tests/`)
- `nbstripout` on staged `.ipynb` files (strips output so notebooks don't bloat the diff)
- `detect-private-key` / trailing-whitespace / end-of-file-fixer / mixed-line-ending (LF)

Install once per clone:
```bash
conda activate ssi
pip install pre-commit        # already in environment.yml
pre-commit install
```

Run on demand (without committing):
```bash
pre-commit run --all-files
```

The `pc/` package doesn't exist yet, so the pre-commit hooks will only run over `tests/` and `pyproject.toml` until modules land. As soon as the first `pc/*.py` file shows up, the ruff + mypy hooks will start working on it.

## Commit & push workflow

- **Commit at the end of every session (or after each logical chunk of work)** — this is the user's standing rule, not optional.
- Remote: `https://github.com/laukomatic/Silent_Speech_Interface.git` (configured as `origin`).
- A GitHub MCP server is configured in `~/.config/opencode/opencode.jsonc` (`github` entry, `@modelcontextprotocol/server-github` with the user's PAT in `GITHUB_PERSONAL_ACCESS_TOKEN`). Prefer the MCP tools (`mcp_github_*`) for repo/issue/PR operations.
- For `git push` from the shell, the MCP doesn't cover raw git transport. Use either:
  ```bash
  git push origin master                                    # if a credential helper is configured
  # or
  git push https://x-access-token:<PAT>@github.com/laukomatic/Silent_Speech_Interface.git master
  ```
  Don't store the token in the repo or in any committed file. The PAT lives in `~/.config/opencode/opencode.jsonc`; that's the only place it should be.
- **Never commit**: anything in `data/`, `*.pyc`, `__pycache__/`, `.venv/`, `venv/`, `*.egg-info/`, `.ipynb_checkpoints/`, `.env`, `*.pem`, `*.key`. The `.gitignore` already covers these.

## Things that look generic but aren't

- "Use venv" — wrong. Use conda (`environment.yml`).
- "Add gitignore for node_modules" — there's no Node in this project.
- "Configure CI with GitHub Actions" — repo has no code yet; CI is deliberately deferred.
- "Use a separate branch per phase" — there's no branching convention. Use `master` for everything.
- "You should squash-merge with a conventional commit prefix" — plain commit messages only. No `feat:` / `fix:` prefixes.
