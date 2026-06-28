"""Mandatory spoken disclosures.

Two distinct disclosures matter:

1. AI / identity disclosure. The FCC's 2024 ruling treats AI voices as
   "artificial or prerecorded." Artificial-voice calls must identify the entity
   responsible for the call, and several states (e.g. CA "Bot" law) require
   disclosing that the caller is an automated system. We therefore open EVERY
   call by stating the company and that the caller is an AI assistant.

2. Recording disclosure. Played when recording is enabled and the lead is in an
   all-party-consent state (or state is unknown).
"""

from __future__ import annotations

from ..config import settings


def ai_identity_disclosure() -> str:
    """The opening line spoken on every call. Identity + AI nature + purpose."""
    return (
        f"Hi, this is {settings.agent_name}, an AI assistant calling on behalf of "
        f"{settings.company_name}."
    )


def recording_disclosure() -> str:
    return "Just so you know, this call may be recorded for quality purposes."


def opt_out_disclosure() -> str:
    """Telemarketing artificial-voice calls must offer an opt-out."""
    return (
        "If you'd rather not get calls like this, just say the word and I'll add you "
        "to our do-not-call list right away."
    )
