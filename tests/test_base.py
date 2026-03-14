# tests/test_base.py
import pytest
from scrapers.base import make_event, slugify


def test_make_event_generates_id():
    event = make_event(
        title="The War on Drugs",
        date="2026-03-15",
        time="8:00 PM",
        venue="The Ark",
        url="https://theark.org/event/123",
        source="ark",
        category="arts_culture",
    )
    assert event["id"] == "ark-2026-03-15-the-war-on-drugs"


def test_make_event_required_fields_present():
    event = make_event(
        title="Test Event",
        date="2026-03-15",
        time="7:00 PM",
        venue="Test Venue",
        url="https://example.com/event",
        source="test",
        category="arts_culture",
    )
    required = ["id", "title", "date", "time", "venue", "url", "source",
                "category", "tags", "description", "address",
                "also_listed_at", "image_url", "possible_duplicate", "scraped_at"]
    for field in required:
        assert field in event, f"Missing field: {field}"


def test_make_event_defaults():
    event = make_event(
        title="Test",
        date="2026-03-15",
        time="7:00 PM",
        venue="Venue",
        url="https://example.com",
        source="test",
        category="arts_culture",
    )
    assert event["tags"] == []
    assert event["description"] == ""
    assert event["address"] == ""
    assert event["also_listed_at"] == []
    assert event["image_url"] is None
    assert event["possible_duplicate"] is False


def test_make_event_url_required():
    with pytest.raises(ValueError, match="url"):
        make_event(
            title="Test",
            date="2026-03-15",
            time="7:00 PM",
            venue="Venue",
            url=None,
            source="test",
            category="arts_culture",
        )


def test_slugify():
    assert slugify("The War on Drugs") == "the-war-on-drugs"
    assert slugify("Conor O'Neill's") == "conor-oneills"
    assert slugify("  extra  spaces  ") == "extra-spaces"
    assert slugify("Special! @#$ Chars") == "special-chars"


from scrapers.base import parse_date, is_in_window, parse_ical_feed
from datetime import date
import responses as responses_lib


def test_parse_date_iso():
    assert parse_date("2026-03-15") == date(2026, 3, 15)


def test_parse_date_human():
    assert parse_date("March 15, 2026") == date(2026, 3, 15)
    assert parse_date("Saturday, March 15, 2026") == date(2026, 3, 15)


def test_parse_date_slash():
    assert parse_date("03/15/2026") == date(2026, 3, 15)


def test_parse_date_invalid():
    assert parse_date("not a date") is None


def test_is_in_window_today():
    today = date.today()
    assert is_in_window(today.isoformat()) is True


def test_is_in_window_future_in_range():
    from datetime import timedelta
    future = date.today() + timedelta(days=15)
    assert is_in_window(future.isoformat()) is True


def test_is_in_window_too_far():
    from datetime import timedelta
    far = date.today() + timedelta(days=45)
    assert is_in_window(far.isoformat()) is False


def test_is_in_window_past():
    assert is_in_window("2020-01-01") is False
