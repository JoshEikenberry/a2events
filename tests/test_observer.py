"""Tests for the Ann Arbor Observer scraper."""
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = (Path(__file__).parent / "fixtures" / "observer.html").read_text(encoding="utf-8")


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        result = observer.scrape()
        assert isinstance(result, list)


def test_events_source():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        for e in observer.scrape():
            assert e["source"] == "observer"
            assert e["category"] == "community"


def test_events_in_window():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        from scrapers.base import is_in_window
        for e in observer.scrape():
            assert is_in_window(e["date"]), f"Event date {e['date']} out of window"


def test_events_have_required_fields():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        events = observer.scrape()
        for e in events:
            assert "title" in e and e["title"]
            assert "date" in e and e["date"]
            assert "url" in e and e["url"]
            assert e["url"].startswith("http")


def test_events_no_duplicates():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        events = observer.scrape()
        ids = [e["id"] for e in events]
        assert len(ids) == len(set(ids)), "Duplicate event IDs found"
