"""Brain routing helpers: decide when a turn deserves the smarter (slower) model.

A live phone call is latency-bound, so the default turn-loop model should be
fast (Haiku). But a handful of moments — pricing pushback, a real objection, a
technical question — are where the call is won or lost and a smarter model
(Sonnet/Opus) earns its latency. ``is_hard_turn`` is a cheap, deterministic
classifier the pipeline can use to escalate only on those turns.

This keeps "smarter AND faster": fast on the 90% of turns that are easy, smart
on the 10% that matter. The model ids come from settings (``llm_model`` and
``llm_escalation_model``).
"""

from __future__ import annotations

import re

from ..config import settings

# Phrases that signal a high-stakes turn worth the smarter model.
_HARD_SIGNALS = (
    # price / money
    "how much", "cost", "price", "pricing", "expensive", "afford", "budget",
    "per month", "contract", "cancel", "refund", "fee", "charge",
    # hard objections
    "not interested", "no thanks", "already have", "already work with",
    "happy with", "we use", "don't need", "waste of time", "scam", "stop calling",
    "take me off", "do not call", "remove me",
    # skepticism / trust
    "who are you", "how did you get", "robot", "are you a bot",
    "are you ai", "real person", "prove it", "guarantee", "spam",
    # technical / specific
    "how does it work", "what exactly", "integrate", "compare", "versus", "vs",
    "what makes you different", "case study", "results", "roi",
)

_HARD_RE = re.compile("|".join(re.escape(s) for s in _HARD_SIGNALS), re.IGNORECASE)


def is_hard_turn(user_text: str) -> bool:
    """True if this user turn is high-stakes (objection / price / trust / depth).

    Cheap and deterministic so it adds no latency to the turn loop.
    """
    if not user_text:
        return False
    return bool(_HARD_RE.search(user_text))


def model_for_turn(user_text: str) -> str:
    """Pick the model id for this turn: escalate on hard turns, else the fast one."""
    if settings.llm_escalation_model and is_hard_turn(user_text):
        return settings.llm_escalation_model
    return settings.llm_model
