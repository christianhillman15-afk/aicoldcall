from datetime import datetime, timezone

from fastapi.testclient import TestClient

from coldy.api.app import app
from coldy.db.session import init_db, session_scope

client = TestClient(app)

IN_WINDOW = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)  # 10:00 CDT


def setup_module(_module):
    init_db()


def test_landing_page_renders_with_consent_and_no_numbers():
    r = client.get("/optin")
    assert r.status_code == 200
    body = r.text.lower()
    assert "consent" in body
    assert "<form" in body and 'name="phone"' in r.text
    # The page is a blank form — it must not contain any phone numbers.
    assert "+1" not in r.text


def test_optin_requires_consent():
    r = client.post("/api/optin", json={"phone": "+16125557001", "consent": False})
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_optin_creates_consented_callable_lead():
    r = client.post(
        "/api/optin",
        json={
            "phone": "+16125557002", "consent": True,
            "contact_name": "Dan", "business_name": "North Star Painting",
            "industry": "painting", "src": "fb_ad_test",
        },
    )
    assert r.status_code == 200
    lead_id = r.json()["lead_id"]
    assert lead_id

    from coldy.compliance import ComplianceEngine
    from coldy.db.models import Lead

    with session_scope() as s:
        lead = s.get(Lead, lead_id)
        assert lead.status.value == "queued"
        # Written consent recorded with the exact language + evidence.
        consents = lead.consents
        assert any(c.consent_type.value == "express_written" for c in consents)
        assert consents[0].consent_text and "automated" in consents[0].consent_text.lower()
        # And it now passes the compliance gate inside the calling window.
        assert ComplianceEngine(s).evaluate(lead, now_utc=IN_WINDOW).allowed


def test_optin_form_submit_thanks():
    r = client.post(
        "/optin",
        data={"phone": "+16125557003", "consent": "on", "contact_name": "Maria"},
    )
    assert r.status_code == 200
    assert "✅" in r.text or "set" in r.text.lower()


def test_optin_form_without_consent_reprompts():
    r = client.post("/optin", data={"phone": "+16125557004"})  # no consent box
    assert r.status_code == 200
    assert "consent" in r.text.lower()
