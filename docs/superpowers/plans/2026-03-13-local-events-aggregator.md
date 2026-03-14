# Local Events Aggregator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily-updating public events calendar for Ann Arbor/Ypsilanti/Washtenaw County, scraped from 11 sources, deduplicated, and served as a GitHub Pages static site.

**Architecture:** Modular Python scrapers each output a per-source JSON file to `data/raw/`. A merge script deduplicates across sources using fuzzy matching and writes `docs/events.json`. A vanilla JS static site in `docs/index.html` reads the JSON and renders a hybrid mini-calendar + event card list. GitHub Actions runs the full pipeline daily at 6 AM UTC.

**Tech Stack:** Python 3.11, requests, BeautifulSoup4, rapidfuzz, playwright, icalendar, python-dateutil, pytest, vanilla HTML/CSS/JS, GitHub Actions, GitHub Pages

---

## Chunk 1: Project Scaffolding & Base Utilities

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `scrapers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/` (directory, empty)

- [ ] **Step 1: Create requirements.txt**

```
requests==2.31.0
beautifulsoup4==4.12.3
lxml==5.1.0
rapidfuzz==3.6.1
playwright==1.41.2
icalendar==5.0.11
python-dateutil==2.8.2
pytest==8.0.0
pytest-mock==3.12.0
responses==0.25.0
```

- [ ] **Step 2: Create empty package init files**

```bash
touch scrapers/__init__.py tests/__init__.py
mkdir -p tests/fixtures
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

Expected: all packages install without errors.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt scrapers/__init__.py tests/__init__.py tests/fixtures/
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: Base utilities — `make_event` and HTTP session

**Files:**
- Create: `scrapers/base.py`
- Create: `tests/test_base.py`

- [ ] **Step 1: Write failing tests for `make_event`**

```python
# tests/test_base.py
import pytest
from datetime import date, datetime, timezone
from scrapers.base import make_event, slugify


def test_make_event_generates_id():
    event = make_event(
        title="The War on Drugs",
        date="2026-03-15",
        time="8:00 PM",
        venue="The Ark",
        url="https://theark.org/event/123",
        source="ark",
        category="arts_culture",
    )
    assert event["id"] == "ark-2026-03-15-the-war-on-drugs"


def test_make_event_required_fields_present():
    event = make_event(
        title="Test Event",
        date="2026-03-15",
        time="7:00 PM",
        venue="Test Venue",
        url="https://example.com/event",
        source="test",
        category="arts_culture",
    )
    required = ["id", "title", "date", "time", "venue", "url", "source",
                "category", "tags", "description", "address",
                "also_listed_at", "image_url", "possible_duplicate", "scraped_at"]
    for field in required:
        assert field in event, f"Missing field: {field}"


def test_make_event_defaults():
    event = make_event(
        title="Test",
        date="2026-03-15",
        time="7:00 PM",
        venue="Venue",
        url="https://example.com",
        source="test",
        category="arts_culture",
    )
    assert event["tags"] == []
    assert event["description"] == ""
    assert event["address"] == ""
    assert event["also_listed_at"] == []
    assert event["image_url"] is None
    assert event["possible_duplicate"] is False


def test_make_event_url_required():
    with pytest.raises(ValueError, match="url"):
        make_event(
            title="Test",
            date="2026-03-15",
            time="7:00 PM",
            venue="Venue",
            url=None,
            source="test",
            category="arts_culture",
        )


def test_slugify():
    assert slugify("The War on Drugs") == "the-war-on-drugs"
    assert slugify("Conor O'Neill's") == "conor-oneills"
    assert slugify("  extra  spaces  ") == "extra-spaces"
    assert slugify("Special! @#$ Chars") == "special-chars"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_base.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `scrapers.base` does not exist yet.

- [ ] **Step 3: Implement `scrapers/base.py`**

```python
# scrapers/base.py
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def make_event(
    *,
    title: str,
    date: str,
    time: str,
    venue: str,
    url: Optional[str],
    source: str,
    category: str,
    tags: list = None,
    description: str = "",
    address: str = "",
    image_url: Optional[str] = None,
) -> dict:
    """Build a validated event dict conforming to the event schema."""
    if not url:
        raise ValueError("url is required and must not be None or empty")

    event_id = f"{source}-{date}-{slugify(title)}"

    return {
        "id": event_id,
        "title": title,
        "date": date,
        "time": time,
        "venue": venue,
        "address": address,
        "category": category,
        "tags": tags or [],
        "description": description,
        "url": url,
        "source": source,
        "also_listed_at": [],
        "image_url": image_url,
        "possible_duplicate": False,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def make_session() -> requests.Session:
    """Create an HTTP session with retry logic and rate limiting built in."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,  # exponential: 1s, 2s, 4s
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; A2EventsBot/1.0; +https://github.com/your-org/a2events)"
    })
    return session


class RateLimitedSession:
    """Wraps requests.Session with per-domain rate limiting (1-2s delay)."""

    def __init__(self):
        self._session = make_session()
        self._last_request_time: float = 0.0
        self._delay: float = 1.5  # seconds between requests

    def get(self, url: str, **kwargs) -> requests.Response:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request_time = time.time()
        response = self._session.get(url, timeout=15, **kwargs)
        response.raise_for_status()
        return response
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_base.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scrapers/base.py tests/test_base.py
git commit -m "feat: add base utilities (make_event, slugify, HTTP session)"
```

---

### Task 3: Base utilities — date helpers and iCal parser

**Files:**
- Modify: `scrapers/base.py`
- Modify: `tests/test_base.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_base.py`:

```python
from scrapers.base import parse_date, is_in_window, parse_ical_feed
from datetime import date
import responses as responses_lib


def test_parse_date_iso():
    assert parse_date("2026-03-15") == date(2026, 3, 15)


def test_parse_date_human():
    assert parse_date("March 15, 2026") == date(2026, 3, 15)
    assert parse_date("Saturday, March 15, 2026") == date(2026, 3, 15)


def test_parse_date_slash():
    assert parse_date("03/15/2026") == date(2026, 3, 15)


def test_parse_date_invalid():
    assert parse_date("not a date") is None


def test_is_in_window_today():
    today = date.today()
    assert is_in_window(today.isoformat()) is True


def test_is_in_window_future_in_range():
    from datetime import timedelta
    future = date.today() + timedelta(days=15)
    assert is_in_window(future.isoformat()) is True


def test_is_in_window_too_far():
    from datetime import timedelta
    far = date.today() + timedelta(days=45)
    assert is_in_window(far.isoformat()) is False


def test_is_in_window_past():
    assert is_in_window("2020-01-01") is False
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_base.py::test_parse_date_iso -v
```

Expected: `ImportError` — functions not defined yet.

- [ ] **Step 3: Implement date helpers in `scrapers/base.py`**

Add to `scrapers/base.py`:

