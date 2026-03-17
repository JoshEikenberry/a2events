# run_scrapers.py
import importlib
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
SCRAPERS_PKG = "scrapers"

SCRAPER_NAMES = [
    "ark",
    "michigan_theater",
    "hill_auditorium",
    "kerrytown",
    "blind_pig",
    "conor_oneills",
    "blue_llama",
    "detroit_street_filling",
    "resident_advisor",
    "observer",
    "eventbrite",
    "city_ann_arbor",
    "washtenaw_county",
    "ypsilanti",
    "eastern_michigan",
    "um_events",
    "um_athletics",
    "aadl",
]


def discover_scrapers() -> dict:
    """Import all scraper modules and return {name: module}."""
    scrapers = {}
    for name in SCRAPER_NAMES:
        try:
            module = importlib.import_module(f"{SCRAPERS_PKG}.{name}")
            scrapers[name] = module
        except ImportError as e:
            logger.warning(f"Could not import scraper '{name}': {e}")
    return scrapers


def run_scraper(name: str, module) -> list[dict]:
    """Run a single scraper module. Returns events or [] on failure."""
    try:
        events = module.scrape()
        if not isinstance(events, list):
            logger.error(f"[{name}] scrape() returned {type(events).__name__}, expected list")
            return []
        logger.info(f"[{name}] scraped {len(events)} events")
        return events
    except Exception as e:
        logger.error(f"[{name}] FAILED: {e}", exc_info=True)
        return []


def save_raw(name: str, events: list[dict], raw_dir: Path = RAW_DIR):
    """Save events to data/raw/<name>.json."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{name}.json"
    with open(path, "w") as f:
        json.dump(events, f, indent=2)
    logger.info(f"[{name}] saved {len(events)} events to {path}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    scrapers = discover_scrapers()

    if not scrapers:
        logger.error("No scrapers found. Exiting.")
        sys.exit(1)

    total = 0
    for name, module in scrapers.items():
        events = run_scraper(name, module)
        save_raw(name, events)
        total += len(events)

    logger.info(f"Total events scraped: {total}")


if __name__ == "__main__":
    main()
