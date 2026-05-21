"""Unit tests for routing — the deterministic fast-path and LLM branches."""
from winter.brain.intents import IntentType
from winter.brain.router import IntentRouter, _normalize, fastpath_intent
from winter.config.character import Character


# --- fast-path (pure, no LLM) ---------------------------------------------

def test_normalize_strips_punctuation_and_case():
    assert _normalize("  Pause.  ") == "pause"
    assert _normalize("Next Video!") == "next video"


def test_bare_words_route_without_llm():
    assert fastpath_intent("Pause.").media_action == "play_pause"
    assert fastpath_intent("play").media_action == "play_pause"
    assert fastpath_intent("next").media_action == "next"
    assert fastpath_intent("Next video.").media_action == "next"
    assert fastpath_intent("previous").media_action == "previous"


def test_back_routes_to_previous():
    assert fastpath_intent("Back.").media_action == "previous"
    assert fastpath_intent("go back").media_action == "previous"


def test_leading_media_word_wins_over_trailing_junk():
    # STT sometimes appends a hallucinated sentence — the lead word still wins
    assert fastpath_intent("Previous. They drive us.").media_action == "previous"
    assert fastpath_intent("pause the music").media_action == "play_pause"


def test_volume_words():
    assert fastpath_intent("volume up").type is IntentType.VOLUME_CHANGE
    assert fastpath_intent("volume up").amount > 0
    assert fastpath_intent("turn it down").amount < 0


def test_mute():
    intent = fastpath_intent("mute")
    assert intent.type is IntentType.VOLUME_SET
    assert intent.amount == 0


def test_complex_input_defers_to_llm():
    assert fastpath_intent("volume up three") is None
    assert fastpath_intent("what is the tallest mountain") is None
    assert fastpath_intent("") is None


def test_play_song_defers_to_llm():
    # "play <song>" must reach the LLM (-> YouTube), not become bare play/pause
    assert fastpath_intent("play heaven by clairo on youtube") is None
    assert fastpath_intent("play despacito") is None
    # a bare "play" is still an instant play/pause
    assert fastpath_intent("play").media_action == "play_pause"


# --- LLM branches (with fakes — no models, no OS calls) -------------------

class _FakeLLM:
    def __init__(self, intent_type="question"):
        self.intent_type = intent_type

    def parse_intent(self, text):
        return {"type": self.intent_type, "query": text}

    def answer(self, personality_prompt, question, search_results):
        return "It is 8,849 metres tall."

    def roleplay(self, personality_prompt, text):
        return "Hehe, hello to you too!"


class _FakeSearch:
    def search(self, query, max_results=5):
        return ["Everest: about 8849 m above sea level"]


class _FakeBus:
    class _Signal:
        def emit(self, *args):
            pass

    status_message = _Signal()


def _character():
    return Character(id="t", display_name="T", wake_word="hey",
                     personality_prompt="Be nice.")


def test_question_produces_a_spoken_answer():
    router = IntentRouter(_FakeLLM("question"), _FakeSearch(), _FakeBus())
    result = router.handle("how tall is everest", _character())
    assert result.speak == "It is 8,849 metres tall."
    assert result.display == result.speak


def test_chitchat_produces_a_spoken_reply():
    router = IntentRouter(_FakeLLM("chitchat"), _FakeSearch(), _FakeBus())
    result = router.handle("hello there", _character())
    assert result.speak == "Hehe, hello to you too!"
