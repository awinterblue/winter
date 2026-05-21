"""Unit tests for speech text helpers (no model needed)."""
import numpy as np

from winter.audio.tts import clean_for_speech, pitch_shift, split_sentences


def test_strips_emotes():
    assert clean_for_speech("Hello *winks* there") == "Hello there"
    assert clean_for_speech("*waves dramatically* Hi!") == "Hi!"


def test_keeps_parentheses_and_numbers():
    # parentheses often carry real content — must not be dropped
    assert clean_for_speech("Everest (8,849 m) is tall") == "Everest (8,849 m) is tall"


def test_collapses_whitespace():
    assert clean_for_speech("  too    many   spaces ") == "too many spaces"


def test_empty_and_none():
    assert clean_for_speech("") == ""
    assert clean_for_speech(None) == ""  # type: ignore[arg-type]


def test_split_single_sentence():
    assert split_sentences("Hello there friend, how are you today.") == [
        "Hello there friend, how are you today."
    ]


def test_split_multiple_long_sentences():
    parts = split_sentences(
        "This is a reasonably long first sentence here. "
        "And a second one that is also quite long indeed."
    )
    assert len(parts) == 2


def test_split_merges_tiny_fragments():
    # tiny fragments are merged so Chatterbox isn't fed scraps
    parts = split_sentences("Yes. No. Okay then, here is a much longer final part.")
    assert all(len(p) >= 10 for p in parts)


def test_split_empty():
    assert split_sentences("") == []


def test_pitch_shift_factor_one_is_noop():
    audio = np.linspace(-1, 1, 1000, dtype=np.float32)
    assert np.array_equal(pitch_shift(audio, 1.0), audio)


def test_pitch_shift_up_shortens_buffer():
    # pitch up => fewer samples (resample); duration is restored elsewhere
    audio = np.zeros(1000, dtype=np.float32)
    assert len(pitch_shift(audio, 1.25)) < len(audio)


def test_pitch_shift_handles_empty():
    assert len(pitch_shift(np.zeros(0, dtype=np.float32), 1.25)) == 0
