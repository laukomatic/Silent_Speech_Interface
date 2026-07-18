"""Smoke tests: verify the conda env is set up correctly.

These are intentionally trivial. They catch the most common "I forgot to
``conda activate ssi``" or "the environment.yml is out of date" failure modes
before they get masked behind real code.

When real modules land in pc/ (UDP receiver, ECG preprocessing, R-peak
detector, etc.), add focused tests next to them:

    tests/test_receiver.py
    tests/test_preprocess_ecg.py
    tests/test_pan_tompkins.py
    ...

Follow the pattern: one TestClass per module, parametrize over the inputs,
keep each test under ~30 lines.
"""

from __future__ import annotations

import importlib
import sys


def test_python_version() -> None:
    """We require Python 3.11+ (per environment.yml)."""
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version}"


def test_core_imports() -> None:
    """All conda-forge runtime deps from environment.yml must import."""
    for name in ("numpy", "scipy", "sklearn", "pandas", "serial", "matplotlib"):
        importlib.import_module(name)


def test_dev_imports() -> None:
    """Dev tools (lint, format, type-check, test) must import."""
    for name in ("ruff", "mypy", "pytest", "pre_commit"):
        importlib.import_module(name)


def test_pip_imports() -> None:
    """pip-only deps must import."""
    for name in ("pyqtgraph", "neurokit2"):
        importlib.import_module(name)
