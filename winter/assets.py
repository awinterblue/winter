"""Model assets that are too large for the repo — downloaded on first run.

A fresh clone has no `models/` folder; these helpers fetch what's needed the
first time Winter runs, so the project is self-bootstrapping on any machine.
(faster-whisper, Chatterbox and Piper download their own models separately.)
"""
from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

from winter import MODELS_DIR

VOSK_MODEL_DIR = MODELS_DIR / "vosk-model-small-en-us-0.15"
_VOSK_URL = ("https://alphacephei.com/vosk/models/"
             "vosk-model-small-en-us-0.15.zip")

HAND_MODEL = MODELS_DIR / "hand_landmarker.task"
_HAND_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")


def ensure_vosk_model() -> Path:
    """Return the Vosk model directory, downloading + unzipping it if absent."""
    if not VOSK_MODEL_DIR.is_dir():
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        print("[setup] downloading the Vosk speech model (~40 MB, one time)…")
        with urllib.request.urlopen(_VOSK_URL, timeout=180) as response:
            archive = response.read()
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            zf.extractall(MODELS_DIR)
    return VOSK_MODEL_DIR


def ensure_hand_model() -> Path:
    """Return the hand-tracking model path, downloading it if absent."""
    if not HAND_MODEL.exists():
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        print("[setup] downloading the hand-tracking model (~8 MB, one time)…")
        urllib.request.urlretrieve(_HAND_URL, HAND_MODEL)
    return HAND_MODEL
