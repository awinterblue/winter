"""Unit tests for intent parsing (no models or audio required)."""
from winter.brain.intents import Intent, IntentType


def test_volume_change():
    intent = Intent.from_dict({"type": "volume_change", "amount": 3}, raw="volume up 3")
    assert intent.type is IntentType.VOLUME_CHANGE
    assert intent.amount == 3
    assert intent.raw == "volume up 3"


def test_volume_change_negative():
    intent = Intent.from_dict({"type": "volume_change", "amount": -2})
    assert intent.amount == -2


def test_volume_set():
    intent = Intent.from_dict({"type": "volume_set", "amount": "40"})
    assert intent.type is IntentType.VOLUME_SET
    assert intent.amount == 40


def test_media_next():
    intent = Intent.from_dict({"type": "media", "media_action": "next"})
    assert intent.type is IntentType.MEDIA
    assert intent.media_action == "next"


def test_media_action_rejected_when_invalid():
    intent = Intent.from_dict({"type": "media", "media_action": "explode"})
    assert intent.media_action is None


def test_unknown_type_falls_back():
    intent = Intent.from_dict({"type": "nonsense"})
    assert intent.type is IntentType.UNKNOWN


def test_bad_amount_defaults_to_zero():
    intent = Intent.from_dict({"type": "volume_change", "amount": "lots"})
    assert intent.amount == 0


def test_question_query_preserved():
    intent = Intent.from_dict({"type": "question", "query": "how tall is everest"})
    assert intent.type is IntentType.QUESTION
    assert intent.query == "how tall is everest"
