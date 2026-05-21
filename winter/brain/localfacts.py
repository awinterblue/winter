"""Deterministic answers for things the LLM must not guess — the date and time.

A language model has no idea what 'today' is, and a web search won't reliably
return it either. These come straight from the system clock.
"""
from __future__ import annotations

import re
from datetime import datetime

# date/time questions about *here* — "...in Tokyo" is a timezone query and is
# deliberately left to the web/LLM path.
_DATE_RE = re.compile(r"\b(date|day|today)\b")
_TIME_RE = re.compile(r"\b(time|clock|o'?clock)\b")
_ELSEWHERE_RE = re.compile(r"\bin\s+[a-z]")


def _ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def local_fact_answer(text: str, now: datetime | None = None) -> str | None:
    """Answer a local date/time question from the clock, or None if not one."""
    query = (text or "").lower()
    if _ELSEWHERE_RE.search(query):
        return None  # e.g. "what time is it in Tokyo" — not a local question

    wants_date = bool(_DATE_RE.search(query))
    wants_time = bool(_TIME_RE.search(query))
    if not (wants_date or wants_time):
        return None

    now = now or datetime.now()
    date_str = now.strftime(f"%A, %B {_ordinal(now.day)}, %Y")
    time_str = now.strftime("%-I:%M %p")

    if wants_date and wants_time:
        return f"It's {time_str} on {date_str}."
    if wants_time:
        return f"It's {time_str}."
    return f"Today is {date_str}."
