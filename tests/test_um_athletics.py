# tests/test_um_athletics.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "um_athletics.ics").read_bytes()


def _mock_session(content_bytes):
    sess = MagicMock()
    resp = MagicMock()
    resp.content = content_bytes
    resp.raise_for_status = MagicMock()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        for e in scrape():
            assert e["source"] == "um_athletics"
            assert e["category"] == "um_athletics"


def test_events_in_window():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        for e in scrape():
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


def test_url_fallback_for_events_without_url():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        events = scrape()
        for e in events:
            assert e["url"].startswith("http"), f"Empty or invalid URL: {e['url']}"


def test_events_have_sport_tag():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        events = scrape()
        if events:
            assert len(events[0]["tags"]) > 0, "Expected at least one sport tag"
