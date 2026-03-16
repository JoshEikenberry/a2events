# tests/test_washtenaw_county.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "washtenaw_county.html").read_text()

MEETING_KEYWORDS = ["council", "commission", "board", "committee", "meeting", "hearing"]


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.washtenaw_county.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.washtenaw_county import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category():
    with patch("scrapers.washtenaw_county.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.washtenaw_county import scrape
        for e in scrape():
            assert e["source"] == "washtenaw_county"
            assert e["category"] == "washtenaw_county"


def test_events_in_window():
    with patch("scrapers.washtenaw_county.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.washtenaw_county import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


def test_events_have_required_fields():
    with patch("scrapers.washtenaw_county.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.washtenaw_county import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "washtenaw_county"
            assert e["category"] == "washtenaw_county"


def test_meeting_events_are_tagged():
    with patch("scrapers.washtenaw_county.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.washtenaw_county import scrape
        events = scrape()
        assert len(events) >= 1, "Fixture must contain at least one in-window event"
        meeting_events = [e for e in events if "public_meeting" in e["tags"]]
        assert len(meeting_events) >= 1, "Fixture must contain at least one meeting-tagged event"
        for e in events:
            title_lower = e["title"].lower()
            if any(k in title_lower for k in MEETING_KEYWORDS):
                assert "public_meeting" in e["tags"], f"Expected meeting tag on: {e['title']}"
