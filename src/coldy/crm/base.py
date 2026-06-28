"""CRM integration interface.

Outcomes are pushed to whatever CRM/automation you use (HubSpot, GoHighLevel,
Salesforce, a Zapier/Make webhook, or Oxsome's own pipeline). Implement
``CRMSink`` for a specific CRM; the default is a generic signed webhook.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass
class CallOutcomePayload:
    call_id: int
    lead_id: int
    campaign: str | None
    phone: str
    business_name: str | None
    contact_name: str | None
    outcome: str
    summary: str | None
    duration_seconds: int | None
    occurred_at: str = ""

    def __post_init__(self) -> None:
        if not self.occurred_at:
            self.occurred_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class CRMSink(Protocol):
    def send(self, payload: CallOutcomePayload) -> bool:
        """Push an outcome to the CRM. Return True on success."""
        ...