```python
from datetime import date, timedelta
from dateutil import parser as dateutil_parser


def parse_date(text: str) -> Optional[date]:
    """Parse a date string in any common format. Returns None on failure."""
    if not text:
        return None
    try:
        return dateutil_parser.parse(text, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def is_in_window(date_str: str, window_days: int = WINDOW_DAYS) -> bool:
    """Return True if date_str falls within today + window_days."""
    parsed = parse_date(date_str)
    if not parsed:
        return False
    today = date.today()
    return today <= parsed <= today + timedelta(days=window_days)


def parse_ical_feed(ical_bytes: bytes, source: str, category: str) -> list[dict]:
    """Parse an iCal feed and return a list of event dicts within the window."""
    from icalendar import Calendar
    cal = Calendar.from_ical(ical_bytes)
    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.get("DTSTART")
        if not dtstart:
            continue
        event_date = dtstart.dt
        if hasattr(event_date, "date"):
            event_date = event_date.date()
        date_str = event_date.isoformat()
        if not is_in_window(date_str):
            continue
        title = str(component.get("SUMMARY", "")).strip()
        url = str(component.get("URL", "")).strip() or None
        if not url or not title:
            continue
        events.append(make_event(
            title=title,
            date=date_str,
            time=dtstart.dt.strftime("%I:%M %p").lstrip("0") if hasattr(dtstart.dt, "strftime") else "",
            venue=str(component.get("LOCATION", "")).strip(),
            url=url,
            source=source,
            category=category,
            description=str(component.get("DESCRIPTION", "")).strip(),
        ))
    return events
```

- [ ] **Step 4: Run all base tests**

```bash
pytest tests/test_base.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scrapers/base.py tests/test_base.py
git commit -m "feat: add date helpers and iCal parser to base utilities"
```

---

## Chunk 2: Merge & Deduplication

### Task 4: Implement merge.py

**Files:**
- Create: `merge.py`
- Create: `tests/test_merge.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_merge.py
import pytest
from merge import compute_similarity, merge_events, load_raw_events


def make_test_event(title, date, venue, time="8:00 PM", source="test", url=None):
    return {
        "id": f"{source}-{date}-{title.lower().replace(' ', '-')}",
        "title": title,
        "date": date,
        "time": time,
        "venue": venue,
        "url": url or f"https://example.com/{title}",
        "source": source,
        "category": "arts_culture",
        "tags": [],
        "description": "",
        "address": "",
        "also_listed_at": [],
        "image_url": None,
        "possible_duplicate": False,
        "scraped_at": "2026-03-13T06:00:00Z",
    }


def test_compute_similarity_identical():
    a = make_test_event("The War on Drugs", "2026-03-15", "The Ark")
    b = make_test_event("The War on Drugs", "2026-03-15", "The Ark")
    score = compute_similarity(a, b)
    assert score >= 95


def test_compute_similarity_different_events():
    a = make_test_event("Jazz Night", "2026-03-15", "Blue Llama")
    b = make_test_event("Comedy Show", "2026-03-15", "Blind Pig")
    score = compute_similarity(a, b)
    assert score < 70


def test_compute_similarity_fuzzy_title():
    a = make_test_event("The Ark Presents: The War on Drugs", "2026-03-15", "The Ark")
    b = make_test_event("The War on Drugs", "2026-03-15", "Ark")
    score = compute_similarity(a, b)
    assert score >= 80


def test_merge_events_deduplicates_above_threshold():
    events = [
        make_test_event("The War on Drugs", "2026-03-15", "The Ark", source="ark",
                        url="https://theark.org/event/1"),
        make_test_event("The War on Drugs", "2026-03-15", "The Ark", source="observer",
                        url="https://observer.com/event/1"),
    ]
    result = merge_events(events)
    assert len(result) == 1
    merged = result[0]
    assert len(merged["also_listed_at"]) == 1


def test_merge_events_flags_possible_duplicates():
    events = [
        make_test_event("The Ark Presents The War on Drugs Live", "2026-03-15", "The Ark",
                        source="ark", url="https://theark.org/1"),
        make_test_event("War on Drugs", "2026-03-15", "Ark Ann Arbor",
                        source="eventbrite", url="https://eventbrite.com/1"),
    ]
    result = merge_events(events)
    # Score should be 70-85 range — kept separate but flagged
    # (exact behavior depends on score; test that at least one is flagged or merged)
    assert len(result) in (1, 2)
    if len(result) == 2:
        assert any(e["possible_duplicate"] for e in result)


def test_merge_events_keeps_more_detailed():
    short = make_test_event("Great Show", "2026-03-15", "The Ark", source="ark")
    short["description"] = "Short desc"
    long_ = make_test_event("Great Show", "2026-03-15", "The Ark", source="observer")
    long_["description"] = "A much longer and more detailed description of the event"
    result = merge_events([short, long_])
    assert len(result) == 1
    assert result[0]["description"] == long_["description"]


def test_merge_events_preserves_distinct_events():
    events = [
        make_test_event("Jazz Night", "2026-03-15", "Blue Llama"),
        make_test_event("Rock Show", "2026-03-15", "Blind Pig"),
        make_test_event("Comedy Hour", "2026-03-16", "Conor O'Neill's"),
    ]
    result = merge_events(events)
    assert len(result) == 3
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_merge.py -v
```

Expected: `ModuleNotFoundError: No module named 'merge'`

- [ ] **Step 3: Implement `merge.py`**

```python
# merge.py
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
OUTPUT_PATH = Path("docs/events.json")

MERGE_THRESHOLD = 85    # ≥ this: merge into one event
FLAG_THRESHOLD = 70     # ≥ this but < MERGE_THRESHOLD: flag as possible_duplicate


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
    used: set[str] = set()

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
                    keeper["also_listed_at"] = list(keeper["also_listed_at"]) + [secondary["url"]]
                    a = keeper
                    day_used.add(secondary["id"])
                elif score >= FLAG_THRESHOLD:
                    a = dict(a)
                    a["possible_duplicate"] = True
                    b = dict(b)
                    b["possible_duplicate"] = True

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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_merge.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add merge.py tests/test_merge.py
git commit -m "feat: implement merge and fuzzy deduplication"
```

---

### Task 5: Implement `run_scrapers.py` orchestrator

**Files:**
- Create: `run_scrapers.py`
- Create: `tests/test_run_scrapers.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_run_scrapers.py -v
```

Expected: `ModuleNotFoundError: No module named 'run_scrapers'`

- [ ] **Step 3: Implement `run_scrapers.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_run_scrapers.py -v
```

Expected: all tests PASS (note: `discover_scrapers` may return 0 modules since scrapers aren't written yet — that's fine, the test just checks the return type).

- [ ] **Step 5: Commit**

```bash
git add run_scrapers.py tests/test_run_scrapers.py
git commit -m "feat: add scraper orchestrator with failure isolation"
```

---

## Chunk 3: Arts & Culture Scrapers — Part 1

> **Note for implementer:** Before writing each scraper, open the venue's website in a browser and inspect the HTML structure or look for iCal/API feeds. The steps below tell you what to look for. Capture a fixture HTML snippet and save it to `tests/fixtures/<source>.html` (or `.json` for APIs). Tests parse the fixture, not live sites.

### Task 6: The Ark scraper

**Files:**
- Create: `scrapers/ark.py`
- Create: `tests/fixtures/ark.html` (captured from site)
- Create: `tests/test_ark.py`

- [ ] **Step 1: Inspect the site and capture fixture**

Visit `https://theark.org/events/` in a browser. Look for:
- An iCal feed link (check footer, `/events?format=ical`, or page source for `text/calendar`)
- JSON-LD `<script type="application/ld+json">` blocks in the page source
- If neither, identify the HTML structure of event listings

