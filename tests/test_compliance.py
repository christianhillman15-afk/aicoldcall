from datetime import datetime, timezone

from coldy.compliance import ComplianceEngine
from coldy.compliance.dnc import add_to_dnc
from coldy.db.base import ConsentType, LeadStatus
from coldy.db.models import ConsentRecord, Lead

IN_WINDOW = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)  # 10:00 CDT


def _lead(session, **kw) -> Lead:
    defaults = dict(
        phone="+16125550100",
        timezone="America/Chicago",
        status=LeadStatus.NEW,
        attempts=0,
    )
    defaults.update(kw)
    lead = Lead(**defaults)
    session.add(lead)
    session.flush()
    return lead


def test_blocked_without_written_consent(session):
    lead = _lead(session)
    decision = ComplianceEngine(session).evaluate(lead, now_utc=IN_WINDOW)
    assert decision.allowed is False
    assert any("consent" in r for r in decision.reasons)


def test_allowed_with_written_consent_in_window(session):
    lead = _lead(session)
    session.add(
        ConsentRecord(
            lead_id=lead.id,
            consent_type=ConsentType.EXPRESS_WRITTEN,
            source="web form",
        )
    )
    session.flush()
    decision = ComplianceEngine(session).evaluate(lead, now_utc=IN_WINDOW)
    assert decision.allowed is True, decision.reasons


def test_dnc_flag_blocks(session):
    lead = _lead(session, do_not_call=True)
    session.add(
        ConsentRecord(lead_id=lead.id, consent_type=ConsentType.EXPRESS_WRITTEN, source="x")
    )
    session.flush()
    decision = ComplianceEngine(session).evaluate(lead, now_utc=IN_WINDOW)
    assert decision.allowed is False
    assert any("do-not-call" in r for r in decision.reasons)


def test_internal_dnc_list_blocks(session):
    lead = _lead(session)
    session.add(
        ConsentRecord(lead_id=lead.id, consent_type=ConsentType.EXPRESS_WRITTEN, source="x")
    )
    add_to_dnc(session, lead.phone, reason="test")
    session.flush()
    session.refresh(lead)
    decision = ComplianceEngine(session).evaluate(lead, now_utc=IN_WINDOW)
    assert decision.allowed is False


def test_blocked_outside_calling_window(session):
    lead = _lead(session)
    session.add(
        ConsentRecord(lead_id=lead.id, consent_type=ConsentType.EXPRESS_WRITTEN, source="x")
    )
    session.flush()
    late = datetime(2026, 6, 15, 4, 0, tzinfo=timezone.utc)  # 23:00 CDT prev day
    decision = ComplianceEngine(session).evaluate(lead, now_utc=late)
    assert decision.allowed is False
    assert decision.retry_after_utc is not None
