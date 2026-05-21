"""Wake-word detection via Vosk.

Vosk is a fully-offline speech recogniser. Constrained to a tiny grammar — just
the wake phrase plus a catch-all — it spots an arbitrary phrase ("Hey Hu Tao")
efficiently enough to run always-on, with no training, account, or cloud.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np

from winter import MODELS_DIR

VOSK_MODEL_DIR = MODELS_DIR / "vosk-model-small-en-us-0.15"
_MIN_WORD_CONF = 0.7    # ignore words the recogniser isn't sure it heard

# Vosk finalizes an utterance after this much trailing silence. The model
# ships with 0.5 s, which makes the wake word feel sluggish — shorten it so
# the phrase registers sooner after you stop speaking.
_ENDPOINT_TUNING = {
    "--endpoint.rule2.min-trailing-silence": "0.25",
    "--endpoint.rule3.min-trailing-silence": "0.5",
    "--endpoint.rule4.min-trailing-silence": "0.7",
}

# loading a Vosk model takes a second or two — cache it so switching
# characters only rebuilds the (cheap) recogniser
_model_cache: dict[str, object] = {}


def _tune_endpointing(model_dir: Path) -> None:
    """Shorten the trailing-silence the recogniser waits for. Idempotent, and
    re-applies itself if the model is ever re-downloaded."""
    conf = model_dir / "conf" / "model.conf"
    if not conf.exists():
        return
    lines = conf.read_text().splitlines()
    out, changed = [], False
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in _ENDPOINT_TUNING:
            tuned = f"{key}={_ENDPOINT_TUNING[key]}"
            changed = changed or tuned != line
            out.append(tuned)
        else:
            out.append(line)
    if changed:
        conf.write_text("\n".join(out) + "\n")


def _load_model(model_dir: Path):
    from vosk import Model

    key = str(model_dir)
    if key not in _model_cache:
        if not model_dir.is_dir():
            raise FileNotFoundError(f"Vosk model not found: {model_dir}")
        _tune_endpointing(model_dir)   # must run before the model is built
        _model_cache[key] = Model(key)
    return _model_cache[key]


class WakeWordEngine(ABC):
    """Feed 16 kHz int16 mono frames; get the wake phrase back when heard."""

    model_name: str = ""

    @abstractmethod
    def process(self, frame: np.ndarray) -> Optional[str]:
        """Return the wake phrase if it triggered this frame, else None."""

    @abstractmethod
    def reset(self) -> None:
        """Clear internal state after a detection or when toggled off."""


class VoskWakeWordEngine(WakeWordEngine):
    """Spots a wake phrase with a grammar-constrained Vosk recogniser."""

    def __init__(self, phrase: str, model_dir: Path = VOSK_MODEL_DIR,
                 sample_rate: int = 16000):
        from vosk import KaldiRecognizer, SetLogLevel

        SetLogLevel(-1)  # silence Vosk's chatty logging
        self.model_name = phrase
        self._phrase = " ".join(phrase.lower().split())
        model = _load_model(model_dir)
        # constrain recognition to just the wake phrase + a catch-all token
        grammar = json.dumps([self._phrase, "[unk]"])
        self._rec = KaldiRecognizer(model, sample_rate, grammar)
        self._rec.SetWords(True)  # per-word confidence

    def process(self, frame: np.ndarray) -> Optional[str]:
        # Only act on a finalized utterance. Live partial results, with this
        # tight grammar, briefly flicker to the full phrase as soon as the
        # first word is heard — so saying just "hey" could false-trigger.
        if not self._rec.AcceptWaveform(frame.tobytes()):
            return None
        result = json.loads(self._rec.Result())
        self._rec.Reset()
        # keep only words the recogniser is genuinely confident it heard, so a
        # word the grammar 'filled in' but you never said cannot count
        heard = " ".join(
            word["word"] for word in result.get("result", [])
            if word.get("conf", 0.0) >= _MIN_WORD_CONF
        )
        if self._phrase and self._phrase in heard:
            return self.model_name
        return None

    def reset(self) -> None:
        self._rec.Reset()
