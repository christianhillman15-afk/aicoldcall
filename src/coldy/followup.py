"""Multi-touch follow-up: turn one call into a sequence.

After a call ends we optionally send an SMS — a booking link to interested
leads, a soft nudge after a miss. SMS is TCPA-regulated too, so it is gated on
the same prior express written consent the call required, and every message
carries an opt-out.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db.base import CallOutcome, ConsentType
from .db.models import Call, ConsentRecord, Lead
from .logging import get_logger

log = get_logger("coldy.followup")


def has_written_consent(session: Session, lead: Lead) -> bool:
    stmt = select(ConsentRecord).where(
        ConsentRecord.lead_id == lead.id,
        ConsentRecord.consent_type == ConsentType.EXPRESS_WRITTEN,
        ConsentRecord.revoked_at.is_(None),
    )
    return session.execute(stmt).first() is not None


def sms_body(outcome: CallOutcome, lead: Lead) -> str | None:
    company = settings.company_name
    if outcome in (CallOutcome.MEETING_BOOKED, CallOutcome.INTERESTED):
        if settings.booking_link:
            return (
                f"Thanks for chatting with {company}! Grab a time that works here: "
                f"{settings.booking_link}  (Reply STOP to opt out.)"
            )
        return (
            f"Thanks for chatting with {company}! We'll follow up shortly to lock "
            f"in a time. (Reply STOP to opt out.)"
        )
    if outcome in (CallOutcome.NO_ANSWER, CallOutcome.VOICEMAIL):
        return (
            f"Hi, it's {company} — sorry we missed you. We help local businesses "
            f"{settings.value_prop_short}. Want a quick chat? (Reply STOP to opt out.)"
        )
    return None


def send_followup(telephony, session: Session, call: Call) -> bool:
    """Send the appropriate SMS for a finished call. Returns True if sent."""
    if not settings.sms_enabled:
        return False
    lead = session.get(Lead, call.lead_id)
    if lead is None or lead.do_not_call:
        return False
    if not has_written_consent(session, lead):
        log.info("Skipping SMS to %s — no written consent on file", lead.phone)
        return False
    body = sms_body(call.outcome, lead)
    if not body:
        return False
    return bool(telephony.send_sms(lead.phone, body))
