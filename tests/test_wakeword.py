"""Tests for the Vosk wake-word engine — spots a phrase in synthesized speech."""
import subprocess

import numpy as np
import pytest
import soundfile as sf

from winter.audio.wakeword import VOSK_MODEL_DIR, VoskWakeWordEngine

pytestmark = pytest.mark.skipif(
    not VOSK_MODEL_DIR.is_dir(), reason="Vosk model not downloaded",
)


def _say(text: str) -> np.ndarray:
    """Synthesize `text` to 16 kHz int16 mono via macOS `say`."""
    wav = "/tmp/winter_wakeword_test.wav"
    subprocess.run(["say", "--data-format=LEI16@16000", "-o", wav, text],
                   check=True)
    audio, _ = sf.read(wav, dtype="int16")
    return audio[:, 0] if audio.ndim > 1 else audio


def _feed(engine: VoskWakeWordEngine, audio: np.ndarray) -> bool:
    """Stream audio through the engine in 80 ms frames; True if it triggered.

    Trailing silence is appended so Vosk finalizes the utterance — the engine
    only acts on finalized results, never live partials.
    """
    silence = np.zeros(1280, dtype=np.int16)
    frames = [audio[i:i + 1280] for i in range(0, len(audio), 1280)]
    frames += [silence] * 25  # ~2 s of silence to force end-of-utterance
    for frame in frames:
        if engine.process(np.ascontiguousarray(frame)):
            return True
    return False


def test_detects_its_wake_phrase():
    engine = VoskWakeWordEngine("hey hu tao")
    assert _feed(engine, _say("hey hu tao"))


def test_ignores_unrelated_speech():
    engine = VoskWakeWordEngine("hey hu tao")
    assert not _feed(engine, _say("what is the weather like today"))


def test_reset_allows_another_detection():
    engine = VoskWakeWordEngine("hey winter")
    assert _feed(engine, _say("hey winter"))
    engine.reset()
    assert _feed(engine, _say("hey winter"))


def test_model_name_is_the_phrase():
    assert VoskWakeWordEngine("hey hu tao").model_name == "hey hu tao"
