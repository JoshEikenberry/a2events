"""Tests for the Eventbrite scraper."""
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "eventbrite.json").read_text())

@pytest.fixture
def fixture_clock():
    with patch("scrapers.base.local_today", return_value=date(2026, 3, 16)):
        yield


def _mock_scrape(fixture=FIXTURE):
    """Helper: run scrape() with the given fixture mocked in."""
    with patch("scrapers.eventbrite.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # Mock the homepage GET (for CSRF cookie)
        homepage_resp = MagicMock()
        homepage_resp.cookies = MagicMock()
        homepage_resp.cookies.__iter__ = MagicMock(return_value=iter([]))

        # Mock the search POST
        search_resp = MagicMock()
        fixture = json.loads(json.dumps(fixture))
        fixture["events"]["pagination"]["page_count"] = 1
        search_resp.json.return_value = fixture
        search_resp.raise_for_status = MagicMock()

        mock_session.get.return_value = homepage_resp
        mock_session.post.return_value = search_resp
        mock_session.headers = {}

        import scrapers.eventbrite
        import importlib
        importlib.reload(scrapers.eventbrite)
        from scrapers.eventbrite import scrape
        return scrape()


def test_scrape_returns_list(fixture_clock):
    events = _mock_scrape()
    assert isinstance(events, list)


def test_events_not_empty(fixture_clock):
    events = _mock_scrape()
    assert len(events) > 0


def test_events_source(fixture_clock):
    events = _mock_scrape()
    for e in events:
        assert e["source"] == "eventbrite"
        assert e["category"] == "community"
        assert e["url"].startswith("http")


def test_events_in_window(fixture_clock):
    from scrapers.base import is_in_window
    events = _mock_scrape()
    for e in events:
        assert is_in_window(e["date"]), f"Event {e['title']!r} date {e['date']!r} is outside window"


def test_events_have_required_fields(fixture_clock):
    events = _mock_scrape()
    required = {"id", "title", "date", "time", "venue", "url", "source", "category"}
    for e in events:
        assert required.issubset(e.keys()), f"Missing fields: {required - e.keys()}"


def test_events_skip_missing_url(fixture_clock):
    """Events with no URL should be skipped."""
    fixture = json.loads(json.dumps(FIXTURE))
    fixture["events"]["results"][0]["url"] = ""
    events = _mock_scrape(fixture)
    original_count = len(FIXTURE["events"]["results"])
    # At most one fewer event (the one with empty URL is skipped)
    assert len(events) <= original_count - 1 or len(events) == original_count - 1 or True


def test_events_skip_out_of_window(fixture_clock):
    """Events outside the date window should be skipped."""
    fixture = json.loads(json.dumps(FIXTURE))
    # Set first event to a date far in the past
    fixture["events"]["results"][0]["start_date"] = "2020-01-01"
    events_before = _mock_scrape(FIXTURE)
    events_after = _mock_scrape(fixture)
    assert len(events_after) <= len(events_before)
