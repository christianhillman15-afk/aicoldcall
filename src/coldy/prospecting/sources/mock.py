"""Offline mock source — lets you run/test the whole prospecting pipeline
without any API keys. Returns a realistic mix: some with no website (high need),
some in affluent areas (high afford)."""

from __future__ import annotations

from .base import RawBusiness

_SAMPLE = [
    # name, phone, website, city, state, zip, category, rating, reviews, price
    ("Summit Painting Co", "+16125550111", None, "Edina", "MN", "55424", "painting", 4.6, 38, 3),
    ("Lakeshore Plumbing", "+16125550112", "http://lakeshoreplumbing.com", "Wayzata", "MN", "55391", "plumbing", 3.8, 12, 2),
    ("Evergreen Landscaping", "+16125550113", None, "Minnetonka", "MN", "55345", "landscaping", 4.9, 140, 3),
    ("Budget Cleaners", "+16125550114", None, "Brooklyn Park", "MN", "55428", "cleaning", 3.2, 6, 1),
    ("Premier HVAC", "+16125550115", "http://premierhvac.com", "Eden Prairie", "MN", "55344", "hvac", 4.7, 210, 3),
    ("Family Roofing", "+16125550116", None, "Maple Grove", "MN", "55369", "roofing", 4.1, 22, 2),
]


class MockSource:
    name = "mock"

    def search(self, *, query: str, location: str, limit: int = 20) -> list[RawBusiness]:
        out = []
        for (name, phone, web, city, state, zp, cat, rating, reviews, price) in _SAMPLE[:limit]:
            out.append(
                RawBusiness(
                    source="mock",
                    source_id=f"mock:{name}",
                    name=name,
                    phone=phone,
                    website=web,
                    address=f"{city}, {state} {zp}",
                    city=city,
                    state=state,
                    zip=zp,
                    category=cat,
                    rating=rating,
                    review_count=reviews,
                    price_level=price,
                )
            )
        return out
