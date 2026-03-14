# tests/test_ark.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "ark.ics").read_bytes()


def _mock_session(content_bytes):
    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = content_bytes
    mock_sess.get.return_value = mock_resp
    return mock_sess


def test_scrape_returns_list():
    with patch("scrapers.ark.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.ark import scrape
        assert isinstance(scrape(), list)


def test_scrape_events_have_required_fields():
    with patch("scrapers.ark.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.ark import scrape
        events = scrape()
        if events:
            e = events[0]
            assert e["source"] == "ark"
            assert e["category"] == "arts_culture"
            assert e["url"].startswith("http")
            assert e["date"]


def test_scrape_events_in_window():
    with patch("scrapers.ark.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.ark import scrape
        events = scrape()
        for e in events:
            assert is_in_window(e["date"]), f"Event out of window: {e['date']}"


def test_scrape_events_have_music_tag():
    with patch("scrapers.ark.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.ark import scrape
        events = scrape()
        if events:
            assert "music" in events[0]["tags"]
