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


def test_filter_events_skips_event_missing_date_key():
    events = [{"title": "No Date Event", "category": "arts_culture", "url": "https://example.com"}]
    result = generate_rss.filter_events(events)
    assert len(result) == 0


# ── load_events ───────────────────────────────────────────────────────────────

def test_load_events_missing_file(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        generate_rss.load_events(tmp_path / "nonexistent.json")
    assert exc_info.value.code != 0


def test_load_events_malformed_json(tmp_path):
    bad = tmp_path / "events.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        generate_rss.load_events(bad)
    assert exc_info.value.code != 0


def test_load_events_missing_events_key(tmp_path):
    bad = tmp_path / "events.json"
    bad.write_text('{"generated_at": "2026-03-18"}', encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        generate_rss.load_events(bad)
    assert exc_info.value.code != 0


def test_load_events_valid(tmp_path):
    events_file = tmp_path / "events.json"
    events_file.write_text(
        '{"generated_at": "2026-03-18T06:00:00Z", "event_count": 1, "events": []}',
        encoding="utf-8",
    )
    result = generate_rss.load_events(events_file)
    assert result == []


# ── build_feed / write_feed ───────────────────────────────────────────────────

def sample_events_list():
    return [
        make_event(
            id="ark-tomorrow-show",
            title="Tomorrow Show",
            date=TOMORROW,
            category="arts_culture",
        ),
        make_event(
            id="eventbrite-today-meeting",
            title="Today Meeting",
            date=TODAY,
            category="community",
            venue="City Hall",
            address="301 E Huron St",
        ),
    ]


def test_build_feed_item_count():
    events = sample_events_list()
    root = generate_rss.build_feed(events, title="Test Feed", site_url="https://example.com/")
    items = root.findall(".//item")
    assert len(items) == 2


def test_build_feed_sorted_by_date():
    events = sample_events_list()  # TOMORROW first in list, TODAY second
    root = generate_rss.build_feed(events, title="Test Feed", site_url="https://example.com/")
    items = root.findall(".//item")
    # TODAY should sort before TOMORROW - verify by checking guids in order
    guids = [item.findtext("guid") for item in items]
    assert guids[0] == "eventbrite-today-meeting"
    assert guids[1] == "ark-tomorrow-show"


def test_build_feed_item_fields():
    events = [make_event()]
    root = generate_rss.build_feed(events, title="Test Feed", site_url="https://example.com/")
    item = root.find(".//item")
    assert item.findtext("title") == "Test Event @ The Ark"
    assert item.findtext("link") == "https://theark.org/events/test"
    assert item.findtext("guid") == "ark-2026-03-15-test-event"
    assert item.find("guid").get("isPermaLink") == "false"
    assert item.findtext("category") == "arts_culture"


def test_build_feed_channel_fields():
    events = []
    root = generate_rss.build_feed(events, title="My Feed", site_url="https://example.com/")
    channel = root.find("channel")
    assert channel.findtext("title") == "My Feed"
    assert channel.findtext("link") == "https://example.com/"
    assert channel.findtext("ttl") == "1440"
    assert channel.findtext("lastBuildDate") is not None


def test_build_feed_valid_xml(tmp_path):
    events = sample_events_list()
    root = generate_rss.build_feed(events, title="Test Feed", site_url="https://example.com/")
    out = tmp_path / "feed.xml"
    generate_rss.write_feed(root, out)
    # Should parse without error using stdlib ET
    ET.parse(str(out))
    content = out.read_bytes()
    assert b"<![CDATA[" in content


def test_write_feed_xml_declaration(tmp_path):
    events = []
    root = generate_rss.build_feed(events, title="Test", site_url="https://example.com/")
    out = tmp_path / "feed.xml"
    generate_rss.write_feed(root, out)
    content = out.read_text(encoding="utf-8")
    assert content.startswith("<?xml")


def test_build_feed_pubdate_format():
    events = [make_event(date="2026-03-15")]
    root = generate_rss.build_feed(events, title="Test", site_url="https://example.com/")
    pub_date = root.findtext(".//pubDate")
    assert "Mar" in pub_date
    assert "2026" in pub_date
    assert "00:00:00" in pub_date
