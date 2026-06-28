"""Call-recording consent rules by state.

In "all-party" (two-party) consent states, every party must consent to being
recorded. Coldy handles this by (a) only recording when enabled, and (b)
injecting a spoken recording notice at the start of the call when the lead is
in an all-party state (or when the state is unknown — fail safe).
"""

from __future__ import annotations

# States generally requiring all-party consent to record a call. This list is a
# practical superset used to decide when to play a recording notice; confirm
# specifics with counsel, as case law and exceptions vary.
ALL_PARTY_CONSENT_STATES: frozenset[str] = frozenset(
    {
        "CA", "CT", "DE", "FL", "IL", "MD", "MA", "MI", "MT",
        "NV", "NH", "OR", "PA", "WA",
    }
)


def requires_all_party_consent(state: str | None) -> bool:
    """True if we must obtain (or announce) consent before recording.

    Unknown state -> True (fail safe: assume the strictest rule).
    """
    if not state:
        return True
    return state.upper() in ALL_PARTY_CONSENT_STATES
