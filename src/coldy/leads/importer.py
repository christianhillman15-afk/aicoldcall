"""CSV lead import.

Expected columns (header row, case-insensitive; only ``phone`` is required):
    phone, business_name, contact_name, industry, city, state, notes

On import each number is normalized to E.164, its timezone + likely state +
mobile flag are resolved for compliance, and it is deduplicated per campaign.
Numbers already on the internal DNC list are imported but flagged DNC.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from ..compliance import dnc
from ..compliance.geo import (
    is_mobile,
    normalize_e164,
    state_for_number,
    timezone_for_number,
)
from ..db.base import LeadStatus
from ..db.models import Campaign, Lead
from ..db.session import session_scope
from ..logging import get_logger

log = get_logger("coldy.leads.importer")


@dataclass
class ImportResult:
    imported: int = 0
    skipped_invalid: int = 0
    skipped_duplicate: int = 0
    flagged_dnc: int = 0

    def __str__(self) -> str:
        return (
            f"imported={self.imported} duplicates={self.skipped_duplicate} "
            f"invalid={self.skipped_invalid} dnc_flagged={self.flagged_dnc}"
        )


def _get_or_create_campaign(session, name: str) -> Campaign:
    camp = session.execute(select(Campaign).where(Campaign.name == name)).scalar_one_or_none()
    if camp is None:
        camp = Campaign(name=name)
        session.add(camp)
        session.flush()
    return camp


def import_leads_csv(path: str | Path, campaign_name: str) -> ImportResult:
    path = Path(path)
    result = ImportResult()

    with session_scope() as session:
        campaign = _get_or_create_campaign(session, campaign_name)
        existing = {
            row[0]
            for row in session.execute(
                select(Lead.phone).where(Lead.campaign_id == campaign.id)
            )
        }

        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            # Normalize header keys to lowercase for tolerant matching.
            for raw in reader:
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
                phone_raw = row.get("phone", "")
                e164 = normalize_e164(phone_raw)
                if not e164:
                    result.skipped_invalid += 1
                    continue
                if e164 in existing:
                    result.skipped_duplicate += 1
                    continue

                suppressed = dnc.is_internally_suppressed(session, e164)
                lead = Lead(
                    campaign_id=campaign.id,
                    phone=e164,
                    business_name=row.get("business_name") or None,
                    contact_name=row.get("contact_name") or None,
                    industry=row.get("industry") or None,
                    city=row.get("city") or None,
                    state=(row.get("state") or state_for_number(e164) or None),
                    timezone=timezone_for_number(e164),
                    is_mobile=is_mobile(e164),
                    notes=row.get("notes") or None,
                    status=LeadStatus.DNC if suppressed else LeadStatus.NEW,
                    do_not_call=suppressed,
                )
                session.add(lead)
                existing.add(e164)
                result.imported += 1
                if suppressed:
                    result.flagged_dnc += 1

    log.info("Imported leads from %s into '%s': %s", path, campaign_name, result)
    return result
