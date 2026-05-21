"""Unit tests for deterministic date/time answers."""
from datetime import datetime

from winter.brain.localfacts import _ordinal, local_fact_answer

# a fixed reference moment: Wednesday, 20 May 2026, 3:45 PM
_NOW = datetime(2026, 5, 20, 15, 45)


def test_ordinals():
    assert _ordinal(1) == "1st"
    assert _ordinal(2) == "2nd"
    assert _ordinal(3) == "3rd"
    assert _ordinal(4) == "4th"
    assert _ordinal(11) == "11th"   # not 11st
    assert _ordinal(21) == "21st"
    assert _ordinal(20) == "20th"


def test_date_question_uses_the_clock():
    answer = local_fact_answer("What's the date?", _NOW)
    assert answer == "Today is Wednesday, May 20th, 2026."


def test_day_question():
    answer = local_fact_answer("what day is it today", _NOW)
    assert "Wednesday" in answer and "May 20th" in answer


def test_time_question():
    answer = local_fact_answer("what time is it", _NOW)
    assert answer == "It's 3:45 PM."


def test_date_and_time_together():
    answer = local_fact_answer("what's the date and time", _NOW)
    assert "3:45 PM" in answer and "May 20th, 2026" in answer


def test_timezone_question_is_not_intercepted():
    # "...in Tokyo" must fall through to the web/LLM path
    assert local_fact_answer("what time is it in Tokyo", _NOW) is None


def test_non_datetime_question_returns_none():
    assert local_fact_answer("how tall is mount everest", _NOW) is None
    assert local_fact_answer("", _NOW) is None
