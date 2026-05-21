"""In-memory application state."""
from dataclasses import dataclass
from enum import Enum, auto


class Phase(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()


@dataclass
class AppState:
    phase: Phase = Phase.IDLE
    voice_enabled: bool = True
    camera_enabled: bool = False
    active_character: str = "default"
    last_transcript: str = ""
    last_result: str = ""
