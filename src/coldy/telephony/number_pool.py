"""Local-presence caller-ID selection.

People answer local numbers far more than unfamiliar/long-distance ones. Given a
lead, pick a from-number that (1) is under its daily cap (protects number
reputation), then (2) matches the lead's area code, then its state, then falls
back to the least-used number in the pool.

This is the *software* half of deliverability. The other half is operational —
register your numbers for STIR/SHAKEN attestation and branded caller ID with
your carrier (see docs/DELIVERABILITY.md) so they aren't flagged "Spam Likely."
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..compliance.geo import area_code, state_for_number
from ..config import settings
from ..db.models import Call
from ..logging import get_logger

log = get_logger("coldy.telephony.pool")


class NumberPool:
    def __init__(self, numbers: list[str] | None = None):
        self.numbers = numbers if numbers is not None else settings.from_number_pool

    def usage_today(self, session: Session) -> dict[str, int]:
        """Calls placed from each pool number since local midnight (UTC)."""
        if not self.numbers:
            return {}
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = session.execute(
            select(Call.from_number, func.count())
            .where(Call.from_number.in_(self.numbers), Call.started_at >= start)
            .group_by(Call.from_number)
        ).all()
        return {fn: n for fn, n in rows}

    def pick(self, session: Session, to_number: str) -> str | None:
        """Choose the best from-number for this destination."""
        if not self.numbers:
            return None
        usage = self.usage_today(session)
        cap = settings.per_number_daily_cap

        # Prefer numbers under their daily cap; if all are maxed, use the full set.
        available = [n for n in self.numbers if usage.get(n, 0) < cap] or list(self.numbers)

        lead_ac = area_code(to_number)
        lead_state = state_for_number(to_number)

        tier = [n for n in available if lead_ac and area_code(n) == lead_ac]
        if not tier and lead_state:
            tier = [n for n in available if state_for_number(n) == lead_state]
        if not tier:
            tier = available

        # Least-used within the chosen tier (spread load / reputation).
        return min(tier, key=lambda n: usage.get(n, 0))
