"""Locating Winter's isolated voice-cloning environment (.venv-voice).

Chatterbox and its heavy dependencies live in their own virtual environment so
their version pins never collide with the main app's. This module just finds
that environment and the worker entry point; `scripts/setup_voice.py` creates
it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from winter import PROJECT_ROOT

VOICE_VENV = PROJECT_ROOT / ".venv-voice"
WORKER_SCRIPT = Path(__file__).resolve().parent / "_chatterbox_worker.py"


def voice_python() -> Optional[Path]:
    """The Python interpreter inside .venv-voice, or None if it isn't set up."""
    for relative in ("bin/python", "Scripts/python.exe"):  # POSIX, then Windows
        candidate = VOICE_VENV / relative
        if candidate.exists():
            return candidate
    return None


def worker_command() -> Optional[list[str]]:
    """The command that launches the voice worker, or None if unavailable."""
    python = voice_python()
    if python is None or not WORKER_SCRIPT.exists():
        return None
    return [str(python), str(WORKER_SCRIPT)]