Save representative HTML of 2-3 events to `tests/fixtures/ark.html`, or save the iCal feed to `tests/fixtures/ark.ics`.

- [ ] **Step 2: Write failing test using the fixture**

```python
# tests/test_ark.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.ark import scrape

FIXTURE = (Path(__file__).parent / "fixtures" / "ark.html").read_text()
# Or for iCal: FIXTURE = (Path(__file__).parent / "fixtures" / "ark.ics").read_bytes()


def test_scrape_returns_list():
    with patch("scrapers.ark.RateLimitedSession") as mock_sess_cls:
        mock_sess = MagicMock()
        mock_sess_cls.return_value = mock_sess
        mock_response = MagicMock()
        mock_response.text = FIXTURE
        mock_response.content = FIXTURE.encode() if isinstance(FIXTURE, str) else FIXTURE
        mock_sess.get.return_value = mock_response

        events = scrape()
        assert isinstance(events, list)


def test_scrape_events_have_required_fields():
    with patch("scrapers.ark.RateLimitedSession") as mock_sess_cls:
        mock_sess = MagicMock()
        mock_sess_cls.return_value = mock_sess
        mock_response = MagicMock()
        mock_response.text = FIXTURE
        mock_response.content = FIXTURE.encode() if isinstance(FIXTURE, str) else FIXTURE
        mock_sess.get.return_value = mock_response

        events = scrape()
        if events:
            e = events[0]
            assert e["source"] == "ark"
            assert e["category"] == "arts_culture"
            assert e["url"].startswith("http")
            assert e["date"]  # non-empty


def test_scrape_all_events_in_window():
    with patch("scrapers.ark.RateLimitedSession") as mock_sess_cls:
        mock_sess = MagicMock()
        mock_sess_cls.return_value = mock_sess
        mock_response = MagicMock()
        mock_response.text = FIXTURE
        mock_response.content = FIXTURE.encode() if isinstance(FIXTURE, str) else FIXTURE
        mock_sess.get.return_value = mock_response

        from scrapers.base import is_in_window
        events = scrape()
        for e in events:
            assert is_in_window(e["date"]), f"Event out of window: {e['date']}"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
pytest tests/test_ark.py -v
```

Expected: `ModuleNotFoundError` for `scrapers.ark`.

- [ ] **Step 4: Implement `scrapers/ark.py`**

Implement based on what you found in Step 1. Template:

```python
# scrapers/ark.py
"""Scraper for The Ark (theark.org)."""
import logging
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_ical_feed

logger = logging.getLogger(__name__)

SOURCE = "ark"
CATEGORY = "arts_culture"
# Use whichever URL gives the best structured data:
EVENTS_URL = "https://theark.org/events/"  # adjust to iCal/API URL if found

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: iCal path (preferred — check page source for <link type="text/calendar">
    #   or try theark.org/events/?ical=1, /feed/ical/, etc.) ---
    # response = session.get(ICAL_URL)
    # return parse_ical_feed(response.content, SOURCE, CATEGORY)

    # --- Option B: HTML path ---
    # from bs4 import BeautifulSoup
    # from scrapers.base import parse_date
    # response = session.get(EVENTS_URL)
    # soup = BeautifulSoup(response.text, "lxml")
    # for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
    #     title = item.select_one("REPLACE_TITLE").get_text(strip=True)
    #     date_parsed = parse_date(item.select_one("REPLACE_DATE").get_text(strip=True))
    #     if not date_parsed or not is_in_window(date_parsed.isoformat()):
    #         continue
    #     url = item.select_one("a")["href"]
    #     events.append(make_event(
    #         title=title, date=date_parsed.isoformat(), time="", venue="The Ark",
    #         url=url, source=SOURCE, category=CATEGORY, tags=["music"],
    #     ))
    return events
```

Fill in the actual parsing logic (uncomment Option A or B) based on the fixture you captured.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_ark.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scrapers/ark.py tests/test_ark.py tests/fixtures/ark.*
git commit -m "feat: add The Ark scraper"
```

---

### Task 7: Michigan Theater scraper

**Files:**
- Create: `scrapers/michigan_theater.py`
- Create: `tests/fixtures/michigan_theater.html` (or `.json`)
- Create: `tests/test_michigan_theater.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://michtheater.org/` (events section). Look for JSON-LD structured data or iCal feed first. Save fixture to `tests/fixtures/michigan_theater.html` (or appropriate extension).

- [ ] **Step 2: Write failing test**

```python
# tests/test_michigan_theater.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "michigan_theater.html"
FIXTURE = FIXTURE_PATH.read_text()


def _make_mock_session(text):
    mock_sess = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.content = text.encode()
    mock_sess.get.return_value = mock_resp
    return mock_sess


def test_scrape_returns_list():
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        assert isinstance(scrape(), list)


def test_scrape_source_and_category():
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        events = scrape()
        for e in events:
            assert e["source"] == "michigan_theater"
            assert e["category"] == "arts_culture"


def test_scrape_events_in_window():
    with patch("scrapers.michigan_theater.RateLimitedSession") as cls:
        cls.return_value = _make_mock_session(FIXTURE)
        from scrapers.michigan_theater import scrape
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_michigan_theater.py -v
```

- [ ] **Step 4: Implement `scrapers/michigan_theater.py`**

```python
# scrapers/michigan_theater.py
"""Scraper for Michigan Theater (michtheater.org)."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, parse_ical_feed

logger = logging.getLogger(__name__)
SOURCE = "michigan_theater"
CATEGORY = "arts_culture"
EVENTS_URL = "https://michtheater.org/events/"  # verify; may include /calendar/ path

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: iCal feed (preferred if available) ---
    # Look for <link type="text/calendar"> or ?ical=1 in page source
    # response = session.get(ICAL_URL)
    # return parse_ical_feed(response.content, SOURCE, CATEGORY)

    # --- Option B: JSON-LD structured data (check <script type="application/ld+json">) ---
    # import json
    # for tag in soup.find_all("script", type="application/ld+json"):
    #     data = json.loads(tag.string)
    #     if data.get("@type") == "Event": ...

    # --- Option C: HTML parsing (BeautifulSoup) ---
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    # Find the correct CSS selector from your fixture inspection:
    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://michtheater.org" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue="Michigan Theater",
            url=url,
            source=SOURCE,
            category=CATEGORY,
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_michigan_theater.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/michigan_theater.py tests/test_michigan_theater.py tests/fixtures/michigan_theater.*
git commit -m "feat: add Michigan Theater scraper"
```

---

### Task 8: Hill Auditorium scraper

**Files:**
- Create: `scrapers/hill_auditorium.py`
- Create: `tests/fixtures/hill_auditorium.html`
- Create: `tests/test_hill_auditorium.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://www.ums.org/` (University Musical Society) — UMS is the primary booking organization for Hill Auditorium and maintains the authoritative event calendar. Navigate to their events listing and look for an iCal export link or JSON-LD structured data in the page source. Save the HTML of the events listing page to `tests/fixtures/hill_auditorium.html`.

- [ ] **Step 2: Write failing test**

```python
# tests/test_hill_auditorium.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "hill_auditorium.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.hill_auditorium.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.hill_auditorium import scrape
        assert isinstance(scrape(), list)


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
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_hill_auditorium.py -v
```

