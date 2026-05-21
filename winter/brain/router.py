"""Routes a transcript to an action.

Unambiguous commands ("pause", "next", "volume up") are handled deterministically
without the LLM — instant and reliable. Volume amounts, questions and chit-chat
go to the LLM; questions also do a web search first.
"""
from __future__ import annotations

import string
from dataclasses import dataclass

from winter.brain import youtube
from winter.brain.intents import Intent, IntentType
from winter.brain.localfacts import local_fact_answer
from winter.system import control

_MEDIA_LABELS = {
    "play_pause": "Play / pause",
    "next": "Next",
    "previous": "Previous",
}

# normalized transcript -> (kind, value); resolved without the LLM
_FASTPATH: dict[str, tuple[str, object]] = {
    # media transport
    "play": ("media", "play_pause"),
    "pause": ("media", "play_pause"),
    "resume": ("media", "play_pause"),
    "stop": ("media", "play_pause"),
    "next": ("media", "next"),
    "skip": ("media", "next"),
    "next video": ("media", "next"),
    "next song": ("media", "next"),
    "next track": ("media", "next"),
    "previous": ("media", "previous"),
    "previous video": ("media", "previous"),
    "previous song": ("media", "previous"),
    "previous track": ("media", "previous"),
    "back": ("media", "previous"),
    "go back": ("media", "previous"),
    # volume
    "louder": ("volume_change", 2),
    "volume up": ("volume_change", 2),
    "turn it up": ("volume_change", 2),
    "quieter": ("volume_change", -2),
    "softer": ("volume_change", -2),
    "volume down": ("volume_change", -2),
    "turn it down": ("volume_change", -2),
    "mute": ("volume_set", 0),
}

# media words that, when they LEAD a phrase, define the intent even if STT
# appended extra or hallucinated words ("previous. they drive us." -> previous).
# "play" is deliberately absent: "play <song>" must reach the LLM so it can be
# routed to YouTube rather than treated as a bare play/pause.
_MEDIA_FIRST_WORD = {
    "pause": "play_pause",
    "stop": "play_pause",
    "resume": "play_pause",
    "next": "next",
    "skip": "next",
    "previous": "previous",
    "back": "previous",
}


@dataclass
class RouteResult:
    """Outcome of routing — what to show, and optionally what to speak aloud."""

    display: str               # short status line for the menu
    speak: str | None = None   # text to speak in character, or None for commands


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return " ".join(text.split())


def fastpath_intent(text: str) -> Intent | None:
    """Resolve an unambiguous command without the LLM, or None if it needs one."""
    norm = _normalize(text)
    if not norm:
        return None

    hit = _FASTPATH.get(norm)
    if hit is not None:
        kind, value = hit
        if kind == "media":
            return Intent(type=IntentType.MEDIA, media_action=str(value), raw=text)
        if kind == "volume_change":
            return Intent(type=IntentType.VOLUME_CHANGE, amount=int(value), raw=text)
        if kind == "volume_set":
            return Intent(type=IntentType.VOLUME_SET, amount=int(value), raw=text)

    # a media word leading the phrase wins even with trailing junk words
    action = _MEDIA_FIRST_WORD.get(norm.split()[0])
    if action is not None:
        return Intent(type=IntentType.MEDIA, media_action=action, raw=text)
    return None


class IntentRouter:
    def __init__(self, llm, websearch, bus):
        self.llm = llm
        self.websearch = websearch
        self.bus = bus

    def handle(self, text: str, character) -> RouteResult:
        """Parse `text`, execute it, and return what to show / speak."""
        text = (text or "").strip()
        if not text:
            return RouteResult("I didn't catch that.")

        # the date/time must come from the clock, never the LLM or the web
        fact = local_fact_answer(text)
        if fact is not None:
            return RouteResult(display=fact, speak=fact)

        intent = fastpath_intent(text)
        if intent is None:
            try:
                data = self.llm.parse_intent(text)
            except Exception as exc:  # noqa: BLE001
                return RouteResult(f"My brain isn't responding ({exc}).")
            intent = Intent.from_dict(data, raw=text)
        return self.execute(intent, character)

    def execute(self, intent: Intent, character) -> RouteResult:
        if intent.type == IntentType.VOLUME_CHANGE:
            steps = intent.amount or 1
            level = control.change_volume(steps)
            return RouteResult(f"Volume {'up' if steps > 0 else 'down'} — now {level}%.")

        if intent.type == IntentType.VOLUME_SET:
            level = control.set_volume(intent.amount)
            return RouteResult(f"Volume set to {level}%.")

        if intent.type == IntentType.MEDIA:
            action = intent.media_action or "play_pause"
            method = control.media(action)
            if method == "youtube" and action in ("next", "previous"):
                label = "Next video." if action == "next" else "Previous video."
                return RouteResult(label)
            return RouteResult(f"{_MEDIA_LABELS.get(action, action)}.")

        if intent.type == IntentType.PLAY_YOUTUBE:
            return self._play_youtube(intent)

        if intent.type == IntentType.QUESTION:
            return self._answer_question(intent, character)

        if intent.type == IntentType.CHITCHAT:
            return self._chitchat(intent, character)

        return RouteResult("Sorry, I didn't understand that command.")

    def _play_youtube(self, intent: Intent) -> RouteResult:
        query = (intent.query or intent.raw).strip()
        if not query:
            return RouteResult("What would you like me to play?")
        self.bus.status_message.emit(f"Finding “{query}” on YouTube…")
        try:
            found = youtube.play(query)
        except Exception as exc:  # noqa: BLE001
            return RouteResult(f"I couldn't reach YouTube ({exc}).")
        if found:
            return RouteResult(f"Playing “{query}” on YouTube.")
        return RouteResult(f"Opened a YouTube search for “{query}”.")

    def _answer_question(self, intent: Intent, character) -> RouteResult:
        query = intent.query or intent.raw
        self.bus.status_message.emit("Searching the web…")
        results = self.websearch.search(query)
        try:
            answer = self.llm.answer(character.personality_prompt, query, results)
        except Exception as exc:  # noqa: BLE001
            return RouteResult(f"I couldn't think of an answer ({exc}).")
        answer = answer or "Sorry, I couldn't find anything on that."
        return RouteResult(display=answer, speak=answer)

    def _chitchat(self, intent: Intent, character) -> RouteResult:
        try:
            reply = self.llm.roleplay(character.personality_prompt, intent.raw)
        except Exception as exc:  # noqa: BLE001
            return RouteResult(f"I'm a bit tongue-tied ({exc}).")
        reply = reply or "Hmm, I'm not sure what to say to that."
        return RouteResult(display=reply, speak=reply)
