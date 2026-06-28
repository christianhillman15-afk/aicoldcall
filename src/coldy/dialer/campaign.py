"""Campaign lifecycle + reporting."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.base import CallOutcome, CampaignStatus
from ..db.models import Call, Campaign, Lead
from ..leads.repository import LeadRepository


class CampaignService:
    def __init__(self, session: Session):
        self.session = session

    def get(self, name: str) -> Campaign | None:
        return self.session.execute(
            select(Campaign).where(Campaign.name == name)
        ).scalar_one_or_none()

    def create(self, name: str, goal: str | None = None) -> Campaign:
        camp = Campaign(name=name)
        if goal:
            camp.goal = goal
        self.session.add(camp)
        self.session.flush()
        return camp

    def set_status(self, name: str, status: CampaignStatus) -> Campaign | None:
        camp = self.get(name)
        if camp:
            camp.status = status
        return camp

    def report(self, name: str) -> dict:
        camp = self.get(name)
        if camp is None:
            return {}
        leads = LeadRepository(self.session).counts_by_status(camp.id)
        outcomes_stmt = (
            select(Call.outcome, func.count())
            .where(Call.campaign_id == camp.id)
            .group_by(Call.outcome)
        )
        outcomes = {o.value: n for o, n in self.session.execute(outcomes_stmt)}
        total_leads = self.session.execute(
            select(func.count()).select_from(Lead).where(Lead.campaign_id == camp.id)
        ).scalar_one()
        meetings = outcomes.get(CallOutcome.MEETING_BOOKED.value, 0)
        return {
            "campaign": camp.name,
            "status": camp.status.value,
            "total_leads": total_leads,
            "leads_by_status": leads,
            "call_outcomes": outcomes,
            "meetings_booked": meetings,
        }
