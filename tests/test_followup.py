from coldy.db.base import CallOutcome
from coldy.db.models import Lead
from coldy.followup import sms_body


def _lead():
    return Lead(phone="+16125550100", business_name="Acme")


def test_interested_gets_followup_message():
    body = sms_body(CallOutcome.MEETING_BOOKED, _lead())
    assert body and "STOP" in body  # opt-out present


def test_missed_gets_nudge():
    body = sms_body(CallOutcome.NO_ANSWER, _lead())
    assert body and "missed you" in body


def test_neutral_outcomes_get_no_sms():
    assert sms_body(CallOutcome.NOT_INTERESTED, _lead()) is None
    assert sms_body(CallOutcome.OPTED_OUT, _lead()) is None
