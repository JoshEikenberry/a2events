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
