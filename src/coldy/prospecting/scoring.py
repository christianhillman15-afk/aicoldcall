"""Fit scoring: combine "needs marketing help" with "can afford it".

need_score   — the worse their online presence, the more Oxsome can help.
afford_score — affluent area + price level + established/busy + reachable.
fit_score    — weighted blend; a prospect is flagged only when it both needs
               help AND looks able to pay (no point chasing broke businesses).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from .sources.base import RawBusiness


@dataclass
class Scores:
    need: int
    afford: int
    fit: float
    flagged: bool


def score_business(b: RawBusiness, area_income: int | None = None) -> Scores:
    # --- need: weak online presence => more upside from marketing help ---
    need = 0
    if not b.website:
        need += 45  # no website is the strongest "needs help" signal
    if b.rating is not None and b.rating < 4.0:
        need += 15
    if b.review_count is not None:
        if b.review_count < 25:
            need += 25
        elif b.review_count < 75:
            need += 10
    need = min(need, 100)

    # --- afford: affluent area + price level + established/busy + reachable ---
    afford = 0
    if area_income:
        if area_income >= 90_000:
            afford += 40
        elif area_income >= 70_000:
            afford += 28
        elif area_income >= 55_000:
            afford += 15
    if b.price_level:
        afford += min(b.price_level, 4) * 8  # up to 32
    if b.review_count:
        if b.review_count >= 100:
            afford += 20
        elif b.review_count >= 40:
            afford += 12
    if b.phone:
        afford += 5
    afford = min(afford, 100)

    fit = round(0.45 * need + 0.55 * afford, 1)
    flagged = (
        fit >= settings.prospect_min_fit
        and afford >= settings.prospect_min_afford
        and need >= settings.prospect_min_need
    )
    return Scores(need=need, afford=afford, fit=fit, flagged=flagged)
