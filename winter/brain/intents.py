"""Intent model — the structured form of a parsed voice command."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntentType(str, Enum):
    VOLUME_CHANGE = "volume_change"   # relative: amount = signed steps
    VOLUME_SET = "volume_set"         # absolute: amount = target 0-100
    MEDIA = "media"                   # media_action set
    PLAY_YOUTUBE = "play_youtube"     # query = song/video to play on YouTube
    QUESTION = "question"             # query needs a web search
    CHITCHAT = "chitchat"             # small talk for the character
    UNKNOWN = "unknown"


@dataclass
class Intent:
    type: IntentType
    amount: int = 0
    media_action: str | None = None
    query: str = ""
    raw: str = ""

    @classmethod
    def from_dict(cls, data: dict, raw: str = "") -> "Intent":
        try:
            itype = IntentType(str(data.get("type", "unknown")))
        except ValueError:
            itype = IntentType.UNKNOWN

        try:
            amount = int(data.get("amount", 0) or 0)
        except (TypeError, ValueError):
            amount = 0

        action = data.get("media_action")
        if action not in ("play_pause", "next", "previous"):
            action = None

        return cls(
            type=itype,
            amount=amount,
            media_action=action,
            query=str(data.get("query") or ""),
            raw=raw,
        )
