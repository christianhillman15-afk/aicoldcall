"""Affluence enrichment: median household income for a ZIP.

Authoritative source is the US Census ACS 5-year estimates (full national
coverage) — set CENSUS_API_KEY (the keyless endpoint now redirects to a
"missing key" page). When no key/coverage is available we fall back to a small
bundled table so the engine still works offline with zero keys. Best-effort:
returns None rather than failing the pipeline.
"""

from __future__ import annotations

import os
from functools import lru_cache

import httpx

from ..logging import get_logger

log = get_logger("coldy.prospecting.census")

# B19013_001E = median household income (ACS 5-year).
_ACS = "https://api.census.gov/data/2022/acs/acs5"

# Small offline fallback (approximate median HH income) so prospecting runs with
# no key. Census (with a key) covers every ZIP nationwide; extend as needed.
_FALLBACK_INCOME: dict[str, int] = {
    "55424": 120_000, "55391": 150_000, "55345": 110_000, "55344": 115_000,
    "55369": 100_000, "55428": 70_000, "55401": 95_000, "55105": 105_000,
    "94301": 175_000, "94022": 250_000, "90210": 130_000, "33139": 80_000,
    "10021": 145_000, "60614": 120_000, "98004": 160_000, "78701": 95_000,
}


def _census_lookup(zip5: str) -> int | None:
    key = os.getenv("CENSUS_API_KEY")
    if not key:
        return None  # keyless endpoint no longer serves data
    params = {"get": "B19013_001E", "for": f"zip code tabulation area:{zip5}", "key": key}
    try:
        resp = httpx.get(_ACS, params=params, timeout=8, follow_redirects=True)
        resp.raise_for_status()
        rows = resp.json()  # [["B19013_001E","zip..."],["75000","55424"]]
        income = int(rows[1][0])
        return income if income >= 0 else None  # negatives are "no data" sentinels
    except Exception as e:  # noqa: BLE001
        log.debug("census lookup failed for %s: %s", zip5, e)
        return None


@lru_cache(maxsize=4096)
def median_income_for_zip(zip_code: str | None) -> int | None:
    if not zip_code:
        return None
    zip5 = "".join(ch for ch in zip_code if ch.isdigit())[:5]
    if len(zip5) != 5:
        return None
    return _census_lookup(zip5) or _FALLBACK_INCOME.get(zip5)
