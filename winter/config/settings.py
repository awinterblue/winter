"""Global settings — loaded from and saved to config/settings.yaml."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

import yaml

from winter import CONFIG_DIR


def _only_known(cls, data: dict) -> dict:
    """Drop unknown keys so an out-of-date yaml never crashes construction."""
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in (data or {}).items() if k in known}


@dataclass
class AudioSettings:
    input_device: Optional[int] = None
    sample_rate: int = 16000
    # macOS voice processing cancels playing audio from the mic, but ducks all
    # other audio the whole time it runs — off by default for that reason.
    echo_cancellation: bool = False
    # briefly lower system volume only while capturing a command
    duck_while_listening: bool = True


@dataclass
class STTSettings:
    model: str = "base.en"
    compute_type: str = "int8"
    language: Optional[str] = "en"


@dataclass
class LLMSettings:
    model: str = "llama3.2:3b"
    host: str = "http://localhost:11434"


@dataclass
class CameraSettings:
    index: int = 0
    width: int = 640
    height: int = 480


@dataclass
class VisualizerSettings:
    enabled: bool = True
    x: Optional[int] = None
    y: Optional[int] = None
    size: int = 230


@dataclass
class Settings:
    active_character: str = "default"
    voice_enabled: bool = True
    camera_enabled: bool = False
    audio: AudioSettings = field(default_factory=AudioSettings)
    stt: STTSettings = field(default_factory=STTSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)
    visualizer: VisualizerSettings = field(default_factory=VisualizerSettings)
    path: Optional[Path] = field(default=None, repr=False, compare=False)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        path = path or (CONFIG_DIR / "settings.yaml")
        data = {}
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        settings = cls(
            active_character=data.get("active_character", "default"),
            voice_enabled=bool(data.get("voice_enabled", True)),
            camera_enabled=bool(data.get("camera_enabled", False)),
            audio=AudioSettings(**_only_known(AudioSettings, data.get("audio"))),
            stt=STTSettings(**_only_known(STTSettings, data.get("stt"))),
            llm=LLMSettings(**_only_known(LLMSettings, data.get("llm"))),
            camera=CameraSettings(**_only_known(CameraSettings, data.get("camera"))),
            visualizer=VisualizerSettings(**_only_known(VisualizerSettings, data.get("visualizer"))),
        )
        settings.path = path
        return settings

    def to_dict(self) -> dict:
        return {
            "active_character": self.active_character,
            "voice_enabled": self.voice_enabled,
            "camera_enabled": self.camera_enabled,
            "audio": asdict(self.audio),
            "stt": asdict(self.stt),
            "llm": asdict(self.llm),
            "camera": asdict(self.camera),
            "visualizer": asdict(self.visualizer),
        }

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
