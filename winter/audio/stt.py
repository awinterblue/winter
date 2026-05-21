"""Speech-to-text via faster-whisper (local, CPU)."""
from __future__ import annotations

from typing import Optional

import numpy as np

# A natural-sentence hint that biases the decoder toward the command
# vocabulary — short clips like "pause" transcribe far more reliably with it.
_COMMAND_HINT = (
    "Volume up. Volume down. Set volume. Play. Pause. Stop. "
    "Next. Previous. Next video. Go back. Mute."
)

# length of the silent buffer used to warm the encoder at startup
_WARMUP_SAMPLES = 16000


class STTEngine:
    def __init__(self, model: str = "small", compute_type: str = "int8",
                 language: Optional[str] = "en"):
        from faster_whisper import WhisperModel

        self.language = language
        # CTranslate2 has no Metal backend on macOS — CPU + int8 is the
        # sweet spot for short command utterances.
        self._model = WhisperModel(model, device="cpu", compute_type=compute_type)
        # warm the encoder once so the first real command isn't slow
        try:
            self.transcribe(np.zeros(_WARMUP_SAMPLES, dtype=np.int16))
        except Exception:
            pass

    def transcribe(self, audio_int16: np.ndarray) -> str:
        """Transcribe an int16 mono 16 kHz buffer."""
        if audio_int16 is None or len(audio_int16) == 0:
            return ""
        audio = audio_int16.astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=1,                      # greedy — fastest; fine for commands
            initial_prompt=_COMMAND_HINT,     # bias toward the command vocabulary
            condition_on_previous_text=False,
            temperature=0.0,                  # deterministic — no hallucinated retries
            vad_filter=False,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
