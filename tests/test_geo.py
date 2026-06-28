from coldy.compliance.geo import area_code, normalize_e164, state_for_number


def test_normalize_us_number_variants():
    assert normalize_e164("(612) 555-0100") == "+16125550100"
    assert normalize_e164("612-555-0100") == "+16125550100"
    assert normalize_e164("+1 612 555 0100") == "+16125550100"


def test_normalize_rejects_garbage():
    assert normalize_e164("not a phone") is None
    assert normalize_e164("12345") is None


def test_area_code_and_state():
    assert area_code("+16125550100") == "612"
    assert state_for_number("+16125550100") == "MN"
    assert state_for_number("+12135550100") == "CA"
