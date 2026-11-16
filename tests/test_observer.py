"""Tests for the Ann Arbor Observer scraper."""
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import date

import pytest

FIXTURE = (Path(__file__).parent / "fixtures" / "observer.html").read_text(encoding="utf-8")


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        result = observer.scrape()
        assert isinstance(result, list)


def test_events_source():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        for e in observer.scrape():
            assert e["source"] == "observer"
            assert e["category"] == "community"


def test_events_in_window():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        from scrapers.base import is_in_window
        for e in observer.scrape():
            assert is_in_window(e["date"]), f"Event date {e['date']} out of window"


def test_events_have_required_fields():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        events = observer.scrape()
        for e in events:
            assert "title" in e and e["title"]
            assert "date" in e and e["date"]
            assert "url" in e and e["url"]
            assert e["url"].startswith("http")


def test_events_no_duplicates():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers import observer
        import importlib
        importlib.reload(observer)
        events = observer.scrape()
        occurrences = [(e["id"], e["date"], e["time"], e["title"], e["venue"], e["url"])
                       for e in events]
        assert len(occurrences) == len(set(occurrences)), "Duplicate occurrences found"


def test_scrape_preserves_same_id_distinct_occurrences(monkeypatch):
    from scrapers import observer

    first = {"id": "same", "date": "2026-03-15", "time": "7:00 PM",
             "title": "Show", "venue": "The Ark", "url": "https://example.com/show"}
    later = {**first, "time": "9:00 PM"}
    monkeypatch.setattr(observer, "local_today", lambda: date(2026, 3, 15))
    monkeypatch.setattr(observer, "RateLimitedSession", lambda: _mock_session(""))
    monkeypatch.setattr(observer, "_parse_events_from_html", lambda html: [first, later])

    assert observer.scrape() == [first, later]


@pytest.mark.parametrize("failure", ["fetch", "http", "parse"])
def test_scrape_propagates_failure_after_first_page(monkeypatch, failure):
    from scrapers import observer

    session = _mock_session("")
    first_response = session.get.return_value
    second_response = MagicMock()
    if failure == "fetch":
        session.get.side_effect = [first_response, RuntimeError("fetch failed")]
    else:
        session.get.side_effect = [first_response, second_response]
        if failure == "http":
            second_response.raise_for_status.side_effect = RuntimeError("http failed")
    parser = MagicMock(return_value=[{
        "id": "event", "date": "2026-03-15", "time": "7 PM",
        "title": "Show", "venue": "The Ark", "url": "https://example.com/show",
    }])
    if failure == "parse":
        parser.side_effect = [parser.return_value, RuntimeError("parse failed")]
    monkeypatch.setattr(observer, "local_today", lambda: date(2026, 3, 15))
    monkeypatch.setattr(observer, "RateLimitedSession", lambda: session)
    monkeypatch.setattr(observer, "_parse_events_from_html", parser)

    with pytest.raises(RuntimeError, match="failed"):
        observer.scrape()
