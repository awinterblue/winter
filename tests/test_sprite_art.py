"""Unit tests for per-character sprite-image resolution."""
from winter.config.character import Character


def _character(tmp_path):
    sprite = tmp_path / "sprite"
    sprite.mkdir()
    return Character(
        id="t", display_name="T", wake_word="hey",
        personality_prompt="hi", sprite_dir=sprite, directory=tmp_path,
    ), sprite


def test_no_images_means_code_drawn_sprite(tmp_path):
    char, _ = _character(tmp_path)
    assert not char.has_sprite_images
    assert char.sprite_image("idle") is None


def test_exact_state_image_is_used(tmp_path):
    char, sprite = _character(tmp_path)
    (sprite / "speaking.png").write_bytes(b"png")
    assert char.sprite_image("speaking").name == "speaking.png"


def test_missing_state_falls_back_to_idle(tmp_path):
    char, sprite = _character(tmp_path)
    (sprite / "idle.png").write_bytes(b"png")
    # listening.png is absent -> idle.png stands in
    assert char.sprite_image("listening").name == "idle.png"
    assert char.has_sprite_images


def test_one_idle_image_covers_every_state(tmp_path):
    char, sprite = _character(tmp_path)
    (sprite / "idle.png").write_bytes(b"png")
    for state in ("idle", "listening", "thinking", "speaking"):
        assert char.sprite_image(state) is not None


def test_sprite_editable_flag(tmp_path):
    import yaml

    from winter.config.character import CharacterManager

    # the field defaults to editable
    char, _ = _character(tmp_path)
    assert char.sprite_editable is True

    # a character.yaml can pin it off, and CharacterManager honours that
    fixed = tmp_path / "characters" / "fixed"
    fixed.mkdir(parents=True)
    (fixed / "character.yaml").write_text(
        yaml.safe_dump({"display_name": "Fixed", "sprite_editable": False}),
        encoding="utf-8",
    )
    manager = CharacterManager(characters_dir=tmp_path / "characters")
    assert manager.get("fixed").sprite_editable is False


# --- custom override: upload installs custom.png; reset removes only that ---

def test_custom_sprite_overrides_default_then_reset_restores(tmp_path):
    from PyQt6.QtGui import QImage

    from winter.ui.settings_window import (clear_sprite_images,
                                           install_sprite_image)

    char, sprite = _character(tmp_path)
    # the developer-placed default
    QImage(40, 40, QImage.Format.Format_RGB32).save(str(sprite / "idle.png"), "PNG")
    assert char.sprite_image("idle").name == "idle.png"
    assert not char.has_custom_sprite

    # a user uploads their own image -> goes to custom.png, overrides idle
    source = tmp_path / "uploaded.jpg"
    QImage(80, 60, QImage.Format.Format_RGB32).save(str(source), "JPG")
    dest = install_sprite_image(char, source)
    assert dest.name == "custom.png"
    assert char.has_custom_sprite
    assert char.sprite_image("idle").name == "custom.png"   # override wins
    assert (sprite / "idle.png").exists()                   # default untouched

    # reset removes only the custom override -> back to the default idle.png
    assert clear_sprite_images(char) is True
    assert not char.has_custom_sprite
    assert char.sprite_image("idle").name == "idle.png"
    assert not (sprite / "custom.png").exists()


def test_reset_with_no_custom_sprite_is_safe(tmp_path):
    from winter.ui.settings_window import clear_sprite_images

    char, _ = _character(tmp_path)
    assert clear_sprite_images(char) is False     # nothing to remove, no error
