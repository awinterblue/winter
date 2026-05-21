"""Tiny UI sounds. Best-effort — never raises into the caller."""
from __future__ import annotations

import numpy as np


def play_chime(frequency: float = 880.0, duration: float = 0.12,
               sample_rate: int = 44100, volume: float = 0.18) -> None:
    """Play a short sine 'I'm listening' chime (non-blocking)."""
    try:
        import sounddevice as sd

        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.sin(2 * np.pi * frequency * t)
        # 10 ms fades to avoid clicks
        fade = max(1, int(sample_rate * 0.01))
        envelope = np.ones_like(wave)
        envelope[:fade] = np.linspace(0, 1, fade)
        envelope[-fade:] = np.linspace(1, 0, fade)
        sd.play((wave * envelope * volume).astype(np.float32), sample_rate)
    except Exception:
        pass
