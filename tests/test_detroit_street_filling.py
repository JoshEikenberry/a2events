"""Tests for the Detroit Street Filling Station / North Star Lounge scraper."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "detroit_street_filling.json"
FIXTURE_BYTES = FIXTURE_PATH.read_bytes()
FIXTURE_TEXT = FIXTURE_BYTES.decode("utf-8")


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode() if isinstance(text, str) else text
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_TEXT)
        import importlib
        import scrapers.detroit_street_filling as mod
        importlib.reload(mod)
        result = mod.scrape()
        assert isinstance(result, list)


def test_events_source():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_TEXT)
        import importlib
        import scrapers.detroit_street_filling as mod
        importlib.reload(mod)
        events = mod.scrape()
        assert len(events) > 0, "Expected at least one event in fixture"
        for e in events:
            assert e["source"] == "detroit_street_filling"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_TEXT)
        import importlib
        import scrapers.detroit_street_filling as mod
        importlib.reload(mod)
        from scrapers.base import is_in_window
        for e in mod.scrape():
            assert is_in_window(e["date"]), f"Event date {e['date']} is out of window"


def test_events_have_required_fields():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_TEXT)
        import importlib
        import scrapers.detroit_street_filling as mod
        importlib.reload(mod)
        for e in mod.scrape():
            assert e.get("title"), "Event must have a title"
            assert e.get("date"), "Event must have a date"
            assert e.get("url"), "Event must have a url"
            assert e.get("venue"), "Event must have a venue"


def test_events_url_is_absolute():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE_TEXT)
        import importlib
        import scrapers.detroit_street_filling as mod
        importlib.reload(mod)
        for e in mod.scrape():
            assert e["url"].startswith("http"), f"URL should be absolute: {e['url']}"


def test_empty_upcoming_returns_empty_list():
    empty_data = {"upcoming": [], "past": []}
    empty_text = json.dumps(empty_data)
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(empty_text)
        from scrapers.detroit_street_filling import scrape
        result = scrape()
        assert result == []
