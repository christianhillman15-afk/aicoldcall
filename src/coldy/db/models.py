"""ORM models.

The lead lifecycle is the spine of the dialer:

    NEW -> QUEUED -> CALLING -> (INTERESTED | CALLBACK | NOT_INTERESTED |
                                 DNC | FAILED -> QUEUED | EXHAUSTED)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base,
    CallOutcome,
    CallStatus,
    CampaignStatus,
    ConsentType,
    LeadStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT
    )
    # Per-campaign overrides (fall back to global settings when None).
    goal: Mapped[str] = mapped_column(
        Text, default="Qualify the business and book a 15-minute discovery call."
    )
    requires_written_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("campaign_id", "phone", name="uq_campaign_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    # Identity
    phone: Mapped[str] = mapped_column(String(20), index=True)  # E.164, e.g. +16125550100
    business_name: Mapped[str | None] = mapped_column(String(200))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2))   # USPS 2-letter
    timezone: Mapped[str | None] = mapped_column(String(40))  # IANA, e.g. America/Chicago
    is_mobile: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)

    # State machine
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus), default=LeadStatus.NEW, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    do_not_call: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="leads")
    calls: Mapped[list["Call"]] = relationship(back_populates="lead")
    consents: Mapped[list["ConsentRecord"]] = relationship(back_populates="lead")


class ConsentRecord(Base):
    """Evidence of consent to receive AI/automated calls.

    The compliance engine treats EXPRESS_WRITTEN as the only sufficient basis
    for AI-voice telemarketing (per the FCC's 2024 TCPA ruling). Store the
    source (web form, contract clause, etc.) so consent is auditable.
    """

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    consent_type: Mapped[ConsentType] = mapped_column(Enum(ConsentType))
    source: Mapped[str] = mapped_column(String(300))  # how/where consent was captured
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    evidence_url: Mapped[str | None] = mapped_column(String(500))

    lead: Mapped["Lead"] = relationship(back_populates="consents")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    provider_call_sid: Mapped[str | None] = mapped_column(String(64), index=True)
    from_number: Mapped[str | None] = mapped_column(String(20))
    to_number: Mapped[str] = mapped_column(String(20))

    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus), default=CallStatus.INITIATED
    )
    outcome: Mapped[CallOutcome] = mapped_column(
        Enum(CallOutcome), default=CallOutcome.UNKNOWN
    )

    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    recorded: Mapped[bool] = mapped_column(Boolean, default=False)
    recording_url: Mapped[str | None] = mapped_column(String(500))
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)

    lead: Mapped["Lead"] = relationship(back_populates="calls")


class DNCEntry(Base):
    """Internal (company-specific) do-not-call list.

    A number here is suppressed across ALL campaigns. This is separate from the
    federal National DNC Registry, which must be scrubbed against via a
    licensed provider (see compliance/dnc.py).
    """

    __tablename__ = "dnc_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(120), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
