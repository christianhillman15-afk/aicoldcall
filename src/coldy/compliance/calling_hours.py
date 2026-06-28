"""TCPA calling-window enforcement.

Federal TCPA telemarketing rules restrict calls to 8:00am–9:00pm in the
*called party's* local time. We default to a slightly tighter 9:00–20:00
window (configurable) to stay clear of the edges and to respect stricter
state windows. When a lead's timezone is unknown we refuse to call (fail
closed) rather than risk an out-of-window call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import settings


def local_now(tz_name: str | None, now_utc: datetime | None = None) -> datetime | None:
    if not tz_name:
        return None
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        return now_utc.astimezone(ZoneInfo(tz_name))
    except (ZoneInfoNotFoundError, ValueError):
        return None


def within_calling_window(
    tz_name: str | None, now_utc: datetime | None = None
) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    local = local_now(tz_name, now_utc)
    if local is None:
        return False, "unknown timezone (failing closed to avoid out-of-window calls)"

    start = settings.call_window_start_hour
    end = settings.call_window_end_hour
    hour = local.hour
    if start <= hour < end:
        return True, f"local time {local.strftime('%H:%M %Z')} is within {start}:00-{end}:00"
    return (
        False,
        f"local time {local.strftime('%H:%M %Z')} is outside the {start}:00-{end}:00 window",
    )


def next_window_open_utc(tz_name: str | None, now_utc: datetime | None = None) -> datetime | None:
    """The next UTC instant the calling window opens for this lead."""
    from datetime import timedelta

    local = local_now(tz_name, now_utc)
    if local is None:
        return None
    start = settings.call_window_start_hour
    candidate = local.replace(hour=start, minute=0, second=0, microsecond=0)
    if local.hour >= settings.call_window_end_hour:
        candidate = candidate + timedelta(days=1)
    elif local.hour >= start:
        # already inside the window; "next open" is now
        return local.astimezone(timezone.utc)
    return candidate.astimezone(timezone.utc)
