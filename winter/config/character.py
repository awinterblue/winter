"""Character profiles — each is a folder under config/characters/<id>/."""
from __future__ import annotations

import re
import shutil
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


def slugify(name: str) -> str:
    """Reduce a display name to a safe folder id (lowercase alphanumerics)."""
    slug = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    return slug or "character"


def install_sprite(src: Path, dest: Path) -> None:
    """Save a user-chosen image into a sprite folder as a PNG, scaled down if
    very large. Raises ValueError on an unreadable image."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage

    image = QImage(str(src))
    if image.isNull():
        raise ValueError("that file isn't a readable image")
    max_dim = 1024  # keep the stored sprite a sensible size
    if image.width() > max_dim or image.height() > max_dim:
        image = image.scaled(
            max_dim, max_dim,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(dest), "PNG"):
        raise IOError(f"could not save the sprite to {dest}")


def _extract_audio(src: Path, dest: Path, max_seconds: float = 25.0) -> None:
    """Decode the audio track of any audio/video file into a mono WAV clip,
    trimmed to the first `max_seconds` — a short, clean clip clones best."""
    import wave

    import av  # PyAV bundles its own ffmpeg; handles .mov/.mp4/.mp3/.wav/...
    import numpy as np

    rate = 24000
    limit = int(max_seconds * rate)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)

    def _frames(out) -> list:
        if out is None:
            return []
        return out if isinstance(out, list) else [out]

    chunks: list = []
    collected = 0
    with av.open(str(src)) as container:
        if not container.streams.audio:
            raise ValueError("that file has no audio track")
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            for out in _frames(resampler.resample(frame)):
                samples = out.to_ndarray().reshape(-1)
                chunks.append(samples)
                collected += samples.shape[0]
            if collected >= limit:
                break
        else:  # reached the file's end before the limit — flush the resampler
            for out in _frames(resampler.resample(None)):
                chunks.append(out.to_ndarray().reshape(-1))

    if not chunks:
        raise ValueError("could not read any audio from that file")
    audio = np.concatenate(chunks)[:limit]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as out_wav:
        out_wav.setnchannels(1)
        out_wav.setsampwidth(2)
        out_wav.setframerate(rate)
        out_wav.writeframes(audio.astype("<i2").tobytes())


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

    def create(self, name: str, wake_word: str = "", personality: str = "",
               sprite_src: Optional[Path] = None,
               voice_src: Optional[Path] = None) -> Character:
        """Build a new character folder from user input and return it.

        A voice clip (audio or video) makes the character clone that voice;
        without one it uses the fast default voice. Raises ValueError on bad
        input, and never leaves a half-built folder behind."""
        name = (name or "").strip()
        if not name:
            raise ValueError("the character needs a name")
        wake_word = (wake_word or "").strip() or f"Hey {name}"

        base = slugify(name)
        char_id = base
        suffix = 2
        while (self.dir / char_id).exists():
            char_id = f"{base}{suffix}"
            suffix += 1
        directory = self.dir / char_id
        directory.mkdir(parents=True, exist_ok=True)

        try:
            cloned = voice_src is not None
            if cloned:
                _extract_audio(Path(voice_src), directory / "reference.wav")
            if sprite_src is not None:
                install_sprite(Path(sprite_src),
                               directory / "sprite" / "idle.png")
            data = {
                "id": char_id,
                "display_name": name,
                "wake_word": wake_word,
                "personality_prompt": (personality or "").strip() or (
                    f"You are {name}, a helpful desktop assistant. "
                    "Keep replies short — they will be spoken aloud."
                ),
                "tts": {"engine": "chatterbox"} if cloned else {
                    "engine": "piper", "voice": "en_US-amy-medium",
                },
                "sprite_editable": True,
            }
            (directory / "character.yaml").write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
            )
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)  # no half-built folder
            raise

        self.reload()
        return self._characters[char_id]

    def delete(self, char_id: str) -> bool:
        """Delete a character's folder entirely. Returns True if removed."""
        character = self._characters.get(char_id)
        if character is None or character.directory is None:
            return False
        shutil.rmtree(character.directory, ignore_errors=True)
        if self._active_id == char_id:
            self._active_id = None
        self.reload()
        return True

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
