"""Microphone sources.

VoiceProcessingMicSource routes capture through the macOS AVAudioEngine voice
processor — hardware echo cancellation + noise suppression, so audio playing on
the Mac (a video, Winter's own replies) doesn't drown out the user. It falls
back to a plain sounddevice stream when voice processing is unavailable.

Both deliver 16 kHz mono int16 through a blocking `read(frames)`.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000


class MicSource(ABC):
    using_aec: bool = False

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def read(self, frames: int) -> np.ndarray:
        """Block until `frames` int16 mono samples are ready; return them.
        Returns an empty array once the source has been stopped."""

    @abstractmethod
    def stop(self) -> None:
        ...


class VoiceProcessingMicSource(MicSource):
    """macOS AVAudioEngine input with voice processing (echo cancellation)."""

    using_aec = True

    def __init__(self) -> None:
        self._engine = None
        self._input_node = None
        self._resampler = None
        self._buf = np.zeros(0, dtype=np.int16)
        self._cond = threading.Condition()
        self._running = False
        self._max_samples = SAMPLE_RATE * 5  # drop audio older than ~5 s

    def start(self) -> None:
        import soxr
        from AVFoundation import AVAudioEngine

        engine = AVAudioEngine.alloc().init()
        node = engine.inputNode()
        ok, err = node.setVoiceProcessingEnabled_error_(True, None)
        if not ok:
            raise RuntimeError(f"voice processing unavailable ({err})")

        # By default voice processing ducks ALL other system audio the whole
        # time it runs (macOS "voice call" behaviour). Set it to the minimum
        # ducking level so videos/music stay at normal volume. macOS 14+.
        try:
            from AVFoundation import \
                AVAudioVoiceProcessingOtherAudioDuckingLevelMin
            node.setVoiceProcessingOtherAudioDuckingConfiguration_(
                (False, AVAudioVoiceProcessingOtherAudioDuckingLevelMin)
            )
        except Exception:  # noqa: BLE001 - older macOS lacks this knob
            pass

        in_fmt = node.outputFormatForBus_(0)
        in_rate = float(in_fmt.sampleRate())
        self._resampler = soxr.ResampleStream(
            in_rate, SAMPLE_RATE, 1, dtype="float32", quality="HQ",
        )
        self._running = True
        node.installTapOnBus_bufferSize_format_block_(
            0, 4096, in_fmt, self._tap_block,
        )
        engine.prepare()
        ok, err = engine.startAndReturnError_(None)
        if not ok:
            raise RuntimeError(f"audio engine failed to start ({err})")
        self._engine = engine
        self._input_node = node

    def _tap_block(self, buffer, when) -> None:
        """Realtime CoreAudio callback — must never raise."""
        try:
            n = int(buffer.frameLength())
            if n == 0:
                return
            channels = buffer.floatChannelData()
            if not channels:
                return
            # channel 0 = the voice-processed (echo-cancelled) mono signal
            mono = np.frombuffer(channels[0].as_buffer(n), dtype=np.float32)
            chunk = self._resampler.resample_chunk(mono)
            if len(chunk) == 0:
                return
            pcm = np.clip(chunk * 32768.0, -32768, 32767).astype(np.int16)
            with self._cond:
                self._buf = np.concatenate((self._buf, pcm))
                if len(self._buf) > self._max_samples:
                    self._buf = self._buf[-self._max_samples:]
                self._cond.notify_all()
        except Exception:  # noqa: BLE001 - a raise here would crash the process
            pass

    def read(self, frames: int) -> np.ndarray:
        with self._cond:
            while self._running and len(self._buf) < frames:
                self._cond.wait(0.5)
            if len(self._buf) < frames:
                return np.zeros(0, dtype=np.int16)
            out = self._buf[:frames]
            self._buf = self._buf[frames:]
            return np.ascontiguousarray(out)

    def stop(self) -> None:
        with self._cond:
            self._running = False
            self._cond.notify_all()
        if self._engine is not None:
            try:
                self._engine.stop()
                self._input_node.removeTapOnBus_(0)
            except Exception:  # noqa: BLE001
                pass
        self._engine = None
        self._input_node = None


class SoundDeviceMicSource(MicSource):
    """Plain microphone capture — the fallback when voice processing fails."""

    using_aec = False

    def __init__(self, device: Optional[int] = None) -> None:
        self._device = device
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16",
            blocksize=0, device=self._device,
        )
        self._stream.start()

    def read(self, frames: int) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype=np.int16)
        data, _ = self._stream.read(frames)
        return np.ascontiguousarray(data[:, 0])

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None


def open_mic_source(settings) -> MicSource:
    """Open the mic. Voice processing only if explicitly enabled (it ducks all
    other audio); otherwise a plain microphone."""
    if getattr(settings.audio, "echo_cancellation", False):
        try:
            source = VoiceProcessingMicSource()
            source.start()
            print("[mic] echo cancellation active (macOS voice processing)")
            return source
        except Exception as exc:  # noqa: BLE001
            print(f"[mic] voice processing unavailable, using plain mic: {exc}")
    source = SoundDeviceMicSource(settings.audio.input_device)
    source.start()
    print("[mic] plain microphone")
    return source
