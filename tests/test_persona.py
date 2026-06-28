from coldy.config import settings
from coldy.voice.persona import CallContext, build_opening_line, build_system_prompt


def test_opening_discloses_ai_and_company():
    line = build_opening_line(CallContext(business_name="Acme Plumbing"))
    assert "AI assistant" in line
    assert settings.company_name in line
    assert "Acme Plumbing" in line


def test_system_prompt_has_spoken_rules_and_product():
    prompt = build_system_prompt(
        CallContext(business_name="Acme", industry="plumbing", city="Minneapolis", state="MN")
    )
    assert settings.product_name in prompt
    # spoken-style guardrails present
    assert "ONE question at a time" in prompt
    assert "Never use lists" in prompt
    # opt-out behavior is mandated
    assert "do_not_call" in prompt
