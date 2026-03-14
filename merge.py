# merge.py
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
OUTPUT_PATH = Path("docs/events.json")

MERGE_THRESHOLD = 85    # >= this: merge into one event
FLAG_THRESHOLD = 70     # >= this but < MERGE_THRESHOLD: flag as possible_duplicate


def compute_similarity(a: dict, b: dict) -> float:
    """Compute weighted fuzzy similarity between two events (0-100)."""
    title_score = fuzz.token_set_ratio(a["title"], b["title"])
    venue_score = fuzz.token_set_ratio(a["venue"], b["venue"])

    if a["time"] and b["time"]:
        time_score = 100 if a["time"] == b["time"] else fuzz.ratio(a["time"], b["time"])
    else:
        time_score = 50  # unknown — neutral

    return title_score * 0.6 + venue_score * 0.3 + time_score * 0.1


def _pick_better(a: dict, b: dict) -> tuple[dict, dict]:
    """Return (keeper, secondary) based on detail level."""
    a_score = len(a.get("description", "")) + (100 if a.get("image_url") else 0)
    b_score = len(b.get("description", "")) + (100 if b.get("image_url") else 0)
    if b_score > a_score:
        return b, a
    return a, b


def merge_events(events: list[dict]) -> list[dict]:
    """Deduplicate events using fuzzy matching. Returns merged event list."""
    merged: list[dict] = []

    # Group by date for efficiency
    by_date: dict[str, list[dict]] = {}
    for event in events:
        by_date.setdefault(event["date"], []).append(event)

    for date_str, day_events in by_date.items():
        day_result: list[dict] = []
        day_used: set[str] = set()

        for i, a in enumerate(day_events):
            if a["id"] in day_used:
                continue
            for j, b in enumerate(day_events):
                if i >= j or b["id"] in day_used:
                    continue
                score = compute_similarity(a, b)
                if score >= MERGE_THRESHOLD:
                    keeper, secondary = _pick_better(a, b)
                    keeper = dict(keeper)
                    keeper["also_listed_at"] = list(keeper["also_listed_at"]) + [secondary["url"]] + list(secondary.get("also_listed_at", []))
                    a = keeper
                    day_used.add(secondary["id"])
                elif score >= FLAG_THRESHOLD:
                    a = dict(a)
                    a["possible_duplicate"] = True
                    day_events[j] = dict(day_events[j])
                    day_events[j]["possible_duplicate"] = True

            if a["id"] not in day_used:
                day_result.append(a)
                day_used.add(a["id"])

        merged.extend(day_result)

    merged.sort(key=lambda e: (e["date"], e.get("time", "")))
    return merged


def load_raw_events() -> list[dict]:
    """Load all per-source JSON files from data/raw/."""
    events = []
    if not RAW_DIR.exists():
        logger.warning(f"Raw data directory {RAW_DIR} does not exist.")
        return events
    for path in RAW_DIR.glob("*.json"):
        try:
            with open(path) as f:
                source_events = json.load(f)
            events.extend(source_events)
            logger.info(f"Loaded {len(source_events)} events from {path.name}")
        except Exception as e:
            logger.error(f"Failed to load {path.name}: {e}")
    return events


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    events = load_raw_events()
    logger.info(f"Loaded {len(events)} total events across all sources")

    merged = merge_events(events)
    logger.info(f"After dedup: {len(merged)} events")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(merged),
        "events": merged,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
