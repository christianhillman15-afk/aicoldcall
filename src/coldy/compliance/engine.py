"""The single compliance gate. The dialer calls ``evaluate(lead)`` before every
dial and must honor the returned decision.

A call is ALLOWED only when every check passes:
  - not internally suppressed / flagged DNC
  - not on the federal DNC registry (when a checker is configured)
  - valid prior express WRITTEN consent on file (when required)
  - current time is inside the lead's local calling window
  - attempt cap / retry interval respected
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..db.base import ConsentType, LeadStatus
from ..db.models import Lead
from . import calling_hours, dnc, recording


@dataclass
class ComplianceDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    # When allowed, these shape how the call is conducted:
    requires_recording_notice: bool = True
    recording_allowed: bool = False
    # When blocked, when (UTC) the lead might next be eligible (None = never/manual).
    retry_after_utc: datetime | None = None

    def block(self, reason: str) -> "ComplianceDecision":
        self.allowed = False
        self.reasons.append(reason)
        return self


class ComplianceEngine:
    def __init__(self, session: Session):
        self.session = session

    def _has_written_consent(self, lead: Lead) -> bool:
        for c in lead.consents:
            if c.consent_type == ConsentType.EXPRESS_WRITTEN and c.is_active:
                return True
        return False

    def evaluate(self, lead: Lead, now_utc: datetime | None = None) -> ComplianceDecision:
        now_utc = now_utc or datetime.now(timezone.utc)
        decision = ComplianceDecision(allowed=True)

        # 1) Hard DNC checks ------------------------------------------------
        if lead.do_not_call or lead.status == LeadStatus.DNC:
            return decision.block("lead is flagged do-not-call")

        if dnc.is_internally_suppressed(self.session, lead.phone):
            return decision.block("number is on the internal DNC list")

        federal = dnc.federal_dnc_listed(lead.phone)
        if federal is True:
            return decision.block("number is on the federal National DNC Registry")
        # federal is None -> no checker configured; we proceed but the operator
        # is responsible for registry scrubbing (see docs/COMPLIANCE.md).

        # 2) Consent (the TCPA-critical gate for AI/artificial voice) -------
        require_consent = settings.require_written_consent
        if lead.campaign is not None:
            require_consent = require_consent and lead.campaign.requires_written_consent
        if require_consent and not self._has_written_consent(lead):
            return decision.block(
                "no prior express WRITTEN consent on file (required for AI "
                "telemarketing under the FCC's 2024 TCPA ruling)"
            )

        # 3) Calling-hours window ------------------------------------------
        in_window, why = calling_hours.within_calling_window(lead.timezone, now_utc)
        if not in_window:
            decision.retry_after_utc = calling_hours.next_window_open_utc(
                lead.timezone, now_utc
            )
            return decision.block(why)

        # 4) Attempt cap + retry spacing -----------------------------------
        if lead.attempts >= settings.max_attempts:
            return decision.block(f"max attempts ({settings.max_attempts}) reached")

        if lead.last_attempt_at is not None:
            last = lead.last_attempt_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            earliest = last + timedelta(hours=settings.retry_interval_hours)
            if now_utc < earliest:
                decision.retry_after_utc = earliest
                return decision.block(
                    f"retry interval not elapsed (next eligible {earliest.isoformat()})"
                )

        # 5) Recording posture (does not block; shapes the call) -----------
        if settings.record_calls:
            from .geo import state_for_number

            state = lead.state or state_for_number(lead.phone)
            decision.requires_recording_notice = recording.requires_all_party_consent(state)
            decision.recording_allowed = True
        else:
            decision.recording_allowed = False
            decision.requires_recording_notice = False

        return decision
