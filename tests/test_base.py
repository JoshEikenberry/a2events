# tests/test_base.py
import pytest
from datetime import date, timedelta
from scrapers.base import make_event, slugify, parse_date, is_in_window, parse_ical_feed


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
    future = date.today() + timedelta(days=15)
    assert is_in_window(future.isoformat()) is True


def test_is_in_window_too_far():
    far = date.today() + timedelta(days=45)
    assert is_in_window(far.isoformat()) is False


def test_is_in_window_past():
    assert is_in_window("2020-01-01") is False


# ---------------------------------------------------------------------------
# parse_ical_feed tests
# ---------------------------------------------------------------------------

def _make_ical(events_data: list[dict]) -> bytes:
    """Build a minimal iCal feed from a list of dicts with keys: summary, dtstart, url, location, description."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for e in events_data:
        lines += [
            "BEGIN:VEVENT",
            f"SUMMARY:{e['summary']}",
            f"DTSTART:{e['dtstart']}",
            f"URL:{e['url']}",
            f"LOCATION:{e.get('location', '')}",
            f"DESCRIPTION:{e.get('description', '')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode()


def test_parse_ical_feed_returns_events_in_window():
    future = date.today() + timedelta(days=5)
    ical = _make_ical([{
        "summary": "Jazz Night",
        "dtstart": future.strftime("%Y%m%d"),
        "url": "https://example.com/jazz",
        "location": "Blue Llama",
        "description": "A great jazz show",
    }])
    events = parse_ical_feed(ical, source="test", category="arts_culture")
    assert len(events) == 1
    assert events[0]["title"] == "Jazz Night"
    assert events[0]["venue"] == "Blue Llama"
    assert events[0]["url"] == "https://example.com/jazz"


def test_parse_ical_feed_skips_out_of_window():
    far_future = date.today() + timedelta(days=60)
    ical = _make_ical([{
        "summary": "Far Future Event",
        "dtstart": far_future.strftime("%Y%m%d"),
        "url": "https://example.com/far",
    }])
    events = parse_ical_feed(ical, source="test", category="arts_culture")
    assert len(events) == 0


def test_parse_ical_feed_skips_missing_url():
    future = date.today() + timedelta(days=5)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "BEGIN:VEVENT",
        "SUMMARY:No URL Event",
        f"DTSTART:{future.strftime('%Y%m%d')}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    ical = "\r\n".join(lines).encode()
    events = parse_ical_feed(ical, source="test", category="arts_culture")
    assert len(events) == 0


def test_parse_ical_feed_datetime_event_has_time():
    future = date.today() + timedelta(days=5)
    dtstart = future.strftime("%Y%m%d") + "T200000"  # 8 PM
    ical = _make_ical([{
        "summary": "Evening Show",
        "dtstart": dtstart,
        "url": "https://example.com/show",
    }])
    events = parse_ical_feed(ical, source="test", category="arts_culture")
    assert len(events) == 1
    assert events[0]["time"] != ""  # datetime event should have a time


def test_parse_ical_feed_allday_event_has_empty_time():
    future = date.today() + timedelta(days=5)
    dtstart = future.strftime("%Y%m%d")  # all-day (date only)
    ical = _make_ical([{
        "summary": "All Day Event",
        "dtstart": dtstart,
        "url": "https://example.com/allday",
    }])
    events = parse_ical_feed(ical, source="test", category="arts_culture")
    assert len(events) == 1
    assert events[0]["time"] == ""  # all-day event should have empty time
