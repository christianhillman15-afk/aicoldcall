"""Campaign lifecycle + reporting."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.base import CallOutcome, CallStatus, CampaignStatus
from ..db.models import Call, Campaign, Lead
from ..leads.repository import LeadRepository

# Outcomes that mean a human actually engaged in a conversation.
_CONVERSATION_OUTCOMES = {
    CallOutcome.INTERESTED.value,
    CallOutcome.MEETING_BOOKED.value,
    CallOutcome.CALLBACK.value,
    CallOutcome.NOT_INTERESTED.value,
    CallOutcome.OPTED_OUT.value,
    CallOutcome.TRANSFERRED.value,
}


class CampaignService:
    def __init__(self, session: Session):
        self.session = session

    def get(self, name: str) -> Campaign | None:
        return self.session.execute(
            select(Campaign).where(Campaign.name == name)
        ).scalar_one_or_none()

    def list_campaigns(self) -> list[dict]:
        rows = self.session.execute(
            select(Campaign).order_by(Campaign.created_at.desc())
        ).scalars()
        return [{"name": c.name, "status": c.status.value} for c in rows]

    def recent_calls(self, campaign_id: int, limit: int = 25) -> list[dict]:
        stmt = (
            select(Call, Lead)
            .join(Lead, Call.lead_id == Lead.id)
            .where(Call.campaign_id == campaign_id)
            .order_by(Call.started_at.desc())
            .limit(limit)
        )
        out = []
        for call, lead in self.session.execute(stmt):
            out.append(
                {
                    "phone": call.to_number,
                    "business": lead.business_name,
                    "direction": call.direction,
                    "status": call.status.value,
                    "outcome": call.outcome.value,
                    "opener": call.opener_id,
                    "score": call.interest_score,
                    "duration": call.duration_seconds,
                    "started_at": call.started_at.isoformat() if call.started_at else None,
                }
            )
        return out

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

        # --- Funnel: dials -> connected -> conversations -> meetings ---
        dials = self.session.execute(
            select(func.count()).select_from(Call).where(Call.campaign_id == camp.id)
        ).scalar_one()
        connected = self.session.execute(
            select(func.count())
            .select_from(Call)
            .where(
                Call.campaign_id == camp.id,
                Call.status.in_(
                    [CallStatus.IN_PROGRESS, CallStatus.COMPLETED, CallStatus.VOICEMAIL]
                ),
            )
        ).scalar_one()
        conversations = sum(outcomes.get(o, 0) for o in _CONVERSATION_OUTCOMES)

        def _rate(num: int, den: int) -> float:
            return round(100 * num / den, 1) if den else 0.0

        funnel = {
            "dials": dials,
            "connected": connected,
            "conversations": conversations,
            "meetings": meetings,
            "connect_rate_pct": _rate(connected, dials),
            "conversation_rate_pct": _rate(conversations, connected),
            "meeting_rate_pct": _rate(meetings, conversations),
        }

        # --- Per-opener A/B: which opener books the most meetings? ---
        by_opener: dict[str, dict] = {}
        rows = self.session.execute(
            select(Call.opener_id, Call.outcome).where(Call.campaign_id == camp.id)
        ).all()
        for opener_id, outcome in rows:
            oid = opener_id or "unknown"
            d = by_opener.setdefault(oid, {"calls": 0, "meetings": 0})
            d["calls"] += 1
            if outcome == CallOutcome.MEETING_BOOKED:
                d["meetings"] += 1
        for d in by_opener.values():
            d["meeting_rate_pct"] = _rate(d["meetings"], d["calls"])

        return {
            "campaign": camp.name,
            "status": camp.status.value,
            "total_leads": total_leads,
            "leads_by_status": leads,
            "call_outcomes": outcomes,
            "meetings_booked": meetings,
            "funnel": funnel,
            "by_opener": by_opener,
        }
