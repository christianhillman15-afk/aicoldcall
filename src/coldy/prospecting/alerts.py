"""Send flagged prospects to you. Posts to COLDY_ALERT_WEBHOOK_URL (Slack-style
``{"text": ...}`` works out of the box); logs them if no webhook is set."""

from __future__ import annotations

import httpx

from ..config import settings
from ..logging import get_logger

log = get_logger("coldy.prospecting.alerts")


def format_flagged(prospects: list[dict]) -> str:
    lines = [f"🔥 {len(prospects)} new flagged prospect(s) for Oxsome:"]
    for p in prospects[:25]:
        where = ", ".join(filter(None, [p.get("city"), p.get("state")]))
        no_site = " · no website" if not p.get("has_website") else ""
        lines.append(
            f"• {p['business_name']} ({where}) — fit {p['fit']}"
            f" [need {p['need']}/afford {p['afford']}] — {p.get('phone') or 'no phone'}{no_site}"
        )
    return "\n".join(lines)


def send_flagged(prospects: list[dict]) -> bool:
    if not prospects:
        return False
    text = format_flagged(prospects)
    url = settings.alert_webhook_url
    if not url:
        log.info("Flagged prospects (set COLDY_ALERT_WEBHOOK_URL to get pinged):\n%s", text)
        return False
    try:
        httpx.post(url, json={"text": text}, timeout=10).raise_for_status()
        return True
    except httpx.HTTPError as e:
        log.error("Alert webhook failed: %s", e)
        return False
