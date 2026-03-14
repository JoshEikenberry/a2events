# tests/test_base.py
import pytest
from datetime import date, datetime, timezone
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