- [ ] **Step 4: Implement `scrapers/hill_auditorium.py`**

```python
# scrapers/hill_auditorium.py
"""Scraper for Hill Auditorium via University Musical Society (ums.org)."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, parse_ical_feed

logger = logging.getLogger(__name__)
SOURCE = "hill_auditorium"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.ums.org/events/"  # verify; UMS lists all Hill Auditorium events

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: iCal feed (preferred if UMS provides one) ---
    # response = session.get(ICAL_URL)
    # return parse_ical_feed(response.content, SOURCE, CATEGORY)

    # --- Option B: HTML parsing ---
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://www.ums.org" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue="Hill Auditorium",
            url=url,
            source=SOURCE,
            category=CATEGORY,
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_hill_auditorium.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/hill_auditorium.py tests/test_hill_auditorium.py tests/fixtures/hill_auditorium.*
git commit -m "feat: add Hill Auditorium scraper"
```

---

### Task 9: Kerrytown Concert House scraper

**Files:**
- Create: `scrapers/kerrytown.py`
- Create: `tests/fixtures/kerrytown.html`
- Create: `tests/test_kerrytown.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://www.kerrytownconcerthouse.com/` and inspect the events listing page. Save fixture.

- [ ] **Step 2: Write failing test**

```python
# tests/test_kerrytown.py
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE = (Path(__file__).parent / "fixtures" / "kerrytown.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        for e in scrape():
            assert e["source"] == "kerrytown"


def test_events_in_window():
    with patch("scrapers.kerrytown.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.kerrytown import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_kerrytown.py -v
```

- [ ] **Step 4: Implement `scrapers/kerrytown.py`**

```python
# scrapers/kerrytown.py
"""Scraper for Kerrytown Concert House."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, parse_ical_feed

logger = logging.getLogger(__name__)
SOURCE = "kerrytown"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.kerrytownconcerthouse.com/events/"  # verify URL

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: iCal feed ---
    # response = session.get(ICAL_URL)
    # return parse_ical_feed(response.content, SOURCE, CATEGORY)

    # --- Option B: HTML parsing ---
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://www.kerrytownconcerthouse.com" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue="Kerrytown Concert House",
            url=url,
            source=SOURCE,
            category=CATEGORY,
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_kerrytown.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/kerrytown.py tests/test_kerrytown.py tests/fixtures/kerrytown.*
git commit -m "feat: add Kerrytown Concert House scraper"
```

---

## Chunk 4: Arts & Culture Scrapers — Part 2

> **Note for implementer:** Before writing each scraper, open the venue's website and inspect the HTML structure or look for iCal/API feeds. Capture a fixture HTML snippet and save it to `tests/fixtures/<source>.html` (or `.json` for APIs). Tests parse the fixture, not live sites.

### Task 10: Blind Pig scraper

**Files:**
- Create: `scrapers/blind_pig.py`
- Create: `tests/fixtures/blind_pig.html`
- Create: `tests/test_blind_pig.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://www.blindpigmusic.com/` and find the events listing. Open DevTools → Network tab, filter for XHR/Fetch, and reload — many smaller venues embed Eventbrite, Bandsintown, or Songkick widgets. If you see an embedded widget making API calls, use those API endpoints directly. **Important:** If the Blind Pig uses Eventbrite internally, its events will also appear in `scrapers/eventbrite.py` output — that is fine and expected. The deduplicator in `merge.py` will handle the overlap. Save fixture HTML or the API JSON response to `tests/fixtures/blind_pig.html` (or `.json`).

- [ ] **Step 2: Write failing test**

```python
# tests/test_blind_pig.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = (Path(__file__).parent / "fixtures" / "blind_pig.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        assert isinstance(scrape(), list)


def test_events_source_and_category():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        for e in scrape():
            assert e["source"] == "blind_pig"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.blind_pig.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blind_pig import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_blind_pig.py -v
```

- [ ] **Step 4: Implement `scrapers/blind_pig.py`**

```python
# scrapers/blind_pig.py
"""Scraper for The Blind Pig (blindpigmusic.com)."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, parse_ical_feed

logger = logging.getLogger(__name__)
SOURCE = "blind_pig"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.blindpigmusic.com/events/"  # verify; may be the homepage

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: Third-party widget API (Bandsintown, Songkick, Eventbrite) ---
    # If DevTools shows an embedded widget API, call it directly:
    # response = session.get("https://api.WIDGET.com/artists/blind-pig-ann-arbor/events")
    # data = response.json()
    # for item in data: ...

    # --- Option B: HTML parsing ---
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://www.blindpigmusic.com" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue="The Blind Pig",
            url=url,
            source=SOURCE,
            category=CATEGORY,
            tags=["music"],
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_blind_pig.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/blind_pig.py tests/test_blind_pig.py tests/fixtures/blind_pig.*
git commit -m "feat: add Blind Pig scraper"
```

---

### Task 11: Conor O'Neill's scraper

**Files:**
- Create: `scrapers/conor_oneills.py`
- Create: `tests/fixtures/conor_oneills.html`
- Create: `tests/test_conor_oneills.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://www.conoroneills.com/` — look at their events page. Many Irish pubs use Eventbrite. Check network requests in DevTools. Save fixture.

- [ ] **Step 2: Write failing test**

```python
# tests/test_conor_oneills.py
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE = (Path(__file__).parent / "fixtures" / "conor_oneills.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        for e in scrape():
            assert e["source"] == "conor_oneills"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.conor_oneills.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.conor_oneills import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_conor_oneills.py -v
```

- [ ] **Step 4: Implement `scrapers/conor_oneills.py`**

```python
# scrapers/conor_oneills.py
"""Scraper for Conor O'Neill's Irish pub (Ann Arbor)."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)
SOURCE = "conor_oneills"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.conoroneills.com/events/"  # verify; may use Eventbrite widget

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: Eventbrite embed (common for Irish pubs) ---
    # If DevTools shows Eventbrite API calls, use the Eventbrite API filtered by organizer/venue
    # instead of scraping HTML. This avoids double-counting with scrapers/eventbrite.py
    # only if the Eventbrite scraper doesn't already cover this organizer's events.

    # --- Option B: HTML parsing ---
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://www.conoroneills.com" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue="Conor O'Neill's",
            url=url,
            source=SOURCE,
            category=CATEGORY,
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_conor_oneills.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/conor_oneills.py tests/test_conor_oneills.py tests/fixtures/conor_oneills.*
git commit -m "feat: add Conor O'Neill's scraper"
```

---

### Task 12: Blue Llama Jazz Club scraper

**Files:**
- Create: `scrapers/blue_llama.py`
- Create: `tests/fixtures/blue_llama.html`
- Create: `tests/test_blue_llama.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://www.bluellamaclub.com/` and inspect the events listing. Save fixture.

- [ ] **Step 2: Write failing test**

```python
# tests/test_blue_llama.py
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE = (Path(__file__).parent / "fixtures" / "blue_llama.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        for e in scrape():
            assert e["source"] == "blue_llama"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.blue_llama.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.blue_llama import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_blue_llama.py -v
```

- [ ] **Step 4: Implement `scrapers/blue_llama.py`**

