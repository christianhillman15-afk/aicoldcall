"""Yelp Fusion API source.

GET https://api.yelp.com/v3/businesses/search
Auth: Authorization: Bearer <YELP_API_KEY>.
Note Yelp's data-retention terms (you may not store most Yelp content
long-term); use it for discovery/scoring, not as a permanent datastore.
"""

from __future__ import annotations

import os

import httpx

from ...logging import get_logger
from .base import RawBusiness

log = get_logger("coldy.prospecting.yelp")

_ENDPOINT = "https://api.yelp.com/v3/businesses/search"


class YelpSource:
    name = "yelp"

    def search(self, *, query: str, location: str, limit: int = 20) -> list[RawBusiness]:
        key = os.getenv("YELP_API_KEY", "")
        if not key:
            raise RuntimeError("YELP_API_KEY is not set")
        headers = {"Authorization": f"Bearer {key}"}
        params = {"term": query, "location": location, "limit": min(limit, 50)}
        resp = httpx.get(_ENDPOINT, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        businesses = resp.json().get("businesses", [])

        out: list[RawBusiness] = []
        for b in businesses[:limit]:
            loc = b.get("location") or {}
            cats = b.get("categories") or []
            price = b.get("price")  # like "$$"
            out.append(
                RawBusiness(
                    source="yelp",
                    source_id=b.get("id"),
                    name=b.get("name", "Unknown"),
                    phone=b.get("phone") or None,  # Yelp returns E.164 in `phone`
                    website=None,  # Yelp gives its own listing URL, not the business site
                    address=", ".join(filter(None, [loc.get("address1"), loc.get("city")])),
                    city=loc.get("city"),
                    state=loc.get("state"),
                    zip=loc.get("zip_code"),
                    category=cats[0]["title"] if cats else None,
                    rating=b.get("rating"),
                    review_count=b.get("review_count"),
                    price_level=len(price) if price else None,
                    latitude=(b.get("coordinates") or {}).get("latitude"),
                    longitude=(b.get("coordinates") or {}).get("longitude"),
                    raw=b,
                )
            )
        log.info("Yelp returned %d businesses for '%s in %s'", len(out), query, location)
        return out
