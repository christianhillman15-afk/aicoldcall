from datetime import datetime, timezone

from coldy.compliance import calling_hours


def _utc(y, m, d, h):
    return datetime(y, m, d, h, 0, tzinfo=timezone.utc)


def test_within_window_midday_chicago():
    # 15:00 UTC in June = 10:00 CDT -> inside the default 9-20 window.
    allowed, _ = calling_hours.within_calling_window(
        "America/Chicago", _utc(2026, 6, 15, 15)
    )
    assert allowed is True


def test_outside_window_late_night_chicago():
    # 04:00 UTC in June = 23:00 CDT previous day -> outside the window.
    allowed, reason = calling_hours.within_calling_window(
        "America/Chicago", _utc(2026, 6, 15, 4)
    )
    assert allowed is False
    assert "outside" in reason


def test_unknown_timezone_fails_closed():
    allowed, reason = calling_hours.within_calling_window(None, _utc(2026, 6, 15, 15))
    assert allowed is False
    assert "unknown timezone" in reason


def test_next_window_open_is_future_when_blocked():
    nxt = calling_hours.next_window_open_utc("America/Chicago", _utc(2026, 6, 15, 4))
    assert nxt is not None
    assert nxt > _utc(2026, 6, 15, 4)