```python
# scrapers/blue_llama.py
"""Scraper for Blue Llama Jazz Club (Ann Arbor)."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, parse_ical_feed

logger = logging.getLogger(__name__)
SOURCE = "blue_llama"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.bluellamaclub.com/events/"  # verify URL

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    # --- Option A: iCal feed ---
    # response = session.get(ICAL_URL)
    # return parse_ical_feed(response.content, SOURCE, CATEGORY)

    # --- Option B: HTML parsing ---
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://www.bluellamaclub.com" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue="Blue Llama Jazz Club",
            url=url,
            source=SOURCE,
            category=CATEGORY,
            tags=["music", "jazz"],
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_blue_llama.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/blue_llama.py tests/test_blue_llama.py tests/fixtures/blue_llama.*
git commit -m "feat: add Blue Llama Jazz Club scraper"
```

---

### Task 13: Detroit Street Filling Station scraper

**Files:**
- Create: `scrapers/detroit_street_filling.py`
- Create: `tests/fixtures/detroit_street_filling.html`
- Create: `tests/test_detroit_street_filling.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://detroitstreetfillingstation.com/` and navigate to their events page. Note there are two venues — the restaurant/bar and the upstairs jazz club. Capture events from both if listed separately. Save fixture.

- [ ] **Step 2: Write failing test**

```python
# tests/test_detroit_street_filling.py
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE = (Path(__file__).parent / "fixtures" / "detroit_street_filling.html").read_text()


def _mock_session(text):
    sess = MagicMock()
    resp = MagicMock()
    resp.text = text
    resp.content = text.encode()
    sess.get.return_value = resp
    return sess


def test_scrape_returns_list():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.detroit_street_filling import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.detroit_street_filling import scrape
        for e in scrape():
            assert e["source"] == "detroit_street_filling"
            assert e["category"] == "arts_culture"


def test_events_in_window():
    with patch("scrapers.detroit_street_filling.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.detroit_street_filling import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_detroit_street_filling.py -v
```

- [ ] **Step 4: Implement `scrapers/detroit_street_filling.py`**

```python
# scrapers/detroit_street_filling.py
"""Scraper for Detroit Street Filling Station (+ upstairs jazz club)."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)
SOURCE = "detroit_street_filling"
CATEGORY = "arts_culture"
EVENTS_URL = "https://detroitstreetfillingstation.com/events/"  # verify URL

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []

    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    # The venue has two spaces (main floor + upstairs jazz club).
    # If events are on separate pages, make a second session.get() call for the jazz page.
    # If they share one events page, the selector below should capture both.
    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://detroitstreetfillingstation.com" + url
        # Infer venue name from page section if both floors are present:
        venue_name = "Detroit Street Filling Station"
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue=venue_name,
            url=url,
            source=SOURCE,
            category=CATEGORY,
            tags=["music"],
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_detroit_street_filling.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/detroit_street_filling.py tests/test_detroit_street_filling.py tests/fixtures/detroit_street_filling.*
git commit -m "feat: add Detroit Street Filling Station scraper"
```

---

## Chunk 5: Community & API Scrapers

> **Note for implementer:** Community scrapers include a mix of HTML scraping (Observer) and API-based sources (Resident Advisor, Eventbrite). For each task, follow Step 1 to inspect the source before writing tests or code.

### Task 14: Resident Advisor scraper

**Files:**
- Create: `scrapers/resident_advisor.py`
- Create: `tests/fixtures/resident_advisor.json`
- Create: `tests/test_resident_advisor.py`

- [ ] **Step 1: Find the API endpoint**

Visit `https://ra.co/events/us/annarbor` in a browser. Open DevTools → Network tab, filter for XHR/Fetch requests. Look for the GraphQL or REST API call that returns event data. Key things to look for:
- RA uses a GraphQL API at `https://ra.co/graphql`
- The events listing query passes `area` as a filter
- Capture the request payload and a sample response, save to `tests/fixtures/resident_advisor.json`

- [ ] **Step 2: Write failing test**

```python
# tests/test_resident_advisor.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from scrapers.base import is_in_window

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "resident_advisor.json").read_text())


def test_scrape_returns_list():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE
        mock_post.return_value = mock_resp

        from scrapers.resident_advisor import scrape
        events = scrape()
        assert isinstance(events, list)


def test_events_source():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE
        mock_post.return_value = mock_resp

        from scrapers.resident_advisor import scrape
        for e in scrape():
            assert e["source"] == "resident_advisor"
            assert e["category"] == "arts_culture"
            assert "music" in e["tags"] or e["tags"] == []


def test_events_in_window():
    with patch("scrapers.resident_advisor.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE
        mock_post.return_value = mock_resp

        from scrapers.resident_advisor import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_resident_advisor.py -v
```

- [ ] **Step 4: Implement `scrapers/resident_advisor.py`**

```python
# scrapers/resident_advisor.py
"""Scraper for Resident Advisor (Ann Arbor electronic/club events)."""
import logging
import requests
from scrapers.base import make_event, is_in_window

logger = logging.getLogger(__name__)
SOURCE = "resident_advisor"
CATEGORY = "arts_culture"

# RA GraphQL endpoint — verify this is still correct at implementation time
RA_GRAPHQL_URL = "https://ra.co/graphql"

# Adjust query/variables based on what you captured from DevTools
RA_QUERY = """
query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $pageSize: Int) {
  eventListings(filters: $filters, pageSize: $pageSize, page: 1, type: CLUB) {
    data {
      id
      event {
        title
        date
        startTime
        venue { name address { address1 } }
        contentUrl
        images { filename }
      }
    }
  }
}
"""

def scrape() -> list[dict]:
    payload = {
        "query": RA_QUERY,
        "variables": {
            "filters": {"areas": {"eq": 218}, "listingDate": {"gte": "TODAY"}},  # 218 = Ann Arbor area — verify
            "pageSize": 100,
        }
    }
    resp = requests.post(RA_GRAPHQL_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    events = []
    listings = data.get("data", {}).get("eventListings", {}).get("data", [])
    for listing in listings:
        ev = listing.get("event", {})
        date_str = ev.get("date", "")[:10]  # ISO date
        if not is_in_window(date_str):
            continue
        venue = ev.get("venue", {})
        url = f"https://ra.co{ev.get('contentUrl', '')}"
        images = ev.get("images", [])
        events.append(make_event(
            title=ev.get("title", ""),
            date=date_str,
            time=ev.get("startTime", ""),
            venue=venue.get("name", ""),
            address=venue.get("address", {}).get("address1", ""),
            url=url,
            source=SOURCE,
            category=CATEGORY,
            tags=["music", "electronic"],
            image_url=images[0].get("filename") if images else None,
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_resident_advisor.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/resident_advisor.py tests/test_resident_advisor.py tests/fixtures/resident_advisor.json
git commit -m "feat: add Resident Advisor scraper"
```

---

### Task 15: Ann Arbor Observer scraper

**Files:**
- Create: `scrapers/observer.py`
- Create: `tests/fixtures/observer.html`
- Create: `tests/test_observer.py`

- [ ] **Step 1: Inspect and capture fixture**

Visit `https://annarborobserver.com/` and find their events calendar or listings page. The Observer likely lists events as HTML articles. Save fixture HTML of the events listing page.

- [ ] **Step 2: Write failing test**

