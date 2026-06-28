"""Data-access helpers for leads — the dialer's source of work."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.base import LeadStatus
from ..db.models import Lead


class LeadRepository:
    def __init__(self, session: Session):
        self.session = session

    def dialable(self, campaign_id: int, limit: int = 50) -> list[Lead]:
        """Leads that are candidates to dial right now (cheap pre-filter).

        The authoritative go/no-go is the ComplianceEngine; this just narrows
        the set so we don't evaluate the whole table every tick. Ordered so the
        freshest never-tried leads go first, then due retries.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(Lead)
            .where(
                Lead.campaign_id == campaign_id,
                Lead.do_not_call.is_(False),
                Lead.status.in_([LeadStatus.NEW, LeadStatus.QUEUED, LeadStatus.CALLBACK, LeadStatus.FAILED]),
                (Lead.next_eligible_at.is_(None)) | (Lead.next_eligible_at <= now),
            )
            .order_by(Lead.attempts.asc(), Lead.next_eligible_at.asc().nullsfirst())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def counts_by_status(self, campaign_id: int) -> dict[str, int]:
        stmt = (
            select(Lead.status, func.count())
            .where(Lead.campaign_id == campaign_id)
            .group_by(Lead.status)
        )
        return {status.value: n for status, n in self.session.execute(stmt)}

    def mark_calling(self, lead: Lead) -> None:
        lead.status = LeadStatus.CALLING
        lead.attempts += 1
        lead.last_attempt_at = datetime.now(timezone.utc)

    def defer(self, lead: Lead, until: datetime | None) -> None:
        """Put a lead back in the queue, eligible again at ``until``."""
        lead.next_eligible_at = until
        if lead.status == LeadStatus.CALLING:
            lead.status = LeadStatus.QUEUED
