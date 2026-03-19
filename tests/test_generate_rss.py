import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import pytest

import generate_rss


# ── fixtures ──────────────────────────────────────────────────────────────────

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
IN_WINDOW = (date.today() + timedelta(days=15)).isoformat()
OUTSIDE_WINDOW = (date.today() + timedelta(days=31)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def make_event(**overrides):
    base = {
        "id": "ark-2026-03-15-test-event",
        "title": "Test Event",
        "date": TOMORROW,
        "time": "8:00 PM",
        "venue": "The Ark",
        "address": "316 S Main St, Ann Arbor, MI",
        "category": "arts_culture",
        "tags": ["music"],
        "description": "A great show.",
        "url": "https://theark.org/events/test",
        "source": "ark",
        "also_listed_at": [],
        "image_url": None,
        "possible_duplicate": False,
        "scraped_at": "2026-03-18T06:00:00Z",
    }
    base.update(overrides)
    return base


# ── format_rfc822 ─────────────────────────────────────────────────────────────

def test_format_rfc822_returns_string():
    result = generate_rss.format_rfc822("2026-03-15")
    assert isinstance(result, str)
    assert "2026" in result
    assert "Mar" in result


def test_format_rfc822_midnight_utc():
    result = generate_rss.format_rfc822("2026-03-15")
    # RFC 822 format: "Sun, 15 Mar 2026 00:00:00 GMT"
    assert "00:00:00" in result
    assert "GMT" in result


# ── format_date_long ──────────────────────────────────────────────────────────

def test_format_date_long():
    assert generate_rss.format_date_long("2026-03-15") == "March 15, 2026"


def test_format_date_long_single_digit_day():
    assert generate_rss.format_date_long("2026-03-05") == "March 5, 2026"


# ── build_item_title ──────────────────────────────────────────────────────────

def test_build_item_title_with_venue():
    event = make_event(title="The War on Drugs", venue="The Ark")
    assert generate_rss.build_item_title(event) == "The War on Drugs @ The Ark"


def test_build_item_title_no_venue():
    event = make_event(title="Mystery Event", venue="")
    assert generate_rss.build_item_title(event) == "Mystery Event"


def test_build_item_title_none_venue():
    event = make_event(title="Mystery Event", venue=None)
    assert generate_rss.build_item_title(event) == "Mystery Event"


# ── build_item_description ────────────────────────────────────────────────────

def test_build_item_description_full():
    event = make_event(
        date=TOMORROW,
        time="8:00 PM",
        venue="The Ark",
        address="316 S Main St, Ann Arbor, MI",
        description="A great show.",
    )
    result = generate_rss.build_item_description(event)
    assert "8:00 PM" in result
    assert "The Ark" in result
    assert "316 S Main St" in result
    assert "A great show." in result
    assert "<strong>" in result


def test_build_item_description_no_venue_no_address():
    event = make_event(venue="", address="", description="A show.")
    result = generate_rss.build_item_description(event)
    # no venue line at all
    assert "·" not in result
    assert "A show." in result


def test_build_item_description_venue_no_address():
    event = make_event(venue="The Ark", address="")
    result = generate_rss.build_item_description(event)
    assert "The Ark" in result
    assert "·" not in result


def test_build_item_description_address_no_venue():
    event = make_event(venue="", address="316 S Main St, Ann Arbor, MI")
    result = generate_rss.build_item_description(event)
    assert "316 S Main St" in result
    assert "·" not in result


def test_build_item_description_no_description():
    event = make_event(description="")
    result = generate_rss.build_item_description(event)
    # no trailing empty paragraph
    assert result.count("<p>") == 1


def test_build_item_description_no_time():
    event = make_event(time="")
    result = generate_rss.build_item_description(event)
    assert "—" not in result


def test_build_item_description_none_fields():
    event = make_event(venue=None, address=None, description=None, time=None)
    result = generate_rss.build_item_description(event)
    assert isinstance(result, str)
    assert len(result) > 0


# ── filter_events ─────────────────────────────────────────────────────────────

def test_filter_events_includes_today():
    events = [make_event(date=TODAY, category="arts_culture")]
    result = generate_rss.filter_events(events)
    assert len(result) == 1


def test_filter_events_includes_in_window():
    events = [make_event(date=IN_WINDOW)]
    result = generate_rss.filter_events(events)
    assert len(result) == 1


def test_filter_events_excludes_outside_window():
    events = [make_event(date=OUTSIDE_WINDOW)]
    result = generate_rss.filter_events(events)
    assert len(result) == 0


def test_filter_events_excludes_past():
    events = [make_event(date=YESTERDAY)]
    result = generate_rss.filter_events(events)
    assert len(result) == 0


def test_filter_events_by_category():
    events = [
        make_event(date=TOMORROW, category="arts_culture"),
        make_event(date=TOMORROW, category="community"),
    ]
    result = generate_rss.filter_events(events, category="arts_culture")
    assert len(result) == 1
    assert result[0]["category"] == "arts_culture"


def test_filter_events_no_category_returns_all():
    events = [
        make_event(date=TOMORROW, category="arts_culture"),
        make_event(date=TOMORROW, category="community"),
    ]
    result = generate_rss.filter_events(events, category=None)
    assert len(result) == 2


def test_filter_events_includes_possible_duplicates():
    events = [make_event(date=TOMORROW, possible_duplicate=True)]
    result = generate_rss.filter_events(events)
    assert len(result) == 1


# ── load_events ───────────────────────────────────────────────────────────────

def test_load_events_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        generate_rss.load_events(tmp_path / "nonexistent.json")


def test_load_events_malformed_json(tmp_path):
    bad = tmp_path / "events.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(SystemExit):
        generate_rss.load_events(bad)


def test_load_events_missing_events_key(tmp_path):
    bad = tmp_path / "events.json"
    bad.write_text('{"generated_at": "2026-03-18"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        generate_rss.load_events(bad)


def test_load_events_valid(tmp_path):
    events_file = tmp_path / "events.json"
    events_file.write_text(
        '{"generated_at": "2026-03-18T06:00:00Z", "event_count": 1, "events": []}',
        encoding="utf-8",
    )
    result = generate_rss.load_events(events_file)
    assert result == []
