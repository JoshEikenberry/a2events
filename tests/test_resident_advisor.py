"""Tests for the Resident Advisor scraper."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.base import is_in_window

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "resident_advisor.json").read_text()
)


def _make_mock_post(fixture=FIXTURE):
    mock_resp = MagicMock()
    mock_resp.json.return_value = fixture
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def test_scrape_returns_list():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        result = scrape()
        assert isinstance(result, list)


def test_events_source_and_category():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        assert len(events) > 0
        for e in events:
            assert e["source"] == "resident_advisor"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        for e in events:
            assert is_in_window(e["date"]), f"Event date out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        for e in events:
            assert e["title"]
            assert e["date"]
            assert e["url"]
            assert e["venue"]


def test_skips_out_of_window_events():
    """Event with date 2020-01-01 should be excluded."""
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        dates = [e["date"] for e in events]
        assert "2020-01-01" not in dates


def test_skips_events_with_empty_url():
    """Event with empty contentUrl should be excluded."""
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert "No URL Event" not in titles


def test_events_have_music_tags():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        for e in events:
            assert "music" in e["tags"]
            assert "electronic" in e["tags"]


def test_scrape_handles_empty_response():
    empty_fixture = {"data": {"eventListings": {"data": []}}}
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post(empty_fixture)
        from scrapers.resident_advisor import scrape
        result = scrape()
        assert result == []


def test_event_url_format():
    """URLs should be full ra.co URLs."""
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_post.return_value = _make_mock_post()
        from scrapers.resident_advisor import scrape
        events = scrape()
        for e in events:
            assert e["url"].startswith("https://ra.co/"), f"Bad URL: {e['url']}"
