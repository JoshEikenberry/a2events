# tests/test_blue_llama.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "blue_llama.ics").read_bytes()


def _mock_session(content_bytes):
    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = content_bytes
    mock_sess.get.return_value = mock_resp
    return mock_sess


def test_scrape_returns_list():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        events = scrape()
        if events:
            for e in events:
                assert e["source"] == "blue_llama"
                assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        events = scrape()
        for e in events:
            assert is_in_window(e["date"]), f"Event out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        events = scrape()
        if events:
            e = events[0]
            assert e["venue"] == "Blue Llama Jazz Club"
            assert e["url"].startswith("http")
            assert e["date"]
            assert "music" in e["tags"]
            assert "jazz" in e["tags"]
