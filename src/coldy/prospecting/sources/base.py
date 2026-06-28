"""Source interface + the normalized business record every source returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RawBusiness:
    source: str
    name: str
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    category: str | None = None
    rating: float | None = None
    review_count: int | None = None
    price_level: int | None = None  # 0-4
    latitude: float | None = None
    longitude: float | None = None
    source_id: str | None = None
    raw: dict = field(default_factory=dict)


class ProspectSource(Protocol):
    name: str

    def search(self, *, query: str, location: str, limit: int = 20) -> list[RawBusiness]:
        """Return businesses matching ``query`` in ``location``."""
        ...
