"""Phone-number geography: timezone (for calling hours) and state (for
recording-consent rules).

Timezone is resolved from the number itself via the ``phonenumbers`` library
(carrier-grade). State is resolved from a North American area-code map; it is
intentionally conservative — unknown numbers are treated as the strictest case.
"""

from __future__ import annotations

import phonenumbers
from phonenumbers import timezone as pn_timezone

# Area code -> USPS state. Representative coverage of common NANP area codes.
# This is NOT exhaustive; extend as needed or replace with a licensed lookup.
AREA_CODE_STATE: dict[str, str] = {
    # Minnesota (home turf for the example brand)
    "218": "MN", "320": "MN", "507": "MN", "612": "MN", "651": "MN", "763": "MN", "952": "MN",
    # California (two-party consent)
    "209": "CA", "213": "CA", "310": "CA", "323": "CA", "408": "CA", "415": "CA",
    "510": "CA", "530": "CA", "559": "CA", "619": "CA", "626": "CA", "650": "CA",
    "707": "CA", "714": "CA", "760": "CA", "805": "CA", "818": "CA", "858": "CA",
    "909": "CA", "916": "CA", "925": "CA", "949": "CA",
    # Florida (two-party consent)
    "305": "FL", "321": "FL", "352": "FL", "386": "FL", "407": "FL", "561": "FL",
    "727": "FL", "754": "FL", "772": "FL", "786": "FL", "813": "FL", "850": "FL",
    "904": "FL", "941": "FL", "954": "FL",
    # Illinois (two-party consent)
    "217": "IL", "224": "IL", "309": "IL", "312": "IL", "618": "IL", "630": "IL",
    "708": "IL", "773": "IL", "815": "IL", "847": "IL",
    # Texas
    "210": "TX", "214": "TX", "281": "TX", "409": "TX", "469": "TX", "512": "TX",
    "713": "TX", "806": "TX", "817": "TX", "832": "TX", "915": "TX", "972": "TX",
    # New York
    "212": "NY", "315": "NY", "347": "NY", "516": "NY", "518": "NY", "585": "NY",
    "607": "NY", "631": "NY", "646": "NY", "716": "NY", "718": "NY", "845": "NY", "914": "NY",
    # Pennsylvania (two-party consent)
    "215": "PA", "267": "PA", "412": "PA", "484": "PA", "610": "PA", "717": "PA",
    "724": "PA", "814": "PA",
    # Washington (two-party consent)
    "206": "WA", "253": "WA", "360": "WA", "425": "WA", "509": "WA",
    # Massachusetts (two-party consent)
    "339": "MA", "351": "MA", "413": "MA", "508": "MA", "617": "MA", "774": "MA", "781": "MA", "978": "MA",
    # A few more common ones
    "303": "CO", "720": "CO", "404": "GA", "470": "GA", "678": "GA", "770": "GA",
    "602": "AZ", "480": "AZ", "623": "AZ", "702": "NV", "725": "NV",
    "503": "OR", "971": "OR", "615": "TN", "901": "TN", "704": "NC", "919": "NC",
    "313": "MI", "248": "MI", "216": "OH", "614": "OH", "513": "OH",
}


def normalize_e164(raw: str, default_region: str = "US") -> str | None:
    """Parse a phone string to E.164 (+1...), or None if invalid."""
    try:
        num = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def area_code(e164: str) -> str | None:
    """Extract the 3-digit NANP area code from a +1 number."""
    digits = "".join(ch for ch in e164 if ch.isdigit())
    if digits.startswith("1") and len(digits) >= 11:
        return digits[1:4]
    if len(digits) >= 10:
        return digits[:3]
    return None


def state_for_number(e164: str) -> str | None:
    ac = area_code(e164)
    if ac is None:
        return None
    return AREA_CODE_STATE.get(ac)


def timezone_for_number(e164: str) -> str | None:
    """Return an IANA timezone (e.g. 'America/Chicago') for the number, or None.

    Falls back to None when the number maps only to the unknown sentinel.
    """
    try:
        num = phonenumbers.parse(e164, "US")
    except phonenumbers.NumberParseException:
        return None
    zones = pn_timezone.time_zones_for_number(num)
    if not zones:
        return None
    primary = zones[0]
    if primary in ("Etc/Unknown", None):
        return None
    return primary


def is_mobile(e164: str) -> bool | None:
    """Best-effort mobile detection (matters because TCPA is stricter for cells)."""
    try:
        num = phonenumbers.parse(e164, "US")
    except phonenumbers.NumberParseException:
        return None
    from phonenumbers import PhoneNumberType, number_type

    t = number_type(num)
    if t == PhoneNumberType.MOBILE:
        return True
    if t in (PhoneNumberType.FIXED_LINE, PhoneNumberType.VOIP):
        return False
    if t == PhoneNumberType.FIXED_LINE_OR_MOBILE:
        return None  # genuinely ambiguous in NANP
    return None
