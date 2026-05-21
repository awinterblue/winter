"""Continuous microphone capture: wake-word watch + command recording.

Runs on its own QThread so the Qt UI thread is never blocked. Results are
delivered through the EventBus.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import QThread

from winter.audio.micsource import SAMPLE_RATE, open_mic_source

CHUNK = 1280          # 80 ms @ 16 kHz — wake-word processing frame
VAD_FRAME = 480       # 30 ms @ 16 kHz — webrtcvad frame size

# command-recording tuning (counts of 30 ms VAD frames)
_MAX_FRAMES = int(10_000 / 30)       # 10 s hard cap
_SILENCE_LIMIT = int(600 / 30)       # ~0.6 s trailing silence ends the command
_START_TIMEOUT = int(4000 / 30)      # 4 s with no speech -> give up
_CHIME_GUARD_FRAMES = int(220 / 30)  # skip the wake chime at capture start
_PREROLL_FRAMES = 4                  # ~120 ms kept before speech onset
_TAIL_FRAMES = 5                     # ~150 ms kept after the last speech frame
_DUCK_FACTOR = 0.30                  # volume multiplier while capturing a command


class AudioCaptureThread(QThread):
    def __init__(self, bus, settings, wake_engine, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.settings = settings
        self.wake_engine = wake_engine
        self._running = False
        self._enabled = True
        self._suppressed = False
        self._source = None

    # --- control (called from the UI thread) ---
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled and self.wake_engine:
            self.wake_engine.reset()

    def set_suppressed(self, suppressed: bool) -> None:
        """Mute wake-word detection while the assistant itself is speaking."""
        if self._suppressed and not suppressed and self.wake_engine:
            self.wake_engine.reset()  # drop anything heard during playback
        self._suppressed = suppressed

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

    # --- thread body ---
    def run(self) -> None:
        self._running = True
        try:
            self._source = open_mic_source(self.settings)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self.bus.error.emit(f"Microphone unavailable: {exc}")
            return
        try:
            while self._running:
                frame = self._source.read(CHUNK)
                if len(frame) < CHUNK:
                    continue  # short read => source stopping
                if not self._enabled or self._suppressed:
                    continue
                name = self.wake_engine.process(frame)
                if name:
                    self.bus.wake_word_detected.emit(name)
                    saved_volume = self._duck_volume()
                    try:
                        audio = self._capture_command(self._source)
                    finally:
                        self._restore_volume(saved_volume)
                    if audio is not None and len(audio) > 0:
                        self.bus.command_audio_ready.emit(audio)
                    else:
                        self.bus.listening_stopped.emit()
                    self.wake_engine.reset()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self.bus.error.emit(f"Audio capture failed: {exc}")
        finally:
            if self._source is not None:
                self._source.stop()

    # --- duck system volume only while a command is being captured ---
    def _duck_volume(self) -> Optional[int]:
        """Lower the system volume; return the level to restore, or None."""
        if not self.settings.audio.duck_while_listening:
            return None
        try:
            from winter.system import control

            current = control.get_volume()
            if current > 0:
                control.set_volume(int(current * _DUCK_FACTOR))
            return current
        except Exception:  # noqa: BLE001
            return None

    def _restore_volume(self, saved: Optional[int]) -> None:
        if saved is None:
            return
        try:
            from winter.system import control

            control.set_volume(saved)
        except Exception:  # noqa: BLE001
            pass

    def _capture_command(self, source) -> Optional[np.ndarray]:
        """Record the command, then trim trailing silence for a tight clip."""
        from collections import deque

        import webrtcvad

        self.bus.listening_started.emit()
        vad = webrtcvad.Vad(2)
        frames: list[np.ndarray] = []
        preroll: deque = deque(maxlen=_PREROLL_FRAMES)
        speech_started = False
        silence = 0
        waited = 0
        last_speech = -1

        # drop the wake chime so it isn't mistaken for the command itself
        for _ in range(_CHIME_GUARD_FRAMES):
            if not self._running:
                return None
            source.read(VAD_FRAME)

        for _ in range(_MAX_FRAMES):
            if not self._running:
                break
            frame = source.read(VAD_FRAME)
            if len(frame) < VAD_FRAME:
                break
            is_speech = vad.is_speech(frame.tobytes(), SAMPLE_RATE)
            if not speech_started:
                if is_speech:
                    speech_started = True
                    frames.extend(preroll)   # recover the word onset
                    frames.append(frame)
                    last_speech = len(frames) - 1
                else:
                    preroll.append(frame)
                    waited += 1
                    if waited > _START_TIMEOUT:
                        return None
            else:
                frames.append(frame)
                if is_speech:
                    silence = 0
                    last_speech = len(frames) - 1
                else:
                    silence += 1
                    if silence > _SILENCE_LIMIT:
                        break

        if last_speech < 0:
            return None
        # trim trailing silence — a tight clip stops Whisper hallucinating
        end = min(len(frames), last_speech + 1 + _TAIL_FRAMES)
        return np.concatenate(frames[:end])
