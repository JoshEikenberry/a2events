from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scrapers import sun_times_news

FIXTURES = Path(__file__).parent / "fixtures"
PAGE1 = (FIXTURES / "sun_times_news_page1.html").read_text(encoding="utf-8")
PAGE2 = (FIXTURES / "sun_times_news_page2.html").read_text(encoding="utf-8")


def _session(*pages):
    session = MagicMock()
    session.get.side_effect = [MagicMock(text=page) for page in pages]
    return session


def test_paginated_events_and_no_inferred_occurrences():
    session = _session(PAGE1, PAGE2)
    with patch.object(sun_times_news, "RateLimitedSession", return_value=session), patch.object(
        sun_times_news, "local_today", return_value=date(2026, 11, 15)
    ):
        events = sun_times_news.scrape()
    assert [(event["title"], event["date"], event["time"]) for event in events] == [
        ("Morning Movement", "2026-11-16", "07:00"),
        ("GriefShare", "2026-11-19", "18:30"),
    ]
    assert events[0]["venue"] == "Champion Gymnastics"
    assert events[0]["address"] == "2362 Bishop Circle E., Dexter, M, United States"
    assert events[0]["description"] == "Morning movement is for Seniors 55 and older."
    assert events[1]["address"] == ""
    assert all(e["source"] == "sun_times_news" and e["category"] == "community" for e in events)
    assert session.get.call_args_list[1].args[0].endswith("/page/2/?hide_subsequent_recurrences=1")


def test_window_boundary_and_all_day():
    page = PAGE2.replace("2026-11-19", "2026-12-15").replace(
        "November 19 @ 6:30 pm", "December 15"
    )
    session = _session(page)
    with patch.object(sun_times_news, "RateLimitedSession", return_value=session), patch.object(
        sun_times_news, "local_today", return_value=date(2026, 11, 15)
    ):
        events = sun_times_news.scrape()
    assert len(events) == 1
    assert events[0]["date"] == "2026-12-15"
    assert events[0]["time"] == ""


def test_rejects_missing_calendar_and_pagination_loop():
    with patch.object(sun_times_news, "RateLimitedSession", return_value=_session("not a calendar")):
        with pytest.raises(ValueError, match="list not found"):
            sun_times_news.scrape()
    loop = PAGE1.replace(
        "https://thesuntimesnews.com/events/list/page/2/?hide_subsequent_recurrences=1",
        sun_times_news.CALENDAR_URL,
    )
    with patch.object(sun_times_news, "RateLimitedSession", return_value=_session(loop)), patch.object(
        sun_times_news, "local_today", return_value=date(2026, 11, 15)
    ):
        with pytest.raises(ValueError, match="pagination loop"):
            sun_times_news.scrape()


def test_stops_after_page_beyond_window():
    future = PAGE1.replace("2026-11-16", "2026-12-16")
    # Both date tags must be beyond the window before pagination may stop.
    session = _session(future)
    with patch.object(sun_times_news, "RateLimitedSession", return_value=session), patch.object(
        sun_times_news, "local_today", return_value=date(2026, 11, 15)
    ):
        assert sun_times_news.scrape() == []
    assert session.get.call_count == 1
