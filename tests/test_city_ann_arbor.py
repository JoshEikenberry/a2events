"""Tests for the City of Ann Arbor calendar scraper."""
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scrapers.base import is_in_window

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "city_ann_arbor.json"
FIXTURE_DATA = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

@pytest.fixture
def fixture_clock():
    with patch("scrapers.base.local_today", return_value=date(2026, 3, 16)):
        yield


def _mock_session(json_data):
    """Build a mock RateLimitedSession whose .get() returns json_data."""
    sess = MagicMock()
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list(fixture_clock):
    with patch("scrapers.city_ann_arbor.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_DATA)
        from scrapers.city_ann_arbor import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category(fixture_clock):
    with patch("scrapers.city_ann_arbor.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_DATA)
        from scrapers.city_ann_arbor import scrape
        for e in scrape():
            assert e["source"] == "city_ann_arbor"
            assert e["category"] == "city_ann_arbor"


def test_events_in_window(fixture_clock):
    with patch("scrapers.city_ann_arbor.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_DATA)
        from scrapers.city_ann_arbor import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


def test_events_have_required_fields(fixture_clock):
    with patch("scrapers.city_ann_arbor.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_DATA)
        from scrapers.city_ann_arbor import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "city_ann_arbor"
            assert e["category"] == "city_ann_arbor"


def test_public_meeting_tag(fixture_clock):
    with patch("scrapers.city_ann_arbor.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_DATA)
        from scrapers.city_ann_arbor import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        meeting_events = [e for e in events if "public_meeting" in e["tags"]]
        assert len(meeting_events) >= 1, "Fixture must contain at least one meeting-tagged event"
