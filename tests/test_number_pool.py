from datetime import datetime, timezone

from coldy.db.base import CallStatus
from coldy.db.models import Call
from coldy.telephony.number_pool import NumberPool

POOL = ["+16125550100", "+14155550100", "+13055550100"]  # MN, CA, FL


class _EmptySession:
    """Stand-in session whose usage query returns nothing (no DB needed)."""

    def execute(self, *args, **kwargs):
        class _R:
            def all(self_inner):
                return []

        return _R()


def test_local_presence_matches_area_code():
    pool = NumberPool(POOL)
    # A Minneapolis (612) lead should be called from the 612 number.
    assert pool.pick(_EmptySession(), "+16125559999") == "+16125550100"


def test_falls_back_when_no_local_match():
    pool = NumberPool(POOL)
    # A 718 (NY) lead has no area-code/state match -> still returns a pool number.
    assert pool.pick(_EmptySession(), "+17185551234") in POOL


def test_respects_daily_cap_and_spreads(session):
    from coldy.config import settings

    settings.per_number_daily_cap = 2
    now = datetime.now(timezone.utc)
    for _ in range(2):
        session.add(
            Call(
                lead_id=1, to_number="+16125550001", from_number="+16125550100",
                status=CallStatus.COMPLETED, started_at=now,
            )
        )
    session.flush()
    try:
        pool = NumberPool(POOL)
        # 612 number is maxed -> a 612 lead must spread to another number.
        assert pool.pick(session, "+16125559999") != "+16125550100"
    finally:
        settings.per_number_daily_cap = 200
