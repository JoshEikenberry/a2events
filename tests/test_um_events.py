import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "um_events.json").read_text())


def _mock_get(fixture_data):
    mock_resp = MagicMock()
    mock_resp.json.return_value = fixture_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_scrape_returns_list():
    with patch("scrapers.um_events.requests.get") as mock_get:
        mock_get.return_value = _mock_get(FIXTURE)
        from scrapers.um_events import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category():
    with patch("scrapers.um_events.requests.get") as mock_get:
        mock_get.return_value = _mock_get(FIXTURE)
        from scrapers.um_events import scrape
        for e in scrape():
            assert e["source"] == "um_events"
            assert e["category"] == "university_of_michigan"


def test_events_in_window():
    with patch("scrapers.um_events.requests.get") as mock_get:
        mock_get.return_value = _mock_get(FIXTURE)
        from scrapers.um_events import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.um_events.requests.get") as mock_get:
        mock_get.return_value = _mock_get(FIXTURE)
        from scrapers.um_events import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "um_events"
            assert e["category"] == "university_of_michigan"
