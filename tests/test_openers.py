import pytest

from coldy.config import settings
from coldy.voice import openers
from coldy.voice.persona import CallContext

CTX = CallContext(business_name="Acme Painting", industry="painting", city="Minneapolis", state="MN")


@pytest.mark.parametrize("opener", openers.OPENERS, ids=[o.id for o in openers.OPENERS])
def test_every_opener_is_compliant_and_complete(opener):
    rendered = openers.render(opener, CTX)
    # Compliance by construction: AI disclosure + company name always present.
    assert "AI assistant" in rendered
    assert settings.company_name in rendered
    # No unfilled template placeholders left behind.
    assert "{" not in rendered and "}" not in rendered
    # Openers end by handing control to the prospect (a question).
    assert rendered.rstrip().endswith("?")


def test_industry_plural_known_and_fallback():
    assert openers.industry_plural("painting") == "painting companies"
    assert openers.industry_plural("hvac") == "HVAC companies"
    assert openers.industry_plural(None) == "local service businesses"
    assert openers.industry_plural("dog grooming") == "dog grooming businesses"


def test_choose_specific_id():
    o = openers.choose(CTX, style="social_proof_local")
    assert o.id == "social_proof_local"


def test_choose_rotate_is_deterministic_with_seed():
    a = openers.choose(CTX, style="rotate", seed=42)
    b = openers.choose(CTX, style="rotate", seed=42)
    assert a.id == b.id


def test_unknown_style_falls_back_to_a_real_opener():
    o = openers.choose(CTX, style="does_not_exist", seed=1)
    assert o in openers.OPENERS
