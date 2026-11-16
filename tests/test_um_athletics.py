# tests/test_um_athletics.py
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "um_athletics.ics").read_bytes()


def _mock_session(content_bytes):
    sess = MagicMock()
    resp = MagicMock()
    resp.content = content_bytes
    resp.raise_for_status = MagicMock()
    sess.get.return_value = resp
    return sess


@patch("scrapers.base.local_today", new=lambda: date(2026, 3, 15))
def test_scrape_returns_list():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        assert isinstance(scrape(), list)


@patch("scrapers.base.local_today", new=lambda: date(2026, 3, 15))
def test_events_source_and_category():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        for e in scrape():
            assert e["source"] == "um_athletics"
            assert e["category"] == "um_athletics"


@patch("scrapers.base.local_today", new=lambda: date(2026, 3, 15))
def test_events_in_window():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        for e in scrape():
            assert is_in_window(e["date"]), f"Out of window: {e['date']}"


@patch("scrapers.base.local_today", new=lambda: date(2026, 3, 15))
def test_url_fallback_for_events_without_url():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        events = scrape()
        for e in events:
            assert e["url"].startswith("http"), f"Empty or invalid URL: {e['url']}"
        # Events from VEVENTs with URL fields should have event-specific URLs
        explicit_url_events = [e for e in events if "/events/" in e["url"]]
        assert len(explicit_url_events) >= 1, "Expected at least one event with an explicit event URL"
        # Events from the no-URL VEVENT should use the fallback (schedule page)
        fallback_events = [e for e in events if e["title"] == "Women's Basketball vs Penn State"]
        assert len(fallback_events) >= 1, "Expected at least one no-URL event to be present"
        for e in fallback_events:
            assert e["url"].startswith("https://mgoblue.com/sports/"), \
                f"Expected fallback schedule URL, got: {e['url']}"


@patch("scrapers.base.local_today", new=lambda: date(2026, 3, 15))
def test_events_have_sport_tag():
    with patch("scrapers.um_athletics.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.um_athletics import scrape
        events = scrape()
        if events:
            assert len(events[0]["tags"]) > 0, "Expected at least one sport tag"


@pytest.mark.parametrize(("dtstart", "expected_date", "expected_time"), [
    ("DTSTART:20260102T023000Z", "2026-01-01", "9:30 PM"),
    ("DTSTART:20260702T023000Z", "2026-07-01", "10:30 PM"),
    ("DTSTART;TZID=America/Los_Angeles:20260701T193000", "2026-07-01", "10:30 PM"),
    ("DTSTART:20260701T193000", "2026-07-01", "7:30 PM"),
    ("DTSTART;VALUE=DATE:20260701", "2026-07-01", ""),
])
def test_ical_detroit_date_time_and_floating_semantics(dtstart, expected_date, expected_time):
    from scrapers.um_athletics import _parse_sport_ical
    ical = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        f"UID:test\r\nSUMMARY:Game\r\n{dtstart}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode()
    with patch("scrapers.um_athletics.is_in_window", return_value=True) as in_window:
        events = _parse_sport_ical(ical, "football", "https://mgoblue.com/schedule")
    in_window.assert_called_once_with(expected_date)
    assert [(event["date"], event["time"]) for event in events] == [(expected_date, expected_time)]


def test_empty_ical_feed_is_valid():
    from scrapers.um_athletics import _parse_sport_ical
    assert _parse_sport_ical(
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n",
        "football", "https://mgoblue.com/schedule",
    ) == []


def test_invalid_ical_event_propagates():
    from scrapers.um_athletics import _parse_sport_ical
    ical = (
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        b"UID:test\r\nSUMMARY:Game\r\nDTSTART:invalid\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    with pytest.raises(ValueError, match="Invalid football iCalendar event"):
        _parse_sport_ical(ical, "football", "https://mgoblue.com/schedule")


@pytest.mark.parametrize("failure", ["fetch", "parse"])
def test_partial_sport_failure_propagates(failure):
    from scrapers.um_athletics import scrape
    sports = {"first": ("https://example.com/first", "https://example.com"),
              "second": ("https://example.com/second", "https://example.com")}
    with patch("scrapers.um_athletics.SPORTS", sports), \
         patch("scrapers.um_athletics.RateLimitedSession") as cls, \
         patch("scrapers.um_athletics._parse_sport_ical") as parse:
        if failure == "fetch":
            cls.return_value.get.side_effect = [MagicMock(content=FIXTURE), RuntimeError("feed failed")]
            parse.return_value = [{"title": "First"}]
        else:
            cls.return_value.get.return_value.content = FIXTURE
            parse.side_effect = [[{"title": "First"}], RuntimeError("feed failed")]
        with pytest.raises(RuntimeError, match="feed failed"):
            scrape()
