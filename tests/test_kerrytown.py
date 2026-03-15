# tests/test_kerrytown.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "kerrytown.ics").read_bytes()


def _mock_session(content_bytes):
    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = content_bytes
    mock_sess.get.return_value = mock_resp
    return mock_sess


def test_scrape_returns_list():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        assert isinstance(scrape(), list)


def test_scrape_events_have_required_fields():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        events = scrape()
        assert len(events) > 0, "Expected at least one event in fixture"
        e = events[0]
        assert e["source"] == "kerrytown"
        assert e["category"] == "arts_culture"
        assert e["url"].startswith("http")
        assert e["date"]
        assert e["title"]


def test_events_source():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        for e in scrape():
            assert e["source"] == "kerrytown"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        events = scrape()
        for e in events:
            assert is_in_window(e["date"]), f"Event out of window: {e['date']}"


def test_events_have_valid_urls():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        for e in scrape():
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
