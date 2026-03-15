# tests/test_blind_pig.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "blind_pig.html").read_text(encoding="utf-8")


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        result = scrape()
        assert isinstance(result, list)


def test_events_source_and_category():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        for e in scrape():
            assert e["source"] == "blind_pig"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        events = scrape()
        for e in events:
            assert is_in_window(e["date"]), f"Event out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        events = scrape()
        assert len(events) > 0, "Expected at least one event in window"
        for e in events:
            assert e["title"]
            assert e["url"].startswith("http")
            assert e["date"]
            assert e["venue"] == "The Blind Pig"


def test_events_have_music_tag():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        events = scrape()
        if events:
            assert "music" in events[0]["tags"]
