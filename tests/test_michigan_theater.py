"""Tests for the Michigan Theater (Marquee Arts) scraper."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from scrapers.base import is_in_window

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "michigan_theater.html"
FIXTURE = FIXTURE_PATH.read_text(encoding="utf-8")


def _make_mock_session(text):
    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.content = text.encode("utf-8")
    mock_sess.get.return_value = mock_resp
    return mock_sess


def test_scrape_returns_list():
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        assert isinstance(scrape(), list)


def test_scrape_returns_events():
    """Fixture has 4 in-window events (3 Michigan Theater + 1 State Theatre with 3 showings)."""
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        # 3 MT events + 3 Bride showings = 6 in-window events
        assert len(events) >= 4


def test_scrape_source_and_category():
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        for e in events:
            assert e["source"] == "michigan_theater"
            assert e["category"] == "arts_culture"


def test_scrape_events_in_window():
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        for e in scrape():
            assert is_in_window(e["date"]), f"Event {e['title']} date {e['date']} not in window"


def test_scrape_event_fields():
    """Each event must have required fields with non-empty values."""
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        assert len(events) > 0
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"], f"Missing url: {e}"
            assert e["venue"], f"Missing venue: {e}"
            assert e["source"] == "michigan_theater"
            assert e["category"] == "arts_culture"


def test_scrape_out_of_window_excluded():
    """The fixture has one event in May 2026 that is outside the 30-day window."""
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        # "Ann Arbor Concert Band: Favorites 2.0" is on 2026-05-09, outside window
        assert not any("Favorites 2.0" in t for t in titles), (
            "Out-of-window event should be excluded"
        )


def test_scrape_venue_populated():
    """Venue field should come from the event data (fixture has MT and State Theatre)."""
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        venues = {e["venue"] for e in events}
        assert "Michigan Theater" in venues
        assert "State Theatre" in venues


def test_scrape_url_is_ticket_link():
    """URLs should point to the tix.marquee-arts.org ticket system."""
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        for e in events:
            assert "tix.marquee-arts.org" in e["url"], (
                f"URL does not point to tix.marquee-arts.org: {e['url']}"
            )


def test_scrape_multiple_showings_produce_multiple_events():
    """The Bride has 3 showings on the same day; each should be a separate event."""
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        bride_events = [e for e in events if "Bride" in e["title"]]
        assert len(bride_events) == 3, (
            f"Expected 3 showings of The Bride, got {len(bride_events)}"
        )
