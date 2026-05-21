"""Dedicated TTS thread.

PyTorch/MPS models must be created and used on a single consistent thread — a
shared QThreadPool hands work to arbitrary threads and segfaults. This thread
builds the voice engines on itself and serves every request from a queue.

It owns both engines (Chatterbox + Piper) and routes each request to the one
the active character asks for via `params["engine"]`. Replies are spoken
sentence-by-sentence so playback starts as soon as the first sentence is ready.
"""
from __future__ import annotations

import queue
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread


class TTSThread(QThread):
    def __init__(self, bus, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._queue: queue.Queue = queue.Queue()
        self._running = True
        self._engines: dict = {}

    def speak(self, text: str, reference: Optional[Path], params: dict) -> None:
        """Queue a line to synthesize and play. Safe to call from any thread."""
        self._queue.put(("speak", text, reference, params))

    def prepare(self, reference: Optional[Path], params: dict) -> None:
        """Pre-load a voice so its slow conditioning isn't paid per reply."""
        self._queue.put(("prepare", None, reference, params))

    def stop(self) -> None:
        self._running = False
        self._queue.put(None)  # unblock the queue
        self.wait(8000)

    def _engine_for(self, params: dict):
        name = (params or {}).get("engine", "chatterbox")
        engine = self._engines.get(name)
        if engine is None and self._engines:
            engine = next(iter(self._engines.values()))  # fallback
        return engine

    def run(self) -> None:
        from winter.audio.tts import (ChatterboxEngine, PiperEngine,
                                      play_audio, split_sentences)

        # Piper first — it loads in a second or two; Chatterbox takes longer
        for name, factory in (("piper", PiperEngine), ("chatterbox", ChatterboxEngine)):
            try:
                self._engines[name] = factory()
            except Exception as exc:  # noqa: BLE001 - an engine is optional
                print(f"[tts] {name} failed to load:", exc)
        if not self._engines:
            self.bus.tts_ready.emit(False)
            return
        self.bus.tts_ready.emit(True)

        while self._running:
            job = self._queue.get()
            if job is None:
                break
            kind, text, reference, params = job
            engine = self._engine_for(params or {})
            if engine is None:
                continue

            if kind == "prepare":
                try:
                    engine.prepare_voice(reference, params)
                except Exception as exc:  # noqa: BLE001
                    print("[tts] voice prepare failed:", exc)
                continue

            try:  # kind == "speak"
                self.bus.tts_started.emit()
                for sentence in split_sentences(text):
                    audio = engine.synthesize(sentence, reference, params)
                    play_audio(audio, engine.sample_rate, self.bus)
            except Exception as exc:  # noqa: BLE001
                print("[tts] synthesis failed:", exc)
            finally:
                self.bus.tts_finished.emit()
