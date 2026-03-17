"""Tests for the Eastern Michigan University events scraper (today.emich.edu JSON API)."""
import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scrapers.base import is_in_window

# Primary fixture: week-0 API response with 2 valid events + 1 cancelled
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "eastern_michigan.json").read_text()
)

# Fixture was captured on this date; pin today() so in-window checks are stable.
FIXTURE_DATE = datetime.date(2026, 3, 17)

EMPTY_RESPONSE = {"groupedByDay": {}}

# Week-1 response: duplicate of event 1001 (same id) + out-of-window event
WEEK1_RESPONSE = {
    "groupedByDay": {
        "2026-3-24": [
            {
                "id": 1001,
                "title": "Earth Day Campus Cleanup",
                "location": "Student Center",
                "start_date": "2026-03-17 00:00:00",
                "start_time": "10:00am",
                "is_canceled": False,
                "description": "Duplicate — same id as week-0 event.",
            },
            {
                "id": 1099,
                "title": "Far Future Symposium",
                "location": "Convocation Center",
                "start_date": "2026-05-30 00:00:00",
                "start_time": "7:00pm",
                "is_canceled": False,
                "description": "Out of 30-day window.",
            },
        ]
    }
}


def _patch_today():
    """Patch scrapers.base.date.today() to return FIXTURE_DATE."""
    mock_date = MagicMock(wraps=datetime.date)
    mock_date.today.return_value = FIXTURE_DATE
    return patch("scrapers.base.date", mock_date)


def _mock_session(*responses):
    """Return a mock RateLimitedSession whose .get().json() returns responses in order."""
    sess = MagicMock()
    mocks = []
    for data in responses:
        resp = MagicMock()
        resp.json.return_value = data
        mocks.append(resp)
    sess.get.side_effect = mocks
    return sess


def _session_five_weeks(week0=None, week1=None):
    """Build a 5-call mock: week0 and week1 as given, weeks 2-4 empty."""
    if week0 is None:
        week0 = FIXTURE
    if week1 is None:
        week1 = EMPTY_RESPONSE
    return _mock_session(week0, week1, EMPTY_RESPONSE, EMPTY_RESPONSE, EMPTY_RESPONSE)


def test_scrape_returns_list():
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks()
        from scrapers.eastern_michigan import scrape
        assert isinstance(scrape(), list)


def test_scrape_source_and_category():
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks()
        from scrapers.eastern_michigan import scrape
        events = scrape()
        assert len(events) >= 1
        for e in events:
            assert e["source"] == "eastern_michigan"
            assert e["category"] == "eastern_michigan"


def test_scrape_events_in_window():
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks()
        from scrapers.eastern_michigan import scrape
        events = scrape()
        assert len(events) >= 1
        for e in events:
            assert is_in_window(e["date"]), f"Out of window: {e['date']} — {e['title']}"


def test_scrape_required_fields():
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks()
        from scrapers.eastern_michigan import scrape
        events = scrape()
        assert len(events) >= 1
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "eastern_michigan"
            assert e["category"] == "eastern_michigan"


def test_scrape_cancelled_excluded():
    """Event with is_canceled=True must be skipped."""
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks()
        from scrapers.eastern_michigan import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert "Cancelled Lecture" not in titles, "Cancelled event should be excluded"


def test_scrape_out_of_window_excluded():
    """Event dated 2026-05-30 is outside the 30-day window and must be excluded."""
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks(week1=WEEK1_RESPONSE)
        from scrapers.eastern_michigan import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert "Far Future Symposium" not in titles, "Out-of-window event should be excluded"


def test_scrape_deduplication():
    """Event appearing in multiple weekly responses should only be returned once."""
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        cls.return_value = _session_five_weeks(week1=WEEK1_RESPONSE)
        from scrapers.eastern_michigan import scrape
        events = scrape()
        cleanup_events = [e for e in events if e["title"] == "Earth Day Campus Cleanup"]
        assert len(cleanup_events) == 1, (
            f"Expected 1 occurrence after deduplication, got {len(cleanup_events)}"
        )


def test_scrape_makes_five_calls():
    """Scraper must make exactly 5 HTTP calls to cover the 30-day window."""
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        sess = _session_five_weeks()
        cls.return_value = sess
        from scrapers.eastern_michigan import scrape
        scrape()
        assert sess.get.call_count == 5, (
            f"Expected 5 API calls, got {sess.get.call_count}"
        )


def test_scrape_fetch_error_continues():
    """A failed API call should be skipped; other weeks still return events."""
    with _patch_today(), patch("scrapers.eastern_michigan.RateLimitedSession") as cls:
        sess = MagicMock()
        # Week 0 raises, weeks 1-4 return valid/empty data
        ok_resp = MagicMock()
        ok_resp.json.return_value = FIXTURE
        sess.get.side_effect = [
            Exception("connection error"),
            ok_resp,
            MagicMock(**{"json.return_value": EMPTY_RESPONSE}),
            MagicMock(**{"json.return_value": EMPTY_RESPONSE}),
            MagicMock(**{"json.return_value": EMPTY_RESPONSE}),
        ]
        cls.return_value = sess
        from scrapers.eastern_michigan import scrape
        events = scrape()
        assert isinstance(events, list)
        assert len(events) >= 1
