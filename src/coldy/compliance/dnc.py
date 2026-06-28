"""Do-not-call suppression.

Two layers:
  1. Internal / company-specific DNC list (the ``dnc_entries`` table + the
     per-lead ``do_not_call`` flag). Honored immediately and forever.
  2. The federal National DNC Registry. You MUST scrub against it via a
     licensed access provider — Coldy exposes a hook (``federal_dnc_listed``)
     that defaults to "unknown" so you cannot accidentally believe a number is
     clean. Wire in your provider in ``set_federal_dnc_checker``.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import DNCEntry, Lead

# Optional injected checker: phone (E.164) -> True (listed) / False (clear) / None (unknown).
_federal_checker: Callable[[str], bool | None] | None = None


def set_federal_dnc_checker(fn: Callable[[str], bool | None]) -> None:
    """Register a federal National DNC Registry lookup (from a licensed provider)."""
    global _federal_checker
    _federal_checker = fn


def federal_dnc_listed(phone: str) -> bool | None:
    if _federal_checker is None:
        return None  # unknown — caller must decide how strict to be
    return _federal_checker(phone)


def is_internally_suppressed(session: Session, phone: str) -> bool:
    """True if the number is on our internal DNC list."""
    stmt = select(DNCEntry).where(DNCEntry.phone == phone)
    return session.execute(stmt).scalar_one_or_none() is not None


def add_to_dnc(
    session: Session, phone: str, reason: str = "", source: str = "manual"
) -> DNCEntry:
    """Idempotently add a number to the internal DNC list and flag matching leads."""
    existing = session.execute(
        select(DNCEntry).where(DNCEntry.phone == phone)
    ).scalar_one_or_none()
    if existing is None:
        existing = DNCEntry(phone=phone, reason=reason or None, source=source)
        session.add(existing)

    # Flag any leads with this number across all campaigns.
    for lead in session.execute(select(Lead).where(Lead.phone == phone)).scalars():
        lead.do_not_call = True
        from ..db.base import LeadStatus

        lead.status = LeadStatus.DNC
    return existing
