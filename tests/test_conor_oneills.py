"""Tests for Conor O'Neill's scraper."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import date, datetime

import pytest

from scrapers.base import is_in_window

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "conor_oneills.json"
FIXTURE = FIXTURE_PATH.read_text(encoding="utf-8")

@pytest.fixture
def fixture_clock():
    with patch("scrapers.base.local_today", return_value=date(2026, 3, 16)):
        yield


def _mock_session(text):
    """Return a mock RateLimitedSession whose .get() returns a response with .json()."""
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode("utf-8")
    resp.json.return_value = json.loads(text)
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list(fixture_clock):
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        assert isinstance(scrape(), list)


def test_events_source(fixture_clock):
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        for e in scrape():
            assert e["source"] == "conor_oneills"
            assert e["category"] == "arts_culture"


def test_events_in_window(fixture_clock):
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        for e in scrape():
            assert is_in_window(e["date"]), f"Event out of window: {e['date']} ({e['title']})"


def test_events_have_required_fields(fixture_clock):
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        assert len(events) > 0, "Expected at least one in-window event from fixture"
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"], f"Missing url: {e}"
            assert e["venue"] == "Conor O'Neill's"
            assert e["source"] == "conor_oneills"
            assert e["category"] == "arts_culture"


def test_out_of_window_events_excluded(fixture_clock):
    """Fixture contains a May 2026 event that is outside the 30-day window."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert not any("Summer Kickoff" in t for t in titles), (
            "Out-of-window event should be excluded"
        )


def test_past_out_of_window_excluded(fixture_clock):
    """Fixture contains a past event (March 14) that should be excluded."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert not any("St. Practice Day" in t for t in titles), (
            "Past event outside window should be excluded"
        )


def test_event_url_is_absolute(fixture_clock):
    """All event URLs must be absolute (start with http)."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        for e in events:
            assert e["url"].startswith("http"), f"URL not absolute: {e['url']}"


def test_scrape_propagates_fetch_failure():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value.get.side_effect = RuntimeError("network error")
        from scrapers.conor_oneills import scrape
        with pytest.raises(RuntimeError, match="network error"):
            scrape()


@pytest.mark.parametrize(("utc_start", "expected_date", "expected_time"), [
    ("2026-01-02T02:30:00+00:00", "2026-01-01", "9:30 PM"),
    ("2026-07-02T02:30:00+00:00", "2026-07-01", "10:30 PM"),
])
def test_scrape_uses_detroit_date_and_time(utc_start, expected_date, expected_time):
    from scrapers.conor_oneills import scrape
    start_ms = int(datetime.fromisoformat(utc_start).timestamp() * 1000)
    data = {"upcoming": [{"title": "Music", "startDate": start_ms, "fullUrl": "/events/music"}]}
    with patch("scrapers.conor_oneills.RateLimitedSession", return_value=_mock_session(json.dumps(data))), \
         patch("scrapers.conor_oneills.is_in_window", return_value=True) as in_window:
        events = scrape()
    in_window.assert_called_once_with(expected_date)
    assert [(event["date"], event["time"]) for event in events] == [(expected_date, expected_time)]


def test_empty_sections_are_valid():
    from scrapers.conor_oneills import scrape
    with patch("scrapers.conor_oneills.RateLimitedSession", return_value=_mock_session('{"upcoming": [], "past": []}')):
        assert scrape() == []


@pytest.mark.parametrize("data", [
    {},
    {"upcoming": [], "past": None},
    {"upcoming": [{"title": "Bad", "startDate": "invalid", "fullUrl": "/events/bad"}]},
])
def test_invalid_response_or_partial_event_propagates(data):
    from scrapers.conor_oneills import scrape
    with patch("scrapers.conor_oneills.RateLimitedSession", return_value=_mock_session(json.dumps(data))):
        with pytest.raises((TypeError, ValueError)):
            scrape()
