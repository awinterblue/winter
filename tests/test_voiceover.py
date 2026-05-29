"""Unit tests for voiceover helpers (the heavy synthesis lives in .venv-voice
and is exercised by the running app, not here)."""
import wave
from pathlib import Path

import numpy as np

from winter.audio.voiceover import (_silence, _write_wav, next_free_after,
                                    next_free_path)


def test_write_wav_roundtrip(tmp_path: Path) -> None:
    """A round-tripped float32 sine wave comes back at the right rate and length."""
    audio = (np.sin(np.linspace(0, 6.28 * 100, 24000)).astype(np.float32) * 0.5)
    out = tmp_path / "x.wav"
    _write_wav(out, audio, 24000)
    assert out.exists()
    with wave.open(str(out), "rb") as r:
        assert r.getnchannels() == 1
        assert r.getsampwidth() == 2
        assert r.getframerate() == 24000
        assert r.getnframes() == 24000


def test_write_wav_clips_overshoot(tmp_path: Path) -> None:
    """Values outside [-1, 1] must clip to int16 max — they must never wrap."""
    audio = np.array([2.0, -2.0, 0.5], dtype=np.float32)
    out = tmp_path / "clip.wav"
    _write_wav(out, audio, 24000)
    with wave.open(str(out), "rb") as r:
        frames = np.frombuffer(r.readframes(3), dtype="<i2")
    assert frames[0] == 32767                       # clipped to +max
    assert frames[1] == -32767                      # clipped to -1.0 * 32767
    assert abs(int(frames[2]) - int(0.5 * 32767)) <= 1


def test_silence_length_and_dtype() -> None:
    s = _silence(0.5, 24000)
    assert s.shape == (12000,)
    assert s.dtype == np.float32
    assert np.all(s == 0)


def test_write_wav_creates_parent_dir(tmp_path: Path) -> None:
    """The output folder is created if it doesn't already exist."""
    out = tmp_path / "fresh" / "subdir" / "x.wav"
    _write_wav(out, np.zeros(8, dtype=np.float32), 24000)
    assert out.exists()


# --- next-free filename helpers (so renders never silently overwrite) ---

def test_next_free_path_picks_unused(tmp_path: Path) -> None:
    """Empty dir → base name; then -2, -3, … as each is taken."""
    assert next_free_path(tmp_path) == tmp_path / "voiceover.wav"
    (tmp_path / "voiceover.wav").touch()
    assert next_free_path(tmp_path) == tmp_path / "voiceover-2.wav"
    (tmp_path / "voiceover-2.wav").touch()
    assert next_free_path(tmp_path) == tmp_path / "voiceover-3.wav"


def test_next_free_path_custom_base(tmp_path: Path) -> None:
    (tmp_path / "narration.wav").touch()
    assert next_free_path(tmp_path, "narration") == tmp_path / "narration-2.wav"


def test_next_free_path_missing_dir_does_not_create_it(tmp_path: Path) -> None:
    """Querying a name doesn't materialise the folder — that's the writer's job."""
    missing = tmp_path / "missing"
    assert next_free_path(missing) == missing / "voiceover.wav"
    assert not missing.exists()


def test_next_free_after_increments_numbered_suffix(tmp_path: Path) -> None:
    (tmp_path / "narration.wav").touch()
    (tmp_path / "narration-2.wav").touch()
    saved = tmp_path / "narration-2.wav"
    assert next_free_after(saved) == tmp_path / "narration-3.wav"


def test_next_free_after_preserves_user_chosen_base(tmp_path: Path) -> None:
    """A custom name like `my-script.wav` becomes `my-script-2.wav` next."""
    saved = tmp_path / "my-script.wav"
    saved.touch()
    assert next_free_after(saved) == tmp_path / "my-script-2.wav"


def test_next_free_after_does_not_mistake_hyphenated_words_for_a_number(
        tmp_path: Path) -> None:
    """`video-1-final.wav` ends with a word, not a number — don't strip it."""
    saved = tmp_path / "video-1-final.wav"
    saved.touch()
    assert next_free_after(saved) == tmp_path / "video-1-final-2.wav"
