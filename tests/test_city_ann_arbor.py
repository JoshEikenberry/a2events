"""Tests for the City of Ann Arbor calendar scraper."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.base import is_in_window

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "city_ann_arbor.json"
FIXTURE_DATA = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _mock_response(json_data):
    """Build a mock requests.Response returning json_data."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def test_scrape_returns_list():
    with patch("scrapers.city_ann_arbor.requests.get", return_value=_mock_response(FIXTURE_DATA)):
        from scrapers.city_ann_arbor import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category():
    with patch("scrapers.city_ann_arbor.requests.get", return_value=_mock_response(FIXTURE_DATA)):
        from scrapers.city_ann_arbor import scrape
        for e in scrape():
            assert e["source"] == "city_ann_arbor"
            assert e["category"] == "city_ann_arbor"


def test_events_in_window():
    with patch("scrapers.city_ann_arbor.requests.get", return_value=_mock_response(FIXTURE_DATA)):
        from scrapers.city_ann_arbor import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.city_ann_arbor.requests.get", return_value=_mock_response(FIXTURE_DATA)):
        from scrapers.city_ann_arbor import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "city_ann_arbor"
            assert e["category"] == "city_ann_arbor"


def test_public_meeting_tag():
    with patch("scrapers.city_ann_arbor.requests.get", return_value=_mock_response(FIXTURE_DATA)):
        from scrapers.city_ann_arbor import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        meeting_events = [e for e in events if "public_meeting" in e["tags"]]
        assert len(meeting_events) >= 1, "Fixture must contain at least one meeting-tagged event"
