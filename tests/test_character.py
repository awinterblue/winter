"""Unit tests for character loading and voice-reference resolution."""
from winter.config.character import _resolve_voice_reference


def test_finds_configured_wav(tmp_path):
    (tmp_path / "reference.wav").write_bytes(b"fake")
    result = _resolve_voice_reference(tmp_path, "reference.wav")
    assert result is not None and result.name == "reference.wav"


def test_falls_back_to_dropped_in_mp3(tmp_path):
    # configured wav is absent — an mp3 dropped in the folder is found anyway
    (tmp_path / "reference.mp3").write_bytes(b"fake")
    result = _resolve_voice_reference(tmp_path, "reference.wav")
    assert result is not None and result.name == "reference.mp3"


def test_ignores_non_audio_files(tmp_path):
    (tmp_path / "reference.wav.README.md").write_text("placeholder")
    result = _resolve_voice_reference(tmp_path, "reference.wav")
    assert result is None or not result.exists()
