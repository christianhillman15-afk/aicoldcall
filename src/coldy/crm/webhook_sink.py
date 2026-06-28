"""Generic outbound webhook CRM sink.

POSTs the outcome as JSON to ``COLDY_CRM_WEBHOOK_URL``. If a secret is set, it
adds an HMAC-SHA256 signature header (``X-Coldy-Signature``) so the receiver can
verify authenticity.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx

from ..config import settings
from ..logging import get_logger
from .base import CallOutcomePayload

log = get_logger("coldy.crm.webhook")


class WebhookCRMSink:
    def __init__(self, url: str | None = None, secret: str | None = None):
        self.url = url if url is not None else settings.crm_webhook_url
        self.secret = secret if secret is not None else settings.crm_webhook_secret

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def _sign(self, body: bytes) -> str:
        return hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()

    def send(self, payload: CallOutcomePayload) -> bool:
        if not self.enabled:
            log.debug("CRM webhook not configured; skipping outcome push")
            return False
        body = json.dumps(payload.to_dict()).encode()
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Coldy-Signature"] = self._sign(body)
        try:
            resp = httpx.post(self.url, content=body, headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            log.error("CRM webhook push failed: %s", e)
            return False


def get_default_sink() -> WebhookCRMSink:
    return WebhookCRMSink()
