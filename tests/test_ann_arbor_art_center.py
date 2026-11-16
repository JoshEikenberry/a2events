from datetime import date
from unittest.mock import patch

import pytest

from scrapers import ann_arbor_art_center as art_center


def _item(title, start, **changes):
    return {
        "title": title, "start_date": start, "url": "https://example.com/" + title,
        "status": "publish", "categories": [], "all_day": False,
        "venue": {"venue": "Gallery", "address": "117 W Liberty", "city": "Ann Arbor", "state": "MI"},
        "description": "<p>Public event</p>", **changes,
    }


def test_scrape_paginates_and_filters_public_start_dates():
    first = [
        _item("Reception", "2026-11-20 18:00:00"),
        _item("Classes open", "2026-12-02 07:00:00",
              categories=[{"name": "Education Term Launches"}]),
        _item("Members-only preview", "2026-12-03 07:00:00"),
        _item("Ongoing", "2026-11-01 07:00:00"),
        _item("Hidden", "2026-11-20 07:00:00", hide_from_listings=True),
    ]
    second = [
        _item("Public workshop", "2026-12-06 00:00:00", all_day=True),
        _item("Outside window", "2026-12-16 10:00:00"),
    ]
    with patch.object(art_center, "RateLimitedSession") as session, patch.object(
        art_center, "local_today", return_value=date(2026, 11, 15)
    ):
        session.return_value.get.return_value.json.side_effect = [
            {"events": first, "total_pages": 2},
            {"events": second, "total_pages": 2},
        ]
        events = art_center.scrape()
    assert [e["title"] for e in events] == ["Reception", "Public workshop"]
    assert events[0]["time"] == "6:00 PM"
    assert events[0]["venue"] == "Gallery, 117 W Liberty, Ann Arbor, MI"
    assert events[1]["time"] == ""
    calls = session.return_value.get.call_args_list
    assert [call.kwargs["params"]["page"] for call in calls] == [1, 2]
    assert calls[0].kwargs["params"]["end_date"] == "2026-12-15"


def test_fetch_failure_propagates():
    with patch.object(art_center, "RateLimitedSession") as session:
        session.return_value.get.side_effect = RuntimeError("unavailable")
        with pytest.raises(RuntimeError, match="unavailable"):
            art_center.scrape()
