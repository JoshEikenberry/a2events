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


def test_discover_scrapers_imports_available_modules():
    fake_module = MagicMock()
    def fake_import(name):
        if name == "scrapers.ark":
            return fake_module
        raise ImportError(f"No module named '{name}'")

    with patch("run_scrapers.importlib.import_module", side_effect=fake_import):
        scrapers = discover_scrapers()

    assert "ark" in scrapers
    assert scrapers["ark"] is fake_module
    # Other scrapers that raised ImportError should not be included
    assert "michigan_theater" not in scrapers


def test_discover_scrapers_warns_on_import_error(caplog):
    import logging
    with patch("run_scrapers.importlib.import_module", side_effect=ImportError("not found")):
        with caplog.at_level(logging.WARNING, logger="run_scrapers"):
            scrapers = discover_scrapers()
    assert scrapers == {}
    assert any("Could not import" in r.message for r in caplog.records)


def test_run_scraper_non_list_return_returns_empty():
    mock_scraper = MagicMock()
    mock_scraper.scrape.return_value = None  # scraper returns None instead of list
    result = run_scraper("bad", mock_scraper)
    assert result == []
