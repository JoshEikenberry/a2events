from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "hill_auditorium.html").read_text(encoding="utf-8")


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode("utf-8")
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        assert isinstance(scrape(), list)


def test_scrape_returns_expected_count():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        result = scrape()
        # Fixture has 3 events all in the 30-day window
        assert len(result) == 3


def test_events_have_source():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        for e in scrape():
            assert e["source"] == "hill_auditorium"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        for e in scrape():
            assert is_in_window(e["date"]), f"Event date {e['date']} not in window"


def test_events_have_required_fields():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        for e in scrape():
            assert e["title"], "title must not be empty"
            assert e["date"], "date must not be empty"
            assert e["url"], "url must not be empty"
            assert e["venue"] == "Hill Auditorium"


def test_events_have_ums_urls():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        for e in scrape():
            assert e["url"].startswith("https://ums.org/"), f"URL {e['url']} not from ums.org"


def test_event_titles_are_non_empty():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        titles = [e["title"] for e in scrape()]
        assert len(titles) > 0
        first = titles[0]
        assert "Martin Hayes" in first or "An Irish Celebration" in first


def test_no_duplicate_ids():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        events = scrape()
        ids = [e["id"] for e in events]
        assert len(ids) == len(set(ids)), "Duplicate event IDs found"
