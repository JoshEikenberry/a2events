"""Tests for Conor O'Neill's scraper."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrapers.base import is_in_window

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "conor_oneills.json"
FIXTURE = FIXTURE_PATH.read_text(encoding="utf-8")


def _mock_session(text):
    """Return a mock RateLimitedSession whose .get() returns a response with .json()."""
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode("utf-8")
    resp.json.return_value = json.loads(text)
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        for e in scrape():
            assert e["source"] == "conor_oneills"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        for e in scrape():
            assert is_in_window(e["date"]), f"Event out of window: {e['date']} ({e['title']})"


def test_events_have_required_fields():
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


def test_out_of_window_events_excluded():
    """Fixture contains a May 2026 event that is outside the 30-day window."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert not any("Summer Kickoff" in t for t in titles), (
            "Out-of-window event should be excluded"
        )


def test_past_out_of_window_excluded():
    """Fixture contains a past event (March 14) that should be excluded."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert not any("St. Practice Day" in t for t in titles), (
            "Past event outside window should be excluded"
        )


def test_event_url_is_absolute():
    """All event URLs must be absolute (start with http)."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        events = scrape()
        for e in events:
            assert e["url"].startswith("http"), f"URL not absolute: {e['url']}"


def test_scrape_returns_list_on_error():
    """If the HTTP request fails, scrape() returns an empty list rather than raising."""
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        sess = MagicMock()
        sess.get.side_effect = Exception("network error")
        cls.return_value = sess
        from scrapers.conor_oneills import scrape
        result = scrape()
        assert isinstance(result, list)
        assert len(result) == 0
