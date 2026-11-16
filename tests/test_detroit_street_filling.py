"""Tests for the Detroit Street Filling Station / North Star Lounge scraper."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

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


@pytest.mark.parametrize(("utc_start", "expected_date", "expected_time"), [
    ("2026-01-02T02:30:00+00:00", "2026-01-01", "9:30 PM"),
    ("2026-07-02T02:30:00+00:00", "2026-07-01", "10:30 PM"),
])
def test_scrape_uses_detroit_date_and_time(utc_start, expected_date, expected_time):
    from scrapers.detroit_street_filling import scrape
    start_ms = int(datetime.fromisoformat(utc_start).timestamp() * 1000)
    data = {"upcoming": [{"title": "Music", "startDate": start_ms, "fullUrl": "/events/music"}]}
    with patch("scrapers.detroit_street_filling.RateLimitedSession", return_value=_mock_session(json.dumps(data))), \
         patch("scrapers.detroit_street_filling.is_in_window", return_value=True) as in_window:
        events = scrape()
    in_window.assert_called_once_with(expected_date)
    assert [(event["date"], event["time"]) for event in events] == [(expected_date, expected_time)]


@pytest.mark.parametrize("text", [
    "not json",
    "{}",
    '{"upcoming": null}',
    '{"upcoming": [{"title": "Bad", "startDate": "invalid", "fullUrl": "/bad"}]}',
])
def test_invalid_response_or_partial_event_propagates(text):
    from scrapers.detroit_street_filling import scrape
    with patch("scrapers.detroit_street_filling.RateLimitedSession", return_value=_mock_session(text)):
        with pytest.raises((TypeError, ValueError)):
            scrape()


def test_fetch_failure_propagates():
    from scrapers.detroit_street_filling import scrape
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value.get.side_effect = RuntimeError("network error")
        with pytest.raises(RuntimeError, match="network error"):
            scrape()
