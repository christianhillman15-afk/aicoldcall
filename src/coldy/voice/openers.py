"""Opener library — the first 5-10 seconds that decide the call.

Grounded in Gong's analysis of 300M+ cold calls and other sales research:

- **Lead with context**, not with yourself. (top driver across all winners)
- **State a reason** for the call -> ~2.1x lift.
- **Ask permission** with an oddly-specific time ("twenty-seven seconds") -> the
  specificity is itself a pattern interrupt. Permission openers ~11.18%.
- **Social proof** ("I've been talking to other [industry] businesses...") was
  Gong's single highest performer (~11.24%).
- **Disarming honesty** breaks the script and pauses the rejection reflex.
- **Worst openers:** "Did I catch you at a bad time?" (~2.15%) and "How's your
  day going?" (~7.6%) — insincere, status-lowering. We never use these.

The compliance win: US law requires we disclose we're an AI. Instead of hiding
that, we make it the honesty hook. Every opener below states "AI assistant" +
the company name, so it is compliant *by construction* (a test enforces this).

We deliberately EXCLUDE openers that fake familiarity or research we don't have
(e.g. "how have you been?", "I read your quote", "a mutual connection said...").
For an honest AI cold call those are deceptive; honesty is also what converts.

Sources: gong.io best/worst cold call openers (300M calls); martal.ca 25
openers; hyperbound/clickinsights on first-10-seconds pattern interrupts.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..config import settings
from .persona import CallContext

# Nice spoken plurals for common service trades; fallback handles the rest.
_INDUSTRY_PHRASE = {
    "painting": "painting companies",
    "hvac": "HVAC companies",
    "plumbing": "plumbing companies",
    "landscaping": "landscaping companies",
    "cleaning": "cleaning companies",
    "roofing": "roofing companies",
    "electrical": "electrical companies",
    "construction": "construction companies",
    "contractor": "contractors",
}


@dataclass(frozen=True)
class Opener:
    id: str
    style: str          # category, for reporting / A-B analysis
    template: str       # full first utterance; includes AI + company disclosure
    note: str = ""      # why it works


# The curated set. Each template MUST contain the AI disclosure + {company}.
# Placeholders: {agent} {company} {industry_plural} {value} {seconds}
OPENERS: list[Opener] = [
    Opener(
        id="honest_heads_up",
        style="disarming_honesty",
        template=(
            "Hey, quick heads up — I'm {agent}, an AI assistant with {company}, "
            "and yeah, this is a cold call. Give me {seconds} seconds and if it's "
            "not relevant you can tell me to get lost — fair enough?"
        ),
        note="Owns the cold call + AI nature; the honesty pauses the brush-off reflex.",
    ),
    Opener(
        id="permission_specific",
        style="permission",
        template=(
            "Hi, it's {agent}, an AI assistant calling for {company}. I know you "
            "weren't expecting this — can I borrow {seconds} seconds to tell you "
            "why I called, and then you decide if it's worth it?"
        ),
        note="Permission + oddly-specific time. ~11% in Gong data; the number is a pattern interrupt.",
    ),
    Opener(
        id="social_proof_local",
        style="social_proof",
        template=(
            "Hi, this is {agent}, an AI assistant with {company}. I've been "
            "reaching out to {industry_plural} this week and figured I'd give you "
            "a shout too — have you come across us at all?"
        ),
        note="Gong's single highest performer (~11.24%): peer context reframes vendor->peer.",
    ),
    Opener(
        id="reason_led",
        style="reason",
        template=(
            "Hi, {agent} here, an AI assistant with {company}. The reason I'm "
            "calling — we help {industry_plural} {value}, and I figured it was "
            "worth {seconds} seconds. That okay?"
        ),
        note="Stating the reason gives ~2.1x lift; specific and respectful of time.",
    ),
    Opener(
        id="one_idea",
        style="curiosity",
        template=(
            "Hey, it's {agent} — I'm an AI assistant with {company}, so I'll be "
            "quick. I've got one idea that could help you {value}. Mind if I "
            "share it?"
        ),
        note="Teases a single insight; curiosity without pitching.",
    ),
    Opener(
        id="upfront_qualifier",
        style="qualifier",
        template=(
            "Hi, it's {agent}, an AI assistant with {company}. I'll be upfront — "
            "this call's about helping you {value}. If that's not on your plate, "
            "just say so and I'll let you go. Worth {seconds} seconds?"
        ),
        note="Reverse psychology + permission; qualifies fast and builds trust.",
    ),
    Opener(
        id="differentiator",
        style="pattern_interrupt",
        template=(
            "Hey, this is {agent}, an AI assistant with {company}. I bet you're "
            "wondering why you're getting another call today — honestly, fair. "
            "Give me one minute and I'll share something most of those calls "
            "won't. Cool?"
        ),
        note="Names the elephant in the room; promises differentiation.",
    ),
    Opener(
        id="peer_success",
        style="social_proof",
        template=(
            "Hi, {agent} here with {company} — I'm an AI assistant, I'll keep it "
            "short. We just helped another local business {value}, and I thought "
            "you'd want to hear how. Got a sec?"
        ),
        note="Concrete peer win builds credibility before any pitch.",
    ),
    Opener(
        id="value_bold",
        style="value",
        template=(
            "Hi, it's {agent}, an AI assistant calling for {company}. I'll cut "
            "right to it — I think we can help you {value}. Worth a quick look?"
        ),
        note="Busy owners appreciate a direct value statement; fast to the point.",
    ),
    Opener(
        id="industry_pattern",
        style="insight",
        template=(
            "Hey, this is {agent}, an AI assistant with {company}. I've been "
            "talking to a lot of {industry_plural} lately and the same thing "
            "keeps coming up — most aren't showing up when folks search online. "
            "Is that on your radar?"
        ),
        note="Positions caller as a sector observer; opens a conversation, not a pitch.",
    ),
]

OPENERS_BY_ID = {o.id: o for o in OPENERS}
VALID_STYLES = {"rotate", "auto"} | {o.id for o in OPENERS}


def industry_plural(industry: str | None) -> str:
    if not industry:
        return "local service businesses"
    key = industry.strip().lower()
    return _INDUSTRY_PHRASE.get(key, f"{key} businesses")


def choose(ctx: CallContext, style: str | None = None, *, seed: int | None = None) -> Opener:
    """Pick an opener. ``style`` can be a specific opener id or 'rotate'/'auto'
    (random A-B). Falls back to rotation for unknown styles. ``seed`` makes the
    choice deterministic per call (e.g. pass the call id)."""
    style = (style or settings.opener_style or "rotate").strip().lower()
    if style in OPENERS_BY_ID:
        return OPENERS_BY_ID[style]
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(OPENERS)


def render(opener: Opener, ctx: CallContext) -> str:
    """Fill an opener template for a specific lead."""
    return opener.template.format(
        agent=settings.agent_name,
        company=settings.company_name,
        industry_plural=industry_plural(ctx.industry),
        value=settings.value_prop_short,
        seconds=settings.opener_ask_seconds,
    )
