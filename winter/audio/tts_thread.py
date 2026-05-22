"""Dedicated TTS thread.

PyTorch/MPS models must be created and used on a single consistent thread — a
shared QThreadPool hands work to arbitrary threads and segfaults. This thread
builds the voice engines on itself and serves every request from a queue.

It owns the voice engines and routes each request to the one the active
character asks for via `params["engine"]`. Piper (the fast default voice)
loads at startup; Chatterbox (heavy GPU voice cloning) loads lazily on first
use, so a Piper-only session never pays its cost. Replies are spoken
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
        self._factories: dict = {}

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

    def _ensure_engine(self, name: str):
        """Return a TTS engine, building it on first use (on this thread).

        Piper is built at startup; Chatterbox is built the first time a
        character actually asks for it. A factory that fails (or isn't
        installed) is dropped so it isn't retried on every later request.
        """
        if name in self._engines:
            return self._engines[name]
        factory = self._factories.get(name)
        if factory is None:
            return None
        self._factories[name] = None  # one attempt only
        try:
            self._engines[name] = factory()
            return self._engines[name]
        except ImportError:
            # chatterbox is the optional 'voice-cloning' extra — fine to skip
            print(f"[tts] {name} not installed — skipping (Piper voice used)")
        except Exception as exc:  # noqa: BLE001 - an engine is optional
            print(f"[tts] {name} failed to load:", exc)
        return None

    def _engine_for(self, params: dict):
        name = (params or {}).get("engine", "piper")
        engine = self._ensure_engine(name)
        if engine is None and self._engines:
            engine = next(iter(self._engines.values()))  # fallback
        return engine

    def run(self) -> None:
        from winter.audio.tts import (ChatterboxEngine, PiperEngine,
                                      play_audio, split_sentences)
        self._factories = {"piper": PiperEngine, "chatterbox": ChatterboxEngine}

        # Build Piper now — it loads in a second or two and is the default
        # voice. Chatterbox is heavy (voice cloning on the GPU); build it
        # lazily on first use so a Piper-only session never pays its load
        # cost — nor risks its occasional GPU stalls.
        self._ensure_engine("piper")
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

        # shut any engine subprocesses (the isolated voice worker) down cleanly
        for engine in self._engines.values():
            closer = getattr(engine, "close", None)
            if closer is not None:
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass
