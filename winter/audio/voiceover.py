"""Render long-form narration to a WAV file with the cloned voice engine.

Mirrors how `TTSThread` runs Chatterbox, but writes the result to disk instead
of playing it. The renderer keeps its own Chatterbox engine so a long voiceover
render never blocks the live assistant's voice — and never speaks aloud over
the recording you're trying to make.
"""
from __future__ import annotations

import queue
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

# Chunk size for synthesis. Bigger than the per-sentence chunks used for live
# conversation (where low latency matters) so prosody flows across sentences
# without the model losing the thread on a very long paragraph.
_VOICEOVER_MIN_CHARS = 250
# Tiny pause inserted between chunks so they read as natural sentence breaks.
_GAP_SECONDS = 0.30


def _silence(seconds: float, sample_rate: int) -> np.ndarray:
    return np.zeros(int(max(0.0, seconds) * sample_rate), dtype=np.float32)


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    """Save float32 mono audio as a 16-bit PCM WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(audio.astype(np.float32, copy=False), -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(pcm.tobytes())


class VoiceoverRenderer(QThread):
    """Render narration in the background, on its own thread + engine.

    Owns its own Chatterbox engine so the live TTS thread (which serves
    wake-word replies) is never blocked. The engine is built lazily on the
    first render and stays warm for subsequent ones, so only the first
    voiceover pays the model-load cost.
    """

    progress = pyqtSignal(int, int)     # chunks_done, chunks_total
    finished_ok = pyqtSignal(str)       # output WAV path
    failed = pyqtSignal(str)            # error message

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._cancel = False
        self._engine = None             # ChatterboxEngine, built on first use

    def render(self, text: str, reference: Optional[Path],
               params: Optional[dict], output_path: Path) -> None:
        """Queue a render job. Safe to call from any thread."""
        self._cancel = False
        self._queue.put((text, reference, params or {}, Path(output_path)))

    def stop(self) -> None:
        """Signal the thread to exit; an active render bails between chunks."""
        self._running = False
        self._cancel = True
        self._queue.put(None)
        self.wait(15000)

    def run(self) -> None:
        while self._running:
            job = self._queue.get()
            if job is None:
                break
            text, reference, params, output = job
            try:
                self._render_one(text, reference, params, output)
            except Exception as exc:  # noqa: BLE001 - surfaced to the dialog
                self.failed.emit(str(exc))

        # close the worker subprocess cleanly when the thread exits
        if self._engine is not None:
            closer = getattr(self._engine, "close", None)
            if closer is not None:
                try:
                    closer()
                except Exception:  # noqa: BLE001 - best effort
                    pass

    def _render_one(self, text: str, reference: Optional[Path],
                    params: dict, output: Path) -> None:
        from winter.audio.tts import split_sentences

        chunks = split_sentences(text, min_chars=_VOICEOVER_MIN_CHARS)
        if not chunks:
            self.failed.emit("The script is empty.")
            return
        if self._engine is None:
            # lazy — skip the model load entirely until someone actually renders
            from winter.audio.tts import ChatterboxEngine
            self._engine = ChatterboxEngine()
        engine = self._engine
        # pre-analyse the reference clip once so its slow conditioning step
        # is not repeated per chunk
        engine.prepare_voice(reference, params)
        gap = _silence(_GAP_SECONDS, engine.sample_rate)
        pieces: list[np.ndarray] = []
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            if self._cancel:
                return
            audio = engine.synthesize(chunk, reference, params)
            if audio.size:
                pieces.append(audio)
                if i < total - 1:
                    pieces.append(gap)
            self.progress.emit(i + 1, total)
        full = (np.concatenate(pieces) if pieces
                else np.zeros(0, dtype=np.float32))
        _write_wav(output, full, engine.sample_rate)
        self.finished_ok.emit(str(output))
