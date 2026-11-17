# merge.py
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from scrapers.base import local_today
from rapidfuzz import fuzz
from locations import location_review, normalize_location

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
OUTPUT_PATH = Path("docs/events.json")

MERGE_THRESHOLD = 85    # >= this: merge into one event
FLAG_THRESHOLD = 70     # >= this but < MERGE_THRESHOLD: flag as possible_duplicate

# Sidearm and the EMU campus calendar use city/state locations, sometimes
# followed by a venue name. Only classify athletics, not general campus events.
_SCHEDULE = re.compile(
    r"\b(?:EMU|Eastern Michigan|University of Michigan|U[- ]?M|Michigan Wolverines)"
    r"\s+(?:(?:Men|Women)(?:'s|’s)\s+)?"
    r"(?:football|basketball|hockey|baseball|softball|soccer|volleyball|"
    r"rowing|swimming(?:\s*(?:and|&)\s*diving)?|diving|gymnastics|wrestling|"
    r"tennis|golf|lacrosse|cross country|track(?:\s+(?:and|&)\s+field)?|field hockey)"
    r"\s+(at|vs\.?)\s+", re.I
)
_LOCAL_TOWNS = re.compile(
    r"(?:^|\b)(?:Ann Arbor|Ypsilanti|Dexter|Chelsea|Milan|Whitmore Lake|Brighton|Saline|Manchester|"
    r"Pittsfield Township|Northfield Township|Scio Township|Superior Township)$", re.I
)
_LOCAL_VENUES = re.compile(
    r"\b(?:Michigan Stadium|Crisler Center|Yost Ice Arena|Ray Fisher Stadium|"
    r"Alumni Field|Cliff Keen Arena|U-M Soccer Stadium|Rynearson Stadium|"
    r"GameAbove (?:Convocation|Center)|Gervin GameAbove Center|Jones Natatorium|"
    r"Oestrike Stadium|Scicluna Field|Bowen Field House)\b", re.I
)
_STATE = re.compile(
    r"(?:^|,)\s*([^,]+?),\s*"
    r"(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|"
    r"Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|"
    r"Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|"
    r"Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|"
    r"New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    r"Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|"
    r"Virginia|Washington|West Virginia|Wisconsin|Wyoming|"
    r"[A-Z]{2}|Ala\.|Ariz\.|Ark\.|Calif\.|Colo\.|Conn\.|Del\.|Fla\.|Ga\.|"
    r"Ill\.|Ind\.|Kan\.|Ky\.|La\.|Mass\.|Md\.|Mich\.|Minn\.|Miss\.|Mo\.|"
    r"Mont\.|Neb\.|Nev\.|N\.H\.|N\.J\.|N\.M\.|N\.Y\.|N\.C\.|N\.D\.|"
    r"Okla\.|Ore\.|Pa\.|R\.I\.|S\.C\.|S\.D\.|Tenn\.|Tex\.|Vt\.|Va\.|"
    r"Wash\.|W\.Va\.|Wis\.|Wyo\.)(?=\s|,|$)",
    re.I,
)
_FOREIGN_COUNTRY = re.compile(
    r",\s*(?:Mexico|Canada|England|Scotland|Ireland|France|Germany|Spain|Italy|Japan|Australia)\b", re.I
)


def _out_of_town_athletics(event: dict) -> bool:
    title = event.get("title") or ""
    source = event.get("source") or ""
    category = event.get("category") or ""
    schedule = _SCHEDULE.search(title)
    if source != "um_athletics" and category not in ("um_athletics", "athletics", "sports") and not schedule:
        return False

    location = ", ".join(filter(None, (event.get("venue"), event.get("address"))))
    if _FOREIGN_COUNTRY.search(location):
        return True
    match = _STATE.search(location)
    if match:
        city, state = match.groups()
        if state.casefold().rstrip(".") not in ("mi", "mich", "michigan"):
            return True
        if re.search(r"\b(?:stadium|arena|center|centre|field|gym|hall|park)\b", city, re.I) and not _LOCAL_TOWNS.search(city.strip()):
            return False
        return not bool(_LOCAL_TOWNS.search(city.strip()))
    if _LOCAL_VENUES.search(location) or _LOCAL_TOWNS.fullmatch(location.strip()):
        return False
    # A team schedule's "at" denotes an away game unless a known local
    # location establishes a local derby; other uses of "at" are ambiguous.
    return bool(schedule and schedule.group(1).casefold() == "at")


def _normalized_time(value: str) -> tuple[int, int] | None:
    """Return a comparable clock time, or None when the value is ambiguous."""
    match = re.fullmatch(
        r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*",
        value, re.IGNORECASE,
    )
    if match:
        hour, minute = int(match[1]), int(match[2] or 0)
        if 1 <= hour <= 12 and minute < 60:
            return (hour % 12 + (12 if match[3].lower() == "p" else 0), minute)
        return None
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::00)?\s*", value)
    if match:
        hour, minute = int(match[1]), int(match[2])
        if hour < 24 and minute < 60:
            return hour, minute
    return None


