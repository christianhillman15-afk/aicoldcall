"""Google Places API (New) source.

POST https://places.googleapis.com/v1/places:searchText
Auth: X-Goog-Api-Key header. Fields chosen via X-Goog-FieldMask.
Set GOOGLE_PLACES_API_KEY. Respect Google's caching/retention terms.
"""

from __future__ import annotations

import os

import httpx

from ...logging import get_logger
from .base import RawBusiness

log = get_logger("coldy.prospecting.google")

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
_FIELDS = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.priceLevel",
        "places.location",
        "places.primaryType",
        "places.addressComponents",
    ]
)
_PRICE = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


def _component(components: list[dict], type_: str, short: bool = False) -> str | None:
    for c in components or []:
        if type_ in c.get("types", []):
            return c.get("shortText" if short else "longText")
    return None


class GooglePlacesSource:
    name = "google"

    def search(self, *, query: str, location: str, limit: int = 20) -> list[RawBusiness]:
        key = os.getenv("GOOGLE_PLACES_API_KEY", "")
        if not key:
            raise RuntimeError("GOOGLE_PLACES_API_KEY is not set")
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": _FIELDS,
        }
        body = {"textQuery": f"{query} in {location}", "maxResultCount": min(limit, 20)}
        resp = httpx.post(_ENDPOINT, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
        places = resp.json().get("places", [])

        out: list[RawBusiness] = []
        for p in places[:limit]:
            comps = p.get("addressComponents", [])
            out.append(
                RawBusiness(
                    source="google",
                    source_id=p.get("id"),
                    name=(p.get("displayName") or {}).get("text", "Unknown"),
                    phone=p.get("nationalPhoneNumber"),
                    website=p.get("websiteUri"),
                    address=p.get("formattedAddress"),
                    city=_component(comps, "locality"),
                    state=_component(comps, "administrative_area_level_1", short=True),
                    zip=_component(comps, "postal_code"),
                    category=p.get("primaryType"),
                    rating=p.get("rating"),
                    review_count=p.get("userRatingCount"),
                    price_level=_PRICE.get(p.get("priceLevel")),
                    latitude=(p.get("location") or {}).get("latitude"),
                    longitude=(p.get("location") or {}).get("longitude"),
                    raw=p,
                )
            )
        log.info("Google Places returned %d businesses for '%s in %s'", len(out), query, location)
        return out
