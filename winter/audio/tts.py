"""Text-to-speech engines.

Two engines behind one interface, chosen per character:
- ChatterboxEngine — clones a voice from a reference clip (high quality, slow).
- PiperEngine — a fast generic voice (near real-time, no cloning).
"""
from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np

from winter import MODELS_DIR

# let unsupported MPS ops fall back to CPU instead of erroring
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

_DEFAULT_SR = 24000

# matches *roleplay emotes* so the TTS does not read them aloud
_EMOTE_RE = re.compile(r"\*[^*\n]*\*")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def clean_for_speech(text: str) -> str:
    """Strip *stage directions* / emotes and tidy whitespace before synthesis."""
    return " ".join(_EMOTE_RE.sub("", text or "").split())


def pitch_shift(audio: np.ndarray, factor: float) -> np.ndarray:
    """Raise/lower pitch by `factor` while keeping the duration unchanged.

    Resampling alone shifts pitch *and* duration; the caller pairs this with a
    matching speech-rate slowdown so only the pitch changes (see PiperEngine).
    """
    if factor == 1.0 or len(audio) == 0:
        return audio
    new_len = max(1, int(round(len(audio) / factor)))
    src = np.linspace(0.0, len(audio) - 1, new_len)
    return np.interp(src, np.arange(len(audio)), audio).astype(np.float32)


def split_sentences(text: str, min_chars: int = 40) -> list[str]:
    """Split text into sentence-ish chunks for streamed synthesis.

    Tiny fragments are merged into neighbours — short clips make Chatterbox
    ramble and aren't worth a separate synthesis call.
    """
    text = clean_for_speech(text)
    if not text:
        return []
    raw = [p.strip() for p in _SENTENCE_RE.split(text) if p.strip()]
    if not raw:
        return [text]
    merged: list[str] = []
    buffer = ""
    for sentence in raw:
        buffer = f"{buffer} {sentence}".strip() if buffer else sentence
        if len(buffer) >= min_chars:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]} {buffer}"
        else:
            merged.append(buffer)
    return merged


class TTSEngine(ABC):
    """Synthesize speech. Selected per character via `tts.engine`."""

    sample_rate: int = _DEFAULT_SR

    @abstractmethod
    def prepare_voice(self, voice_reference: Optional[Path] = None,
                      params: Optional[dict] = None) -> None:
        """Load a voice's conditioning ahead of time (slow part, done once)."""

    @abstractmethod
    def synthesize(self, text: str, voice_reference: Optional[Path] = None,
                   params: Optional[dict] = None) -> np.ndarray:
        """Return float32 mono audio for `text`."""


class ChatterboxEngine(TTSEngine):
    """Voice cloning from a reference clip. High quality, slow."""

    def __init__(self) -> None:
        import torch
        from chatterbox.tts import ChatterboxTTS

        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        self._model = ChatterboxTTS.from_pretrained(self.device)
        self.sample_rate = int(getattr(self._model, "sr", _DEFAULT_SR))
        self._default_conds = getattr(self._model, "conds", None)
        self._prepared_key: Optional[tuple] = None
        try:
            self.synthesize("Hello there.")  # warm the model
        except Exception:
            pass

    @staticmethod
    def _ref_path(voice_reference: Optional[Path]) -> Optional[str]:
        if voice_reference is not None and Path(voice_reference).exists():
            return str(voice_reference)
        return None

    def prepare_voice(self, voice_reference: Optional[Path] = None,
                      params: Optional[dict] = None) -> None:
        """Analyse the reference clip into conditionals — done once per voice."""
        params = params or {}
        exaggeration = float(params.get("exaggeration", 0.5))
        ref = self._ref_path(voice_reference)
        key = (ref, exaggeration)
        if key == self._prepared_key:
            return
        if ref is not None:
            self._model.prepare_conditionals(ref, exaggeration=exaggeration)
        elif self._default_conds is not None:
            self._model.conds = self._default_conds
        self._prepared_key = key

    def synthesize(self, text: str, voice_reference: Optional[Path] = None,
                   params: Optional[dict] = None) -> np.ndarray:
        import torch

        text = clean_for_speech(text)
        if not text:
            return np.zeros(0, dtype=np.float32)
        params = params or {}
        self.prepare_voice(voice_reference, params)  # no-op if already loaded
        with torch.no_grad():
            wav = self._model.generate(
                text,
                exaggeration=float(params.get("exaggeration", 0.5)),
                cfg_weight=float(params.get("cfg_weight", 0.5)),
            )
        return wav.detach().cpu().numpy().astype(np.float32).reshape(-1)


class PiperEngine(TTSEngine):
    """A fast, generic local voice — near real-time, no cloning."""

    def __init__(self, default_voice: str = "en_US-amy-medium") -> None:
        self._dir = MODELS_DIR / "piper"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._default_voice = default_voice
        self._voices: dict = {}
        self._load(default_voice)

    def _load(self, name: str):
        from piper import PiperVoice
        from piper.download_voices import download_voice

        model = self._dir / f"{name}.onnx"
        if not model.exists():
            download_voice(name, self._dir)
        config = self._dir / f"{name}.onnx.json"
        voice = PiperVoice.load(
            str(model), str(config) if config.exists() else None,
        )
        self._voices[name] = voice
        self.sample_rate = int(getattr(voice.config, "sample_rate", 22050))
        return voice

    def prepare_voice(self, voice_reference: Optional[Path] = None,
                      params: Optional[dict] = None) -> None:
        name = (params or {}).get("voice", self._default_voice)
        if name not in self._voices:
            self._load(name)

    def synthesize(self, text: str, voice_reference: Optional[Path] = None,
                   params: Optional[dict] = None) -> np.ndarray:
        from piper import SynthesisConfig

        params = params or {}
        name = params.get("voice", self._default_voice)
        voice = self._voices.get(name) or self._load(name)
        self.sample_rate = int(getattr(voice.config, "sample_rate", 22050))
        text = clean_for_speech(text)
        if not text:
            return np.zeros(0, dtype=np.float32)

        # `pitch` > 1 = cuter/younger. Speak slower by the same factor so the
        # later resample raises pitch without speeding the speech up.
        pitch = float(params.get("pitch", 1.0))
        syn = SynthesisConfig(length_scale=pitch) if pitch != 1.0 else None

        samples = [
            np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
            for chunk in voice.synthesize(text, syn_config=syn)
        ]
        if not samples:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(samples).astype(np.float32) / 32768.0
        return pitch_shift(audio, pitch)


def play_audio(audio: np.ndarray, sample_rate: int, bus=None) -> None:
    """Play float32 mono audio, emitting `audio_level` for the visualizer."""
    if audio is None or len(audio) == 0:
        return
    import sounddevice as sd

    block = max(1, int(sample_rate * 0.05))  # 50 ms blocks
    peak = float(np.max(np.abs(audio))) or 1.0
    with sd.OutputStream(samplerate=sample_rate, channels=1,
                         dtype="float32") as stream:
        for start in range(0, len(audio), block):
            chunk = np.ascontiguousarray(audio[start:start + block])
            stream.write(chunk)
            if bus is not None:
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                bus.audio_level.emit(min(1.0, rms / peak * 1.5))
    if bus is not None:
        bus.audio_level.emit(0.0)