```python
# tests/test_observer.py
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE = (Path(__file__).parent / "fixtures" / "observer.html").read_text()


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
        from scrapers.observer import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.observer import scrape
        for e in scrape():
            assert e["source"] == "observer"
            assert e["category"] == "community"


def test_events_in_window():
    with patch("scrapers.observer.RateLimitedSession") as cls:
        cls.return_value = _mock_session(FIXTURE)
        from scrapers.observer import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_observer.py -v
```

- [ ] **Step 4: Implement `scrapers/observer.py`**

```python
# scrapers/observer.py
"""Scraper for Ann Arbor Observer events listings."""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)
SOURCE = "observer"
CATEGORY = "community"
EVENTS_URL = "https://annarborobserver.com/events/"  # verify URL at implementation time

def scrape() -> list[dict]:
    session = RateLimitedSession()
    events = []
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    for item in soup.select("REPLACE_WITH_EVENT_CONTAINER_SELECTOR"):
        title = item.select_one("REPLACE_TITLE_SELECTOR").get_text(strip=True)
        date_parsed = parse_date(item.select_one("REPLACE_DATE_SELECTOR").get_text(strip=True))
        if not date_parsed or not is_in_window(date_parsed.isoformat()):
            continue
        link = item.select_one("a")
        url = link["href"] if link else None
        if url and not url.startswith("http"):
            url = "https://annarborobserver.com" + url
        events.append(make_event(
            title=title,
            date=date_parsed.isoformat(),
            time=item.select_one("REPLACE_TIME_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_TIME_SELECTOR") else "",
            venue=item.select_one("REPLACE_VENUE_SELECTOR").get_text(strip=True) if item.select_one("REPLACE_VENUE_SELECTOR") else "",
            url=url,
            source=SOURCE,
            category=CATEGORY,
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_observer.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/observer.py tests/test_observer.py tests/fixtures/observer.html
git commit -m "feat: add Ann Arbor Observer scraper"
```

---

### Task 16: Eventbrite scraper

**Files:**
- Create: `scrapers/eventbrite.py`
- Create: `tests/fixtures/eventbrite.json`
- Create: `tests/test_eventbrite.py`

- [ ] **Step 1: Find the API approach**

Eventbrite has a public search API. Use the search endpoint:
`https://www.eventbrite.com/api/v3/destination/search/`

Open DevTools on `https://www.eventbrite.com/d/mi--ann-arbor/events/` and capture the API request. Key parameters: `place.address`, `dates`, `page_size`. Save a sample response to `tests/fixtures/eventbrite.json`.

- [ ] **Step 2: Write failing test**

```python
# tests/test_eventbrite.py
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "eventbrite.json").read_text())


def test_scrape_returns_list():
    with patch("scrapers.eventbrite.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE
        mock_get.return_value = mock_resp

        from scrapers.eventbrite import scrape
        assert isinstance(scrape(), list)


def test_events_source():
    with patch("scrapers.eventbrite.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE
        mock_get.return_value = mock_resp

        from scrapers.eventbrite import scrape
        for e in scrape():
            assert e["source"] == "eventbrite"
            assert e["category"] == "community"
            assert e["url"].startswith("http")


def test_events_in_window():
    with patch("scrapers.eventbrite.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = FIXTURE
        mock_get.return_value = mock_resp

        from scrapers.eventbrite import scrape
        from scrapers.base import is_in_window
        for e in scrape():
            assert is_in_window(e["date"])
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_eventbrite.py -v
```

- [ ] **Step 4: Implement `scrapers/eventbrite.py`**

```python
# scrapers/eventbrite.py
"""Scraper for Eventbrite (Ann Arbor/Ypsilanti area events)."""
import logging
import requests
from datetime import date, timedelta
from scrapers.base import make_event, is_in_window

logger = logging.getLogger(__name__)
SOURCE = "eventbrite"
CATEGORY = "community"

SEARCH_URL = "https://www.eventbrite.com/api/v3/destination/search/"

def scrape() -> list[dict]:
    today = date.today()
    end = today + timedelta(days=30)
    params = {
        "place.address": "Ann Arbor, MI",
        "dates": f"{today.isoformat()}T00:00:00,{end.isoformat()}T23:59:59",
        "page_size": 50,
        "expand": "event",
    }
    resp = requests.get(SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    events = []
    # Parse based on fixture structure captured from DevTools
    for item in data.get("events", {}).get("results", []):
        date_str = item.get("start_date", "")[:10]
        if not is_in_window(date_str):
            continue
        events.append(make_event(
            title=item.get("name", ""),
            date=date_str,
            time=item.get("start_time", ""),
            venue=item.get("primary_venue", {}).get("name", ""),
            address=item.get("primary_venue", {}).get("address", {}).get("localized_address_display", ""),
            url=item.get("url", ""),
            source=SOURCE,
            category=CATEGORY,
            image_url=item.get("image", {}).get("url"),
        ))
    return events
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_eventbrite.py -v
```

- [ ] **Step 6: Commit**

```bash
git add scrapers/eventbrite.py tests/test_eventbrite.py tests/fixtures/eventbrite.json
git commit -m "feat: add Eventbrite scraper"
```

---

## Chunk 6: Frontend

### Task 17: Static frontend — `docs/index.html`

**Files:**
- Create: `docs/index.html`

> No separate test file — verify manually by opening in browser and by running a quick sanity check.

- [ ] **Step 1: Create the directory**

```bash
mkdir -p docs
```

