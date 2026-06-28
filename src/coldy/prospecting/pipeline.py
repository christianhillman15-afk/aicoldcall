"""Prospecting pipeline: search -> normalize -> dedupe -> enrich -> score ->
persist -> flag -> alert."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..compliance.geo import normalize_e164
from ..db.models import Prospect
from ..logging import get_logger
from . import alerts
from .enrichment import median_income_for_zip
from .scoring import score_business
from .sources import RawBusiness, get_source

log = get_logger("coldy.prospecting.pipeline")


@dataclass
class SearchSummary:
    found: int = 0
    new: int = 0
    flagged: int = 0
    flagged_prospects: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        return f"found={self.found} new={self.new} flagged={self.flagged}"


class ProspectingPipeline:
    def __init__(self, session: Session):
        self.session = session

    def run(
        self,
        *,
        source_name: str,
        query: str,
        location: str,
        limit: int = 20,
        enrich_income: bool = True,
        alert: bool = True,
    ) -> SearchSummary:
        source = get_source(source_name)
        raws: list[RawBusiness] = source.search(query=query, location=location, limit=limit)
        summary = SearchSummary(found=len(raws))

        for b in raws:
            phone = normalize_e164(b.phone) if b.phone else None
            income = median_income_for_zip(b.zip) if enrich_income else None
            sc = score_business(b, income)

            existing = None
            if b.source_id:
                existing = self.session.execute(
                    select(Prospect).where(
                        Prospect.source == b.source, Prospect.source_id == b.source_id
                    )
                ).scalar_one_or_none()

            p = existing or Prospect(source=b.source, source_id=b.source_id)
            if existing is None:
                self.session.add(p)
                summary.new += 1

            p.business_name = b.name
            p.phone = phone
            p.website = b.website
            p.address = b.address
            p.city = b.city
            p.state = b.state
            p.zip = b.zip
            p.category = b.category
            p.rating = b.rating
            p.review_count = b.review_count
            p.price_level = b.price_level
            p.has_website = bool(b.website)
            p.area_income = income
            p.need_score = sc.need
            p.afford_score = sc.afford
            p.fit_score = sc.fit
            p.flagged = sc.flagged
            p.status = "flagged" if sc.flagged else "new"

            if sc.flagged:
                summary.flagged += 1
                summary.flagged_prospects.append(
                    {
                        "business_name": b.name,
                        "phone": phone,
                        "city": b.city,
                        "state": b.state,
                        "has_website": bool(b.website),
                        "fit": sc.fit,
                        "need": sc.need,
                        "afford": sc.afford,
                    }
                )

        self.session.flush()
        log.info("Prospecting '%s in %s' (%s): %s", query, location, source_name, summary)

        if alert and summary.flagged_prospects:
            alerts.send_flagged(summary.flagged_prospects)
        return summary
