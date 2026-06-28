"""Decide who to dial next, honoring compliance and concurrency.

This is pure-ish planning logic (no I/O beyond reads), which makes it easy to
test: given the current state, return a DialPlan of leads cleared to call and a
list of deferrals (lead -> next eligible time) for ones blocked by time windows
or retry spacing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..compliance import ComplianceEngine
from ..config import settings
from ..db.models import Lead
from ..leads.repository import LeadRepository
from ..logging import get_logger

log = get_logger("coldy.dialer.scheduler")


@dataclass
class DialPlan:
    to_dial: list[Lead] = field(default_factory=list)
    # (lead, next_eligible_utc_or_None, reason)
    deferred: list[tuple[Lead, datetime | None, str]] = field(default_factory=list)
    blocked: list[tuple[Lead, str]] = field(default_factory=list)  # hard-blocked (DNC etc.)


def plan_next_dials(
    session: Session,
    campaign_id: int,
    *,
    free_slots: int,
    now_utc: datetime | None = None,
) -> DialPlan:
    """Return up to ``free_slots`` leads cleared to call right now."""
    now_utc = now_utc or datetime.now(timezone.utc)
    repo = LeadRepository(session)
    engine = ComplianceEngine(session)
    plan = DialPlan()

    if free_slots <= 0:
        return plan

    # Pull a generous candidate window; compliance will thin it.
    candidates = repo.dialable(campaign_id, limit=free_slots * 5)
    for lead in candidates:
        if len(plan.to_dial) >= free_slots:
            break
        decision = engine.evaluate(lead, now_utc=now_utc)
        if decision.allowed:
            plan.to_dial.append(lead)
        elif decision.retry_after_utc is not None:
            plan.deferred.append((lead, decision.retry_after_utc, "; ".join(decision.reasons)))
        else:
            plan.blocked.append((lead, "; ".join(decision.reasons)))

    if plan.to_dial or plan.deferred or plan.blocked:
        log.debug(
            "Plan for campaign %s: dial=%d defer=%d block=%d",
            campaign_id, len(plan.to_dial), len(plan.deferred), len(plan.blocked),
        )
    return plan