- [ ] **Step 2: Create `docs/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A2 Events — Ann Arbor & Ypsilanti</title>
  <style>
    /* ── Reset & base ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f8f8f6;
      --surface: #ffffff;
      --border: #e2e2dc;
      --text: #1a1a18;
      --muted: #6b6b65;
      --accent: #2d6a4f;
      --accent-light: #d8f3dc;
      --arts: #6b4c9e;
      --arts-light: #ede7f6;
      --community: #d4691e;
      --community-light: #fef3e2;
      --today: #2d6a4f;
      --selected: #2d6a4f;
    }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: var(--bg); color: var(--text); min-height: 100vh; }

    /* ── Nav ── */
    nav { background: var(--surface); border-bottom: 1px solid var(--border);
          padding: 0 1.5rem; display: flex; align-items: center; gap: 2rem;
          position: sticky; top: 0; z-index: 100; height: 56px; }
    .site-title { font-weight: 700; font-size: 1.1rem; color: var(--accent); text-decoration: none; }
    .tabs { display: flex; gap: 0; }
    .tab { padding: 0.5rem 1rem; border: none; background: none; cursor: pointer;
           font-size: 0.9rem; color: var(--muted); border-bottom: 2px solid transparent;
           transition: color 0.15s, border-color 0.15s; }
    .tab:hover { color: var(--text); }
    .tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }

    /* ── Layout ── */
    .layout { display: grid; grid-template-columns: 260px 1fr; gap: 0; max-width: 1200px;
              margin: 0 auto; padding: 1.5rem; gap: 1.5rem; }
    @media (max-width: 768px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { display: none; }
    }

    /* ── Mini calendar ── */
    .sidebar { position: sticky; top: 72px; align-self: start; }
    .mini-cal { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                padding: 1rem; }
    .cal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
    .cal-title { font-weight: 600; font-size: 0.95rem; }
    .cal-nav { background: none; border: none; cursor: pointer; color: var(--muted);
               font-size: 1.1rem; padding: 0.2rem 0.5rem; border-radius: 4px; }
    .cal-nav:hover { background: var(--bg); color: var(--text); }
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
    .cal-dow { font-size: 0.7rem; color: var(--muted); text-align: center; padding: 0.25rem 0;
               font-weight: 600; }
    .cal-day { aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
               font-size: 0.8rem; border-radius: 50%; cursor: pointer; position: relative;
               transition: background 0.1s; }
    .cal-day:hover { background: var(--bg); }
    .cal-day.other-month { color: var(--muted); opacity: 0.4; }
    .cal-day.today { font-weight: 700; color: var(--today); }
    .cal-day.selected { background: var(--selected); color: white; }
    .cal-day.has-events::after { content: ''; position: absolute; bottom: 2px; left: 50%;
                                  transform: translateX(-50%); width: 4px; height: 4px;
                                  border-radius: 50%; background: var(--accent); }
    .cal-day.selected::after { background: white; }
    .cal-day.empty { cursor: default; }

    /* ── Event list ── */
    .main { min-height: 400px; }
    .date-group { margin-bottom: 1.75rem; }
    .date-label { font-size: 0.8rem; font-weight: 700; text-transform: uppercase;
                  letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.75rem;
                  padding-bottom: 0.4rem; border-bottom: 1px solid var(--border); }
    .event-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
                  padding: 1rem 1.25rem; margin-bottom: 0.75rem; display: flex; gap: 1rem;
                  align-items: flex-start; transition: box-shadow 0.15s; }
    .event-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .event-thumb { width: 64px; height: 64px; border-radius: 8px; object-fit: cover; flex-shrink: 0;
                   background: var(--bg); }
    .event-thumb-placeholder { width: 64px; height: 64px; border-radius: 8px; flex-shrink: 0;
                                background: var(--bg); display: flex; align-items: center;
                                justify-content: center; font-size: 1.5rem; }
    .event-body { flex: 1; min-width: 0; }
    .event-title { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.25rem;
                   white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .event-meta { font-size: 0.82rem; color: var(--muted); margin-bottom: 0.4rem; }
    .event-footer { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
    .badge { display: inline-block; font-size: 0.7rem; font-weight: 600; padding: 0.15rem 0.5rem;
             border-radius: 100px; text-transform: uppercase; letter-spacing: 0.04em; }
    .badge-arts { background: var(--arts-light); color: var(--arts); }
    .badge-community { background: var(--community-light); color: var(--community); }
    .event-link { margin-left: auto; font-size: 0.82rem; color: var(--accent); text-decoration: none;
                  white-space: nowrap; }
    .event-link:hover { text-decoration: underline; }

    .empty-state { text-align: center; padding: 3rem 1rem; color: var(--muted); }
    .empty-state p { margin-bottom: 0.5rem; }

    .loading { text-align: center; padding: 3rem; color: var(--muted); }
  </style>
</head>
<body>

<nav>
  <a class="site-title" href="#">A2 Events</a>
  <div class="tabs">
    <button class="tab active" data-category="all">All</button>
    <button class="tab" data-category="arts_culture">Arts &amp; Culture</button>
    <button class="tab" data-category="community">Community</button>
  </div>
</nav>

<div class="layout">
  <aside class="sidebar">
    <div class="mini-cal">
      <div class="cal-header">
        <button class="cal-nav" id="prev-month">&#8249;</button>
        <span class="cal-title" id="cal-title"></span>
        <button class="cal-nav" id="next-month">&#8250;</button>
      </div>
      <div class="cal-grid" id="cal-dow">
        <div class="cal-dow">Su</div><div class="cal-dow">Mo</div>
        <div class="cal-dow">Tu</div><div class="cal-dow">We</div>
        <div class="cal-dow">Th</div><div class="cal-dow">Fr</div>
        <div class="cal-dow">Sa</div>
      </div>
      <div class="cal-grid" id="cal-days"></div>
    </div>
  </aside>

  <main class="main" id="event-list">
    <div class="loading">Loading events…</div>
  </main>
</div>

<script>
  // ── State ──
  const state = {
    events: [],
    category: "all",
    selectedDate: null,         // "YYYY-MM-DD" or null (show all)
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth(),
  };

  // ── Helpers ──
  const today = () => new Date().toISOString().slice(0, 10);

  function formatDateLabel(dateStr) {
    const d = new Date(dateStr + "T12:00:00");
    const now = new Date();
    const t = new Date(today() + "T12:00:00");
    if (dateStr === today()) return "Today — " + d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    const diff = Math.round((d - t) / 86400000);
    if (diff === 1) return "Tomorrow — " + d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  }

  function categoryBadge(cat) {
    if (cat === "arts_culture") return '<span class="badge badge-arts">Arts &amp; Culture</span>';
    if (cat === "community") return '<span class="badge badge-community">Community</span>';
    return "";
  }

  function categoryEmoji(cat) {
    if (cat === "arts_culture") return "🎵";
    if (cat === "community") return "🏘️";
    return "📅";
  }

  // ── Filtering ──
  function filteredEvents() {
    return state.events.filter(e => {
      if (state.category !== "all" && e.category !== state.category) return false;
      if (state.selectedDate && e.date !== state.selectedDate) return false;
      return true;
    });
  }

  function eventDatesSet() {
    const cats = state.category;
    return new Set(state.events.filter(e => cats === "all" || e.category === cats).map(e => e.date));
  }

  // ── Render events ──
  function renderEvents() {
    const list = document.getElementById("event-list");
    const events = filteredEvents();

    if (!events.length) {
      list.innerHTML = `<div class="empty-state">
        <p>No events found for this selection.</p>
        <p>Try a different date or category.</p>
      </div>`;
      return;
    }

    // Group by date
    const byDate = {};
    events.forEach(e => { (byDate[e.date] = byDate[e.date] || []).push(e); });

    list.innerHTML = Object.keys(byDate).sort().map(date => `
      <div class="date-group">
        <div class="date-label">${formatDateLabel(date)}</div>
        ${byDate[date].map(e => `
          <div class="event-card">
            ${e.image_url
              ? `<img class="event-thumb" src="${e.image_url}" alt="" loading="lazy" onerror="this.style.display='none'">`
              : `<div class="event-thumb-placeholder">${categoryEmoji(e.category)}</div>`}
            <div class="event-body">
              <div class="event-title" title="${e.title}">${e.title}</div>
              <div class="event-meta">${e.time ? e.time + " · " : ""}${e.venue}</div>
              <div class="event-footer">
                ${categoryBadge(e.category)}
                <a class="event-link" href="${e.url}" target="_blank" rel="noopener">More Info →</a>
              </div>
            </div>
          </div>
        `).join("")}
      </div>
    `).join("");
  }

  // ── Render mini calendar ──
  function renderCalendar() {
    const MONTHS = ["January","February","March","April","May","June",
                    "July","August","September","October","November","December"];
    document.getElementById("cal-title").textContent =
      MONTHS[state.calMonth] + " " + state.calYear;

    const dates = eventDatesSet();
    const t = today();
    const firstDay = new Date(state.calYear, state.calMonth, 1).getDay();
    const daysInMonth = new Date(state.calYear, state.calMonth + 1, 0).getDate();

    let html = "";
    // Empty cells before first day
    for (let i = 0; i < firstDay; i++) html += `<div class="cal-day empty"></div>`;

    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${state.calYear}-${String(state.calMonth + 1).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
      const classes = [
        "cal-day",
        dateStr === t ? "today" : "",
        dateStr === state.selectedDate ? "selected" : "",
        dates.has(dateStr) ? "has-events" : "",
      ].filter(Boolean).join(" ");
      html += `<div class="${classes}" data-date="${dateStr}">${d}</div>`;
    }

    document.getElementById("cal-days").innerHTML = html;

    // Attach click handlers
    document.querySelectorAll(".cal-day[data-date]").forEach(el => {
      el.addEventListener("click", () => {
        const d = el.dataset.date;
        state.selectedDate = state.selectedDate === d ? null : d;
        renderCalendar();
        renderEvents();
      });
    });
  }

  // ── Init ──
  async function init() {
    try {
      const resp = await fetch("events.json");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      state.events = data.events || [];
      state.selectedDate = today();
    } catch (e) {
      console.error("Failed to load events.json:", e);
      state.events = [];
    }

    // Tab clicks
    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        state.category = tab.dataset.category;
        renderCalendar();
        renderEvents();
      });
    });

    // Calendar nav
    document.getElementById("prev-month").addEventListener("click", () => {
      state.calMonth--;
      if (state.calMonth < 0) { state.calMonth = 11; state.calYear--; }
      renderCalendar();
    });
    document.getElementById("next-month").addEventListener("click", () => {
      state.calMonth++;
      if (state.calMonth > 11) { state.calMonth = 0; state.calYear++; }
      renderCalendar();
    });

    renderCalendar();
    renderEvents();
  }

  init();
</script>
</body>
</html>
```

