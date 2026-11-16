from datetime import date
from unittest.mock import MagicMock

from scrapers import riverside


def event(day, **overrides):
    item = {
        "title": "Riverside&#8217;s Ypsi Fine Arts Club",
        "url": f"https://www.riversidearts.org/event/club/2026-11-{day:02d}/",
        "start_date": f"2026-11-{day:02d} 17:00:00",
        "all_day": False,
        "venue": {"venue": "Off Center", "address": "76 North Huron", "city": "Ypsilanti", "state": "MI", "zip": "48197"},
        "image": {"url": "https://www.riversidearts.org/image.png"},
        "excerpt": "<p>Meet &amp; create.</p>",
    }
    item.update(overrides)
    return item


def test_scrape_paginates_and_preserves_occurrences(monkeypatch):
    monkeypatch.setattr(riverside, "local_today", lambda: date(2026, 11, 15))
    monkeypatch.setattr("scrapers.base.local_today", lambda: date(2026, 11, 15))
    session = MagicMock()
    session.get.side_effect = [
        MagicMock(json=lambda: {"events": [event(18)], "total_pages": 2}),
        MagicMock(json=lambda: {"events": [event(25), event(26, all_day=True)], "total_pages": 2}),
    ]
    monkeypatch.setattr(riverside, "RateLimitedSession", lambda: session)

    events = riverside.scrape()

    assert [e["date"] for e in events] == ["2026-11-18", "2026-11-25", "2026-11-26"]
    assert [e["time"] for e in events] == ["5:00 PM", "5:00 PM", ""]
    assert events[0]["title"] == "Riverside’s Ypsi Fine Arts Club"
    assert events[0]["url"].endswith("/2026-11-18/")
    assert events[0]["source"] == "riverside"
    assert events[0]["category"] == "arts_culture"
    assert events[0]["venue"] == "Off Center"
    assert events[0]["address"] == "76 North Huron, Ypsilanti, MI, 48197"
    assert events[0]["image_url"].endswith("image.png")
    assert events[0]["description"] == "Meet & create."
    assert session.get.call_count == 2
    assert session.get.call_args_list[0].kwargs["params"] == {
        "start_date": "2026-11-15", "end_date": "2026-12-15", "per_page": 50, "page": 1,
    }
    assert session.get.call_args_list[1].kwargs["params"]["page"] == 2


def test_scrape_skips_invalid_and_out_of_window_events(monkeypatch):
    monkeypatch.setattr(riverside, "local_today", lambda: date(2026, 11, 15))
    monkeypatch.setattr("scrapers.base.local_today", lambda: date(2026, 11, 15))
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "events": [event(14), event(18, start_date="invalid"), event(18, title=""), event(18, url=""), event(19, venue=None, image=False)],
        "total_pages": 1,
    }
    monkeypatch.setattr(riverside, "RateLimitedSession", lambda: session)
    events = riverside.scrape()
    assert len(events) == 1
    assert events[0]["date"] == "2026-11-19"
    assert events[0]["venue"] == ""
    assert events[0]["image_url"] is None
