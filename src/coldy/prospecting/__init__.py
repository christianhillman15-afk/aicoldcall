"""Prospecting engine: find businesses Oxsome can help, score fit, flag the best.

Sources are OFFICIAL business-data APIs (Google Places, Yelp) — not scraping of
social platforms. Prospects are scored on "needs marketing" + "can afford it"
and the strongest are flagged to you. A flagged prospect becomes a callable lead
only after consent is captured (export -> import). See docs/PROSPECTING.md.
"""

from .pipeline import ProspectingPipeline, SearchSummary

__all__ = ["ProspectingPipeline", "SearchSummary"]