- [ ] **Step 3: Create a minimal `docs/events.json` for local testing**

```json
{
  "generated_at": "2026-03-13T06:00:00Z",
  "event_count": 2,
  "events": [
    {
      "id": "ark-2026-03-14-test-show",
      "title": "Test Show",
      "date": "2026-03-14",
      "time": "8:00 PM",
      "venue": "The Ark",
      "address": "316 S Main St, Ann Arbor, MI",
      "category": "arts_culture",
      "tags": ["music"],
      "description": "A test event.",
      "url": "https://theark.org",
      "source": "ark",
      "also_listed_at": [],
      "image_url": null,
      "possible_duplicate": false,
      "scraped_at": "2026-03-13T06:00:00Z"
    },
    {
      "id": "observer-2026-03-15-community-meetup",
      "title": "Community Meetup",
      "date": "2026-03-15",
      "time": "6:30 PM",
      "venue": "Downtown Library",
      "address": "343 S 5th Ave, Ann Arbor, MI",
      "category": "community",
      "tags": [],
      "description": "A community gathering.",
      "url": "https://annarborobserver.com",
      "source": "observer",
      "also_listed_at": [],
      "image_url": null,
      "possible_duplicate": false,
      "scraped_at": "2026-03-13T06:00:00Z"
    }
  ]
}
```

- [ ] **Step 4: Verify frontend in browser**

```bash
cd docs && python -m http.server 8080
```

Open `http://localhost:8080` in a browser. Verify:
- Events display in the list for today/tomorrow
- Category tabs filter correctly
- Mini calendar shows, days with events have dot indicators
- Clicking a calendar day filters the list
- "More Info →" links open correctly

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/events.json
git commit -m "feat: add static frontend with hybrid calendar UI"
```

---

## Chunk 7: GitHub Actions Pipeline & Final Wiring

### Task 18: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/scrape.yml`
- Create: `data/raw/.gitkeep`

- [ ] **Step 1: Create workflow file**

```bash
mkdir -p .github/workflows
touch data/raw/.gitkeep
```

- [ ] **Step 2: Write `.github/workflows/scrape.yml`**

```yaml
name: Scrape Events

on:
  schedule:
    - cron: '0 6 * * *'    # Daily at 6 AM UTC
  workflow_dispatch:         # Manual trigger

permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright browsers
        run: playwright install chromium --with-deps

      - name: Run scrapers
        run: python run_scrapers.py

      - name: Merge and deduplicate
        run: python merge.py

      - name: Commit updated events
        run: |
          git config user.name "events-bot"
          git config user.email "events-bot@users.noreply.github.com"
          git add docs/events.json data/raw/
          git diff --cached --quiet && echo "No changes to commit" || \
            git commit -m "chore: update events $(date -u +%Y-%m-%d)"
          git push
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/scrape.yml data/raw/.gitkeep
git commit -m "chore: add GitHub Actions daily scrape workflow"
```

---

### Task 19: README and GitHub Pages setup

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# A2 Events

A daily-updating events calendar for Ann Arbor, Ypsilanti, and Washtenaw County.

**Live site:** https://your-org.github.io/a2events (update after enabling GitHub Pages)

## How it works

- Python scrapers in `scrapers/` fetch events daily from local venues and community sources
- `run_scrapers.py` orchestrates all scrapers, saving per-source JSON to `data/raw/`
- `merge.py` deduplicates events using fuzzy matching and writes `docs/events.json`
- `docs/index.html` is a static site served by GitHub Pages

The pipeline runs automatically via GitHub Actions every day at 6 AM UTC.

## Adding a new scraper

1. Create `scrapers/<name>.py` with a `scrape() -> list[dict]` function
2. Add `<name>` to `SCRAPER_NAMES` in `run_scrapers.py`
3. Add tests to `tests/test_<name>.py` with a fixture in `tests/fixtures/`

## Running locally

```bash
pip install -r requirements.txt
playwright install chromium
python run_scrapers.py    # fetch events
python merge.py           # dedup → docs/events.json
cd docs && python -m http.server 8080  # view site
```

## Sources

**Arts & Culture:** The Ark, Michigan Theater, Hill Auditorium, Kerrytown Concert House,
Blind Pig, Conor O'Neill's, Blue Llama Jazz Club, Detroit Street Filling Station, Resident Advisor

**Community:** Ann Arbor Observer, Eventbrite
```

- [ ] **Step 2: Enable GitHub Pages**

In the GitHub repository settings:
- Go to Settings → Pages
- Source: Deploy from a branch
- Branch: `main` / `docs` folder

- [ ] **Step 3: Commit README**

```bash
git add README.md
git commit -m "docs: add README with setup and contribution guide"
```

---

### Task 20: Run full test suite

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run full pipeline locally end-to-end**

```bash
python run_scrapers.py
python merge.py
```

Check that `docs/events.json` is updated and contains merged events.

- [ ] **Step 3: Verify site locally**

```bash
cd docs && python -m http.server 8080
```

Open `http://localhost:8080`, verify events from all sources appear, categories filter correctly, and all "More Info →" links point to original listings.

- [ ] **Step 4: Final commit**

```bash
git add -A
git diff --cached --quiet || git commit -m "chore: final wiring and full pipeline verification"
git push
```

- [ ] **Step 5: Trigger GitHub Actions manually**

In the GitHub repo UI: Actions → Scrape Events → Run workflow.

Verify the workflow completes successfully and the site updates.
