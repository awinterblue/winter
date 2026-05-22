"""Text-to-speech engines.

Two engines behind one interface, chosen per character:
- ChatterboxEngine — clones a voice from a reference clip, run in an isolated
  subprocess (see _chatterbox_worker.py).
- PiperEngine — a fast generic voice (near real-time, no cloning).
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import re
import subprocess
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import numpy as np

from winter import MODELS_DIR

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


def _read_wav(path: str) -> np.ndarray:
    """Read a 16-bit mono WAV into float32 audio, then delete the file."""
    try:
        with wave.open(path, "rb") as wav:
            frames = wav.readframes(wav.getnframes())
        return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


class ChatterboxEngine(TTSEngine):
    """Voice cloning, run in an isolated subprocess.

    Chatterbox and its heavy dependencies live in a separate environment
    (.venv-voice), so their version pins never collide with the main app's —
    and a crash or GPU stall in Chatterbox cannot take Winter down with it.
    This class is only the client: it launches the worker and exchanges JSON
    with it over a pipe. If the voice environment is not installed, the
    constructor raises ImportError and the TTS thread falls back to Piper.
    """

    _READY_TIMEOUT = 240.0   # model load + warmup (the model is pre-fetched)
    _SPEAK_TIMEOUT = 120.0   # a synthesis far past this means the worker stalled

    def __init__(self) -> None:
        from winter.audio.voice_env import worker_command

        command = worker_command()
        if command is None:
            raise ImportError(
                "voice cloning is not set up — run scripts/setup_voice.py"
            )
        self._command = command
        self._proc: Optional[subprocess.Popen] = None
        self._replies: queue.Queue = queue.Queue()
        atexit.register(self.close)
        self._spawn()

    # ------------------------------------------------------- worker lifecycle
    def _spawn(self) -> None:
        """Launch the worker subprocess and wait for it to report readiness."""
        proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )
        replies: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump, args=(proc, replies),
                         daemon=True).start()
        self._proc = proc
        self._replies = replies
        ready = self._await(self._READY_TIMEOUT)
        if not ready or not ready.get("ready"):
            self.close()
            raise ImportError("the voice worker did not start")
        self.sample_rate = int(ready.get("sample_rate", _DEFAULT_SR))

    @staticmethod
    def _pump(proc: subprocess.Popen, replies: queue.Queue) -> None:
        """Forward the worker's JSON response lines onto the reply queue."""
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    replies.put(json.loads(line))
                except ValueError:
                    pass  # ignore anything that is not a protocol message
        finally:
            replies.put(None)  # sentinel: the worker's output has ended

    def _await(self, timeout: float) -> Optional[dict]:
        try:
            return self._replies.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        """Stop the worker subprocess. Idempotent."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()  # closing stdin tells the worker to exit
        except OSError:
            pass
        try:
            proc.wait(timeout=3.0)
        except Exception:  # noqa: BLE001
            proc.kill()

    # ------------------------------------------------------ request/response
    def _request(self, message: dict, timeout: float) -> dict:
        """Send one request and return the worker's reply. Restarts the worker
        once if it has died; raises if it stalls or will not come back."""
        if self._proc is None or self._proc.poll() is not None:
            self._spawn()
        try:
            self._proc.stdin.write(json.dumps(message) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._spawn()  # worker died mid-write — restart it and resend
            self._proc.stdin.write(json.dumps(message) + "\n")
            self._proc.stdin.flush()
        reply = self._await(timeout)
        if reply is None:
            # silence past the timeout, or the pipe closed: the worker has
            # stalled or crashed. Drop it so the next call starts a fresh one.
            self.close()
            raise RuntimeError("the voice worker stalled")
        return reply

    # ----------------------------------------------------- TTSEngine interface
    @staticmethod
    def _ref(voice_reference: Optional[Path]) -> Optional[str]:
        if voice_reference is not None and Path(voice_reference).exists():
            return str(voice_reference)
        return None

    def prepare_voice(self, voice_reference: Optional[Path] = None,
                      params: Optional[dict] = None) -> None:
        """Pre-analyse the reference clip in the worker — done once per voice."""
        try:
            self._request(
                {"cmd": "prepare", "reference": self._ref(voice_reference),
                 "params": params or {}},
                self._SPEAK_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 - prepare is best-effort
            print("[tts] voice prepare failed:", exc)

    def synthesize(self, text: str, voice_reference: Optional[Path] = None,
                   params: Optional[dict] = None) -> np.ndarray:
        text = clean_for_speech(text)
        if not text:
            return np.zeros(0, dtype=np.float32)
        reply = self._request(
            {"cmd": "speak", "text": text,
             "reference": self._ref(voice_reference), "params": params or {}},
            self._SPEAK_TIMEOUT,
        )
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "voice synthesis failed"))
        self.sample_rate = int(reply.get("sample_rate", self.sample_rate))
        wav_path = reply.get("wav")
        return _read_wav(wav_path) if wav_path else np.zeros(0, dtype=np.float32)


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
