from coldy.prospecting.scoring import score_business
from coldy.prospecting.sources.base import RawBusiness


def test_no_website_is_high_need():
    s = score_business(RawBusiness(source="m", name="X", website=None, review_count=10))
    assert s.need >= 45


def test_strong_presence_is_low_need():
    s = score_business(
        RawBusiness(source="m", name="X", website="http://x.com", rating=4.8, review_count=200)
    )
    assert s.need < 45


def test_affluent_busy_business_gets_flagged():
    b = RawBusiness(
        source="m", name="Summit Painting", website=None, rating=4.6,
        review_count=120, price_level=3, phone="+16125550111",
    )
    s = score_business(b, area_income=95_000)
    assert s.flagged
    assert s.afford >= 45 and s.need >= 25


def test_broke_area_not_flagged_even_if_needs_help():
    # High need (no site, low rating, few reviews) but no signals it can pay.
    b = RawBusiness(
        source="m", name="Budget Cleaners", website=None, rating=3.2,
        review_count=6, price_level=1,
    )
    s = score_business(b, area_income=None)
    assert not s.flagged
