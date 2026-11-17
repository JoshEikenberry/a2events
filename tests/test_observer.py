"""Deterministic tests for the Observer's public events API."""
from datetime import date
from unittest.mock import MagicMock

import pytest

from scrapers import observer


def _record(event_id, day, **overrides):
    event = {
        "id": event_id,
        "title": "Paul Keller Orchestra.",
        "url": f"https://annarborobserver.com/event/paul-keller-orchestra/{day}/",
        "start_date": f"{day} 19:00:00",
        "all_day": False,
        "description": "<p>Award-winning <b>big band</b> &amp; guests.</p>",
        "venue": {"venue": "Zal Gaz Grotto", "address": "2070 W. Stadium",
                  "city": "Ann Arbor"},
        "categories": [{"name": "Nightspots", "slug": "nightspot"}],
        "hide_from_listings": False,
    }
    event.update(overrides)
    return event


def _page(events, total, pages):
    return {"events": events, "total": total, "total_pages": pages}


def _session(monkeypatch, *pages):
    session = MagicMock()
    responses = []
    for page in pages:
        response = MagicMock()
        response.json.return_value = page
        responses.append(response)
    session.get.side_effect = responses
    monkeypatch.setattr(observer, "RateLimitedSession", lambda: session)
    monkeypatch.setattr(observer, "local_today", lambda: date(2026, 11, 16))
    return session


def test_full_window_pagination_and_recurring_occurrences(monkeypatch):
    first = _record(101, "2026-11-16")
    later = _record(102, "2026-12-16")
    outside = _record(103, "2026-12-17")
    hidden = _record(104, "2026-11-20", hide_from_listings=True)
    session = _session(monkeypatch, _page([first, hidden], 4, 2),
                       _page([later, outside], 4, 2))

    events = observer.scrape()
    assert [event["date"] for event in events] == ["2026-11-16", "2026-12-16"]
    assert events[0]["venue"] == "Zal Gaz Grotto"
    assert events[0]["address"] == "2070 W. Stadium, Ann Arbor"
    assert events[0]["time"] == "7:00 PM"
    assert events[0]["description"] == "Award-winning big band & guests."
    assert events[0]["tags"] == ["nightspot"]
    assert events[0]["source"] == "observer"
    assert events[0]["category"] == "community"
    assert events[0]["url"].endswith("/2026-11-16/")
    assert events[0]["id"] != events[1]["id"]
    assert session._delay == 600
    assert session.get.call_count == 2
    assert session.get.call_args_list[0].kwargs["params"] == {
        "start_date": "2026-11-16", "end_date": "2026-12-16",
        "per_page": 50, "page": 1,
    }
    assert session.get.call_args_list[1].kwargs["params"]["page"] == 2
    assert all(call.args[0] == observer.API_URL for call in session.get.call_args_list)


def test_empty_and_all_day_event(monkeypatch):
    _session(monkeypatch, _page([], 0, 0))
    assert observer.scrape() == []
    _session(monkeypatch, _page([_record(1, "2026-11-16", all_day=True,
                                        venue=[], categories=[])], 1, 1))
    event = observer.scrape()[0]
    assert event["time"] == ""
    assert event["venue"] == ""


@pytest.mark.parametrize("bad_page", [
    {},
    {"events": [], "total": 1, "total_pages": 1},
    {"events": [_record(1, "2026-11-16")], "total": 2, "total_pages": 1},
    {"events": [{"id": 1}], "total": 1, "total_pages": 1},
])
def test_invalid_response_fails_instead_of_empty(monkeypatch, bad_page):
    _session(monkeypatch, bad_page)
    with pytest.raises(ValueError):
        observer.scrape()


@pytest.mark.parametrize("second", [
    _page([], 2, 2),
    _page([_record(2, "2026-11-23")], 3, 2),
    _page([_record(1, "2026-11-16")], 2, 2),
])
def test_partial_or_changed_pagination_fails(monkeypatch, second):
    _session(monkeypatch, _page([_record(1, "2026-11-16")], 2, 2), second)
    with pytest.raises(ValueError):
        observer.scrape()


@pytest.mark.parametrize("failure", ["fetch", "http", "json"])
def test_later_page_failure_propagates(monkeypatch, failure):
    session = _session(monkeypatch, _page([_record(1, "2026-11-16")], 2, 2),
                       _page([_record(2, "2026-11-23")], 2, 2))
    responses = session.get.side_effect
    first = next(responses)
    second = next(responses)
    if failure == "fetch":
        session.get.side_effect = [first, RuntimeError("fetch failed")]
    else:
        session.get.side_effect = [first, second]
        getattr(second, "raise_for_status" if failure == "http" else "json").side_effect = RuntimeError("failed")
    with pytest.raises(RuntimeError, match="failed"):
        observer.scrape()
