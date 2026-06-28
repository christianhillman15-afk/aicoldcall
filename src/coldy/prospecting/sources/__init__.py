"""Prospect data sources (official APIs + a mock for offline use)."""

from __future__ import annotations

from .base import ProspectSource, RawBusiness


def get_source(name: str) -> ProspectSource:
    """Resolve a source by name: 'google', 'yelp', or 'mock'."""
    name = (name or "mock").strip().lower()
    if name == "google":
        from .google_places import GooglePlacesSource

        return GooglePlacesSource()
    if name == "yelp":
        from .yelp import YelpSource

        return YelpSource()
    from .mock import MockSource

    return MockSource()


__all__ = ["ProspectSource", "RawBusiness", "get_source"]
