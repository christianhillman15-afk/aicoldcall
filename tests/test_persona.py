from coldy.config import settings
from coldy.voice.persona import (
    CallContext,
    build_inbound_opening,
    build_opening_line,
    build_system_prompt,
)


def test_opening_discloses_ai_and_company():
    # Openers come from the research-backed library; each must disclose the AI
    # nature and company (compliance by construction) and end with a permission
    # question. They intentionally ask ONE question (no business-name echo).
    line = build_opening_line(CallContext(business_name="Acme Plumbing"), seed=1)
    assert "AI assistant" in line
    assert settings.company_name in line
    assert line.rstrip().endswith("?")


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


def test_inbound_opening_is_a_warm_greeting():
    line = build_inbound_opening(CallContext(inbound=True))
    assert "AI assistant" in line
    assert settings.company_name in line
    assert "Thanks for calling" in line


def test_system_prompt_switches_inbound_vs_outbound():
    assert "INBOUND CALL" in build_system_prompt(CallContext(inbound=True))
    assert "OUTBOUND CALL" in build_system_prompt(CallContext(inbound=False))
