"""Unit tests for character loading, creation, and voice-reference resolution."""
import pytest

from winter.config.character import (CharacterManager, _resolve_voice_reference,
                                     slugify)


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


def test_slugify_reduces_to_alphanumerics():
    assert slugify("Hu Tao") == "hutao"
    assert slugify("My Cool Bot!") == "mycoolbot"
    assert slugify("") == "character"
    assert slugify("???") == "character"


def test_create_character_writes_folder(tmp_path):
    manager = CharacterManager(characters_dir=tmp_path)
    character = manager.create("Test Bot", "Hey Test", "Be helpful.")
    assert character.id == "testbot"
    assert character.display_name == "Test Bot"
    assert character.wake_word == "Hey Test"
    assert (tmp_path / "testbot" / "character.yaml").exists()
    # no voice clip given -> the fast Piper voice
    assert character.tts.get("engine") == "piper"
    # it is discoverable on a fresh load
    assert CharacterManager(characters_dir=tmp_path).get("testbot") is not None


def test_create_character_defaults_wake_word(tmp_path):
    manager = CharacterManager(characters_dir=tmp_path)
    character = manager.create("Banana", personality="Be silly.")
    assert character.wake_word == "Hey Banana"


def test_create_character_gives_unique_ids(tmp_path):
    manager = CharacterManager(characters_dir=tmp_path)
    assert manager.create("Twin").id == "twin"
    assert manager.create("Twin").id == "twin2"


def test_create_character_requires_a_name(tmp_path):
    manager = CharacterManager(characters_dir=tmp_path)
    with pytest.raises(ValueError):
        manager.create("   ")


def test_delete_character_removes_the_folder(tmp_path):
    manager = CharacterManager(characters_dir=tmp_path)
    manager.create("Goner")
    assert manager.get("goner") is not None
    assert manager.delete("goner") is True
    assert manager.get("goner") is None
    assert not (tmp_path / "goner").exists()
