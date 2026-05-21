"""Character profiles — each is a folder under config/characters/<id>/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from winter import CONFIG_DIR

_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aiff", ".aif"}


def _resolve_voice_reference(directory: Path, ref_name: str) -> Optional[Path]:
    """Find the voice-clone clip: the configured name, else any reference.* audio
    file dropped into the character folder (so reference.mp3 just works too)."""
    if ref_name and (directory / ref_name).exists():
        return directory / ref_name
    for candidate in sorted(directory.glob("reference.*")):
        if candidate.suffix.lower() in _AUDIO_EXTS:
            return candidate
    return directory / ref_name if ref_name else None


_SPRITE_STATES = ("idle", "listening", "thinking", "speaking")
# a user-uploaded override, kept separate from the developer-placed defaults
# (idle.png etc.) so it can be added or removed without touching them
CUSTOM_SPRITE = "custom.png"


@dataclass
class Character:
    id: str
    display_name: str
    wake_word: str          # the phrase Vosk listens for, e.g. "Hey Hu Tao"
    personality_prompt: str
    tts: dict = field(default_factory=dict)
    voice_reference: Optional[Path] = None
    sprite_dir: Optional[Path] = None
    sprite_editable: bool = True   # may the user replace the sprite from the UI?
    directory: Optional[Path] = None

    @property
    def has_voice_reference(self) -> bool:
        return self.voice_reference is not None and self.voice_reference.exists()

    def sprite_image(self, state: str) -> Optional[Path]:
        """PNG to draw for a phase. A user-uploaded custom.png overrides
        everything; otherwise the default <state>.png, then idle.png. None
        means: use Winter's built-in code-drawn sprite."""
        if not self.sprite_dir or not self.sprite_dir.is_dir():
            return None
        custom = self.sprite_dir / CUSTOM_SPRITE
        if custom.exists():
            return custom
        exact = self.sprite_dir / f"{state}.png"
        if exact.exists():
            return exact
        idle = self.sprite_dir / "idle.png"
        return idle if idle.exists() else None

    @property
    def has_sprite_images(self) -> bool:
        return any(self.sprite_image(s) for s in _SPRITE_STATES)

    @property
    def has_custom_sprite(self) -> bool:
        """True when a user-uploaded sprite override is installed."""
        return bool(self.sprite_dir
                    and (self.sprite_dir / CUSTOM_SPRITE).exists())


class CharacterManager:
    """Discovers character folders and tracks which one is active."""

    def __init__(self, characters_dir: Optional[Path] = None):
        self.dir = characters_dir or (CONFIG_DIR / "characters")
        self._characters: dict[str, Character] = {}
        self._active_id: Optional[str] = None
        self.reload()

    def reload(self) -> None:
        self._characters.clear()
        if not self.dir.exists():
            return
        for child in sorted(self.dir.iterdir()):
            cfg = child / "character.yaml"
            if child.is_dir() and cfg.exists():
                self._characters[child.name] = self._load_one(child, cfg)

    @staticmethod
    def _load_one(directory: Path, cfg_path: Path) -> Character:
        data = yaml.safe_load(cfg_path.read_text()) or {}
        ref_name = data.get("voice_reference", "reference.wav")
        ref_path = _resolve_voice_reference(directory, ref_name)
        return Character(
            id=data.get("id", directory.name),
            display_name=data.get("display_name", directory.name.title()),
            wake_word=data.get("wake_word", "Hey Winter"),
            personality_prompt=(data.get("personality_prompt") or "").strip(),
            tts=data.get("tts") or {},
            voice_reference=ref_path,
            sprite_dir=directory / "sprite",
            sprite_editable=bool(data.get("sprite_editable", True)),
            directory=directory,
        )

    def list(self) -> list[Character]:
        return list(self._characters.values())

    def get(self, char_id: str) -> Optional[Character]:
        return self._characters.get(char_id)

    def set_active(self, char_id: str) -> Character:
        if char_id in self._characters:
            self._active_id = char_id
        return self.active

    @property
    def active(self) -> Character:
        if self._active_id and self._active_id in self._characters:
            return self._characters[self._active_id]
        if self._characters:
            return next(iter(self._characters.values()))
        # nothing on disk — return a safe built-in fallback
        return Character(
            id="default",
            display_name="Winter",
            wake_word="Hey Winter",
            personality_prompt="You are Winter, a concise, friendly assistant.",
        )
