# tests/test_eastern_michigan.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "eastern_michigan.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.eastern_michigan import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category():
    with patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.eastern_michigan import scrape
        for e in scrape():
            assert e["source"] == "eastern_michigan"
            assert e["category"] == "eastern_michigan"


def test_events_in_window():
    with patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.eastern_michigan import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.eastern_michigan import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "eastern_michigan"
            assert e["category"] == "eastern_michigan"


def test_returns_list_on_empty_page():
    """If no events can be parsed, return empty list rather than raising."""
    with patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _mock_session("<html><body>No events here.</body></html>")
        from scrapers.eastern_michigan import scrape
        result = scrape()
        assert isinstance(result, list)
        assert len(result) == 0
