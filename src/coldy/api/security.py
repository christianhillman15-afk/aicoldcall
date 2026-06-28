"""Production security: Twilio webhook signature validation, dashboard auth,
opt-in API token, and media-stream token. All degrade to "open with a warning"
when their credential isn't configured, so dev stays frictionless — but set them
before going live (see docs/DEPLOY.md).
"""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..config import settings
from ..logging import get_logger

log = get_logger("coldy.api.security")
_basic = HTTPBasic(auto_error=False)


async def verify_twilio_signature(request: Request) -> None:
    """Reject webhook calls not signed by Twilio (prevents spoofed call events)."""
    if not settings.twilio_validate_signatures:
        return
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not token:
        log.warning("TWILIO_AUTH_TOKEN unset — skipping Twilio signature validation")
        return
    from twilio.request_validator import RequestValidator

    signature = request.headers.get("X-Twilio-Signature", "")
    # Twilio signs the PUBLIC url it requested (path + query), not the internal one.
    url = settings.public_base_url.rstrip("/") + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    try:
        form = await request.form()  # Starlette caches this; the route re-reads it fine
        params = dict(form)
    except Exception:  # noqa: BLE001
        params = {}
    if not RequestValidator(token).validate(url, params, signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bad Twilio signature")


def require_dashboard_auth(
    creds: HTTPBasicCredentials | None = Depends(_basic),
) -> None:
    """HTTP Basic auth for the dashboard + its JSON APIs."""
    user, pw = settings.dashboard_user, settings.dashboard_password
    if not user or not pw:
        log.warning("Dashboard auth not configured — /dashboard is OPEN. Set "
                    "COLDY_DASHBOARD_USER / COLDY_DASHBOARD_PASSWORD before going live.")
        return
    ok = bool(creds) and (
        secrets.compare_digest(creds.username, user)
        and secrets.compare_digest(creds.password, pw)
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth required",
            headers={"WWW-Authenticate": "Basic"},
        )


def verify_optin_token(request: Request) -> None:
    """Optional shared secret on the JSON opt-in intake (stops fake opt-ins)."""
    tok = settings.optin_api_token
    if not tok:
        return
    if request.headers.get("X-Coldy-Token") != tok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bad token")


def media_token_ok(token: str | None) -> bool:
    """Validate the token carried in the media-stream URL (if configured)."""
    if not settings.media_token:
        return True
    return token == settings.media_token
