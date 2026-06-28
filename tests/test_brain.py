from coldy.config import settings
from coldy.voice.brain import is_hard_turn, model_for_turn


def test_hard_turns_detected():
    for text in [
        "So how much does this cost?",
        "Honestly I'm not interested.",
        "Wait, are you a robot?",
        "We already have a marketing guy.",
        "What makes you different from the others?",
        "Take me off your list.",
    ]:
        assert is_hard_turn(text), text


def test_easy_turns_not_flagged():
    for text in ["Yeah, sounds good.", "Sure, tell me more.", "Okay.", "Morning!"]:
        assert not is_hard_turn(text), text


def test_model_routing_escalates_on_hard_turns():
    assert model_for_turn("how much is it?") == settings.llm_escalation_model
    assert model_for_turn("yeah go on") == settings.llm_model
