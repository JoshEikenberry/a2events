"""Tests for the AADL (Ann Arbor District Library) events scraper."""
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from scrapers.base import is_in_window
from scrapers.aadl import FALLBACK_URL

FIXTURE = (Path(__file__).parent / "fixtures" / "aadl.html").read_text(encoding="utf-8")

EMPTY_PAGE = """
<!DOCTYPE html><html><body>
<main id="main-content">
<div class="view-content">
<div class="views-results" id="search-results">
</div>
</div>
</main>
</body></html>
"""


def _mock_session(*pages):
    """Return a mock RateLimitedSession whose .get() returns pages in order.

    If only one page is given, every call returns that page (single-page default).
    """
    sess = MagicMock()
    responses = []
    for html in pages:
        resp = MagicMock()
        resp.text = html
        responses.append(resp)
    if len(responses) == 1:
        sess.get.return_value = responses[0]
    else:
        sess.get.side_effect = responses
    return sess


def test_returns_list():
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE, EMPTY_PAGE)
        from scrapers.aadl import scrape
        assert isinstance(scrape(), list)


def test_source_and_category():
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE, EMPTY_PAGE)
        from scrapers.aadl import scrape
        events = scrape()
        assert len(events) >= 1
        for e in events:
            assert e["source"] == "aadl"
            assert e["category"] == "community"


def test_in_window_filtering():
    """Out-of-window event (Sept 2027) must be excluded."""
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE, EMPTY_PAGE)
        from scrapers.aadl import scrape
        events = scrape()
        titles = [e["title"] for e in events]
        assert "Future Author Talk" not in titles, "Out-of-window event was not filtered"
        assert len(events) >= 1, "Fixture must yield at least one in-window event"
        for e in events:
            assert is_in_window(e["date"]), f"Event out of window: {e['date']} — {e['title']}"


def test_required_fields():
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE, EMPTY_PAGE)
        from scrapers.aadl import scrape
        events = scrape()
        assert len(events) >= 1
        for e in events:
            assert e["title"], f"Missing title: {e}"
            assert e["date"], f"Missing date: {e}"
            assert e["url"].startswith("http"), f"Invalid URL: {e['url']}"
            assert e["source"] == "aadl"
            assert e["category"] == "community"


def test_event_type_tag():
    """Event type label from .mat-type-icon p becomes a normalized tag."""
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE, EMPTY_PAGE)
        from scrapers.aadl import scrape
        events = scrape()
        # Event 1 has label "Preschool Storytimes" → tag "preschool_storytimes"
        storytimes = [e for e in events if e["title"] == "Preschool Storytimes"]
        assert storytimes, "Fixture event 'Preschool Storytimes' not found in results"
        assert "preschool_storytimes" in storytimes[0]["tags"]
        # Event 2 has "Lectures & Panel Discussions" → "lectures_panel_discussions"
        lectures = [e for e in events if e["title"] == "Author Event: Local Voices"]
        assert lectures, "Fixture event 'Author Event: Local Voices' not found in results"
        assert "lectures_panel_discussions" in lectures[0]["tags"]


def test_url_fallback():
    """Event with no href in <a> tag falls back to FALLBACK_URL."""
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE, EMPTY_PAGE)
        from scrapers.aadl import scrape
        events = scrape()
        sewing = [e for e in events if e["title"] == "Sewing Lab Open Session"]
        assert sewing, "Fixture event 'Sewing Lab Open Session' not found in results"
        assert sewing[0]["url"] == FALLBACK_URL


def test_pagination_stops():
    """Scraper fetches page 0 (has events), then page 1 (empty), then stops."""
    with patch("scrapers.aadl.RateLimitedSession") as cls:
        # page 0 = fixture with events, page 1 = empty page
        sess = _mock_session(FIXTURE, EMPTY_PAGE)
        cls.return_value = sess
        from scrapers.aadl import scrape
        events = scrape()

    assert sess.get.call_count == 2, (
        f"Expected exactly 2 HTTP calls (page 0 + empty page 1), got {sess.get.call_count}"
    )
    assert len(events) >= 1
