from coldy.voice.sales_playbook import OBJECTIONS, render_playbook


def test_render_playbook_has_objections_discovery_and_qualification():
    text = render_playbook()
    assert "DISCOVERY" in text
    assert "OBJECTION HANDLING" in text
    assert "record_qualification" in text
    # a couple of known objection triggers are present
    assert "Not interested" in text
    assert "How much does it cost?" in text


def test_dnc_objection_is_mandatory_and_present():
    dnc = next(o for o in OBJECTIONS if "do not call" in o["trigger"].lower())
    assert "add_to_do_not_call" in dnc["approach"]
