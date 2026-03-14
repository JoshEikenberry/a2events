# tests/test_run_scrapers.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from run_scrapers import run_scraper, save_raw, discover_scrapers


def test_run_scraper_success():
    mock_scraper = MagicMock()
    mock_scraper.scrape.return_value = [{"id": "test-1", "title": "Test"}]
    mock_scraper.__name__ = "mock_scraper"

    result = run_scraper("mock", mock_scraper)
    assert result == [{"id": "test-1", "title": "Test"}]


def test_run_scraper_failure_returns_empty():
    mock_scraper = MagicMock()
    mock_scraper.scrape.side_effect = Exception("Network error")
    mock_scraper.__name__ = "failing_scraper"

    result = run_scraper("failing", mock_scraper)
    assert result == []


def test_save_raw(tmp_path):
    events = [{"id": "ark-1", "title": "Test Event"}]
    save_raw("ark", events, raw_dir=tmp_path)

    saved = json.loads((tmp_path / "ark.json").read_text())
    assert saved == events


def test_discover_scrapers():
    scrapers = discover_scrapers()
    # Should return a dict of name -> module (may be empty until scrapers are implemented)
    assert isinstance(scrapers, dict)