def _start_time(value: str) -> tuple[int, int] | None:
    """Parse a display time for sorting without changing deduplication rules."""
    value = value.strip()
    match = re.fullmatch(r"(noon|midnight)", value, re.IGNORECASE)
    if match:
        return (12, 0) if match[1].lower() == "noon" else (0, 0)
    normalized = _normalized_time(value)
    if normalized is not None:
        return normalized

    # Some sources attach the meridiem only to the end of a range.
    parts = re.split(r"\s*(?:[-–—]|\bto\b)\s*", value, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    start, end = parts
    first = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", start)
    last = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", end, re.IGNORECASE)
    if not first or not last or not 1 <= int(first[1]) <= 12:
        if start.lower() in ("noon", "midnight"):
            return (12, 0) if start.lower() == "noon" else (0, 0)
        return _normalized_time(start)
    hour, minute = int(first[1]), int(first[2] or 0)
    end_hour, end_minute = int(last[1]), int(last[2] or 0)
    if not (1 <= hour <= 12 and minute < 60 and 1 <= end_hour <= 12 and end_minute < 60):
        return None
    end_minutes = (end_hour % 12 + (12 if last[3].lower() == "p" else 0)) * 60 + end_minute
    morning = (hour % 12) * 60 + minute
    afternoon = morning + 12 * 60
    start = min((morning, afternoon), key=lambda candidate: (end_minutes - candidate) % (24 * 60))
    return divmod(start, 60)


def _sort_key(event: dict) -> tuple[str, int, int]:
    start = _start_time(event.get("time") or "")
    return (event["date"],) + (start if start is not None else (24, 0))


def compute_similarity(a: dict, b: dict) -> float:
    """Compute weighted fuzzy similarity between two events (0-100)."""
    title_score = fuzz.token_set_ratio(a["title"], b["title"])
    venue_score = fuzz.token_set_ratio(a["venue"], b["venue"])

    a_time = _normalized_time(a.get("time") or "")
    b_time = _normalized_time(b.get("time") or "")
    if a_time is not None and b_time is not None:
        time_score = 100 if a_time == b_time else 0
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
        if _out_of_town_athletics(event):
            continue
        by_date.setdefault(event["date"], []).append(event)

    for date_str, day_events in by_date.items():
        day_result: list[dict] = []
        day_used: set[int] = set()

        for i, a in enumerate(day_events):
            if i in day_used:
                continue
            for j, b in enumerate(day_events):
                if i >= j or j in day_used:
                    continue
                a_time = _normalized_time(a.get("time") or "")
                b_time = _normalized_time(b.get("time") or "")
                if a_time is None or b_time is None or a_time != b_time:
                    continue
                score = compute_similarity(a, b)
                if score >= MERGE_THRESHOLD:
                    keeper, secondary = _pick_better(a, b)
                    keeper = normalize_location(keeper)
                    secondary_location = normalize_location(secondary)
                    same_venue = (
                        keeper["venue"].casefold() == secondary_location["venue"].casefold()
                        or not keeper["venue"]
                    )
                    same_city = (
                        not keeper["location_city"] or not secondary_location["location_city"]
                        or keeper["location_city"].casefold() == secondary_location["location_city"].casefold()
                    )
                    if not same_city:
                        continue
                    if (keeper["location_status"] == "resolved"
                            and secondary_location["location_status"] == "resolved"
                            and keeper["address"].casefold() != secondary_location["address"].casefold()):
                        continue
                    if same_venue and keeper["location_status"] != "online":
                        if not keeper["venue"]:
                            keeper["venue"] = secondary_location["venue"]
                        if (not keeper["address"] or
                                (keeper["location_status"] != "resolved" and
                                 secondary_location["location_status"] == "resolved")):
                            if keeper["address"]:
                                keeper["location_original_address"] = keeper["address"]
                            keeper["address"] = secondary_location["address"]
                    keeper["also_listed_at"] = list(keeper.get("also_listed_at") or []) + [secondary["url"]] + list(secondary.get("also_listed_at") or [])
                    a = keeper
                    day_used.add(j)
                elif score >= FLAG_THRESHOLD:
                    a = dict(a)
                    a["possible_duplicate"] = True
                    day_events[j] = dict(day_events[j])
                    day_events[j]["possible_duplicate"] = True

            day_result.append(normalize_location(a))
            day_used.add(i)

        merged.extend(day_result)

    merged.sort(key=_sort_key)
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
    # A failed scraper can leave its last successful raw file in place.
    # Do not republish events that have since passed.
    today = local_today().isoformat()
    events = [event for event in events if event.get("date", "") >= today]
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
    review_path = OUTPUT_PATH.parent / "location-review.json"
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(location_review(merged), f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {review_path}")


if __name__ == "__main__":
    main()
