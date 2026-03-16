# AADL Scraper Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scraper for the Ann Arbor District Library (AADL) public events calendar that returns `community` category events within the 30-day window.

**Architecture:** HTML scraper against `https://www.aadl.org/events-feed/upcoming` (paginated, `?page=N`). Parses `.views-row.search-result` elements with BeautifulSoup. Stops paginating when a page returns 0 rows or all rows are past the window. Registered in `run_scrapers.py` for daily automation.

**Tech Stack:** Python 3.11, requests, BeautifulSoup4, lxml, dateutil, pytest

**Spec:** `docs/superpowers/specs/2026-03-15-aadl-scraper-design.md`

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Create | `tests/fixtures/aadl.html` | Minimal static HTML fixture with 4 test events |
| Create | `tests/test_aadl.py` | 7 unit tests (TDD — written before implementation) |
| Create | `scrapers/aadl.py` | The scraper module |
| Modify | `run_scrapers.py` | Add `"aadl"` to `SCRAPER_NAMES` |

---

## Chunk 1: Fixture and Failing Tests

### Task 1: Create test fixture and write all failing tests

**Files:**
- Create: `tests/fixtures/aadl.html`
- Create: `tests/test_aadl.py`

- [ ] **Step 1: Create the fixture file**

Create `tests/fixtures/aadl.html` with the following content. It contains 4 events covering all test scenarios — 3 in-window, 1 far-future (out-of-window), and 1 with a missing href (for URL fallback testing). **Important:** If implementing after May 2026, update the in-window dates to be within 30 days of today.

```html
<!DOCTYPE html>
<html lang="en">
<head><title>Events | Ann Arbor District Library</title></head>
<body>
<main id="main-content">
<div class="view-content">
<div class="views-results" id="search-results">

<!-- Event 1: in-window, has type label, has venue, has valid URL -->
<div class="views-row search-result l-overflow-clear">
<div class="node-container">
<div class="mat-type-icon">
<p>Preschool Storytimes</p>
</div>
<div class="views-right-padding node-body">
<h2 class="no-margin"><a href="/node/100001">Preschool Storytimes</a></h2>
<p>Thursday April 10, 2026: 10:30am to
11:00am<br/>
Pittsfield Branch: Program Room</p>
</div>
</div>
</div>

<!-- Event 2: in-window, type label with ampersand (tag normalization), has venue -->
<div class="views-row search-result l-overflow-clear">
<div class="node-container">
<div class="mat-type-icon">
<p>Lectures &amp; Panel Discussions</p>
</div>
<div class="views-right-padding node-body">
<h2 class="no-margin"><a href="/node/100002">Author Event: Local Voices</a></h2>
<p>Friday April 11, 2026: 7:00pm to
8:30pm<br/>
Downtown Library: 4th Floor Program Room</p>
</div>
</div>
</div>

<!-- Event 3: OUT-OF-WINDOW (far future — must be excluded by scraper) -->
<div class="views-row search-result l-overflow-clear">
<div class="node-container">
<div class="mat-type-icon">
<p>Author Events</p>
</div>
<div class="views-right-padding node-body">
<h2 class="no-margin"><a href="/node/100003">Future Author Talk</a></h2>
<p>Monday September 15, 2027: 7:00pm to
8:00pm<br/>
Downtown Library: 4th Floor Program Room</p>
</div>
</div>
</div>

<!-- Event 4: in-window, MISSING href (URL fallback test) -->
<div class="views-row search-result l-overflow-clear">
<div class="node-container">
<div class="mat-type-icon">
<p>Crafts</p>
</div>
<div class="views-right-padding node-body">
<h2 class="no-margin"><a>Sewing Lab Open Session</a></h2>
<p>Saturday April 12, 2026: 1:00pm to
3:00pm<br/>
Downtown Library: Secret Lab</p>
</div>
</div>
</div>

</div>
</div>
</main>
</body>
</html>
```

- [ ] **Step 2: Write all 7 failing tests**

Create `tests/test_aadl.py`:

```python
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
```

- [ ] **Step 3: Run tests — confirm they all FAIL**

```bash
cd /c/vibecode
python -m pytest tests/test_aadl.py -v 2>&1
```

Expected: 7 failures with `ModuleNotFoundError: No module named 'scrapers.aadl'` or `ImportError`.

- [ ] **Step 4: Commit the fixture and failing tests**

```bash
git add tests/fixtures/aadl.html tests/test_aadl.py
git commit -m "test: add AADL scraper fixture and failing tests"
```

---

## Chunk 2: Implementation and Registration

### Task 2: Implement the scraper

**Files:**
- Create: `scrapers/aadl.py`

- [ ] **Step 5: Implement `scrapers/aadl.py`**

```python
"""Scraper for Ann Arbor District Library (AADL) events calendar."""
import logging
import re

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from scrapers.base import make_event, is_in_window, parse_date, RateLimitedSession

logger = logging.getLogger(__name__)

SOURCE = "aadl"
CATEGORY = "community"
BASE_URL = "https://www.aadl.org"
FEED_URL = "https://www.aadl.org/events-feed/upcoming"
FALLBACK_URL = "https://www.aadl.org/events"


def _normalize_tag(label: str) -> str:
    """Normalize event type label to a tag string.

    Examples:
        "Preschool Storytimes"        -> "preschool_storytimes"
        "Lectures & Panel Discussions" -> "lectures_panel_discussions"
    """
    return re.sub(r"[&\s_]+", "_", label.lower().strip()).strip("_")


def _parse_page(html: str) -> tuple[list[dict], int]:
    """Parse events from one page of feed HTML.

    Returns (in_window_events, total_rows_on_page).
    total_rows == 0 means no more pages exist.
    """
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(".views-row.search-result")
    total = len(rows)
    events = []

    for row in rows:
        # --- Title and URL ---
        title_link = row.select_one("h2.no-margin a")
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        if not title:
            continue

        href = (title_link.get("href") or "").strip()
        url = (BASE_URL + href) if href else FALLBACK_URL

        # --- Date, time, venue from .node-body p ---
        body_p = row.select_one(".node-body p")
        if not body_p:
            logger.warning("aadl: no body paragraph for %r, skipping", title)
            continue

        # Split on <br>: text before = date/time, text after = venue
        br = body_p.find("br")
        if br:
            before = [
                s.get_text() if hasattr(s, "get_text") else str(s)
                for s in reversed(list(br.previous_siblings))
            ]
            after = [
                s.get_text() if hasattr(s, "get_text") else str(s)
                for s in br.next_siblings
            ]
            date_time_text = " ".join("".join(before).split())
            venue = " ".join("".join(after).split())
        else:
            date_time_text = " ".join(body_p.get_text().split())
            venue = ""

        # --- Parse date ---
        if ": " in date_time_text:
            date_part, time_part = date_time_text.split(": ", 1)
        else:
            date_part = date_time_text
            time_part = ""

        parsed_date = parse_date(date_part)
        if not parsed_date:
            logger.warning("aadl: unparseable date %r for %r, skipping", date_part, title)
            continue

        date_str = parsed_date.isoformat()
        if not is_in_window(date_str):
            continue

        # --- Parse time (start time only, e.g. "10:30am to 11:00am" -> "10:30 AM") ---
        time_str = ""
        if time_part:
            start_time = time_part.split(" to ")[0].strip()
            if start_time:
                try:
                    dt = dateutil_parser.parse(start_time)
                    time_str = dt.strftime("%I:%M %p").lstrip("0")
                except (ValueError, OverflowError):
                    pass

        # --- Event type tag ---
        type_el = row.select_one(".mat-type-icon p")
        tags = []
        if type_el:
            label = type_el.get_text(strip=True)
            if label:
                tags = [_normalize_tag(label)]

        try:
            events.append(make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=tags,
            ))
        except ValueError as exc:
            logger.warning("aadl: skipping %r: %s", title, exc)

    return events, total


def scrape() -> list[dict]:
    """Fetch and parse AADL upcoming events within the 30-day window."""
    session = RateLimitedSession()
    all_events: list[dict] = []
    page = 0

    while True:
        url = f"{FEED_URL}?page={page}"
        try:
            response = session.get(url)
        except Exception as exc:
            logger.error("aadl: failed to fetch page %d: %s", page, exc)
            break

        events, total_rows = _parse_page(response.text)
        all_events.extend(events)

        # No more pages
        if total_rows == 0:
            break

        # All rows on this page were past the window — stop early (dates are ascending)
        if len(events) == 0:
            break

        page += 1

    logger.info("aadl: %d events in window", len(all_events))
    return all_events
```

- [ ] **Step 6: Run the tests — all 7 should pass**

```bash
python -m pytest tests/test_aadl.py -v 2>&1
```

Expected output:
```
tests/test_aadl.py::test_returns_list PASSED
tests/test_aadl.py::test_source_and_category PASSED
tests/test_aadl.py::test_in_window_filtering PASSED
tests/test_aadl.py::test_required_fields PASSED
tests/test_aadl.py::test_event_type_tag PASSED
tests/test_aadl.py::test_url_fallback PASSED
tests/test_aadl.py::test_pagination_stops PASSED
7 passed
```

If any test fails, diagnose and fix before continuing.

- [ ] **Step 7: Run the full test suite — no regressions**

```bash
python -m pytest --tb=short 2>&1
```

Expected: all previously passing tests still pass (was 104+; now 111+).

- [ ] **Step 8: Commit the scraper**

```bash
git add scrapers/aadl.py
git commit -m "feat: add AADL scraper (community, HTML pagination)"
```

---

### Task 3: Register in orchestrator and verify live

**Files:**
- Modify: `run_scrapers.py`

- [ ] **Step 9: Add `"aadl"` to `SCRAPER_NAMES` in `run_scrapers.py`**

Find the `SCRAPER_NAMES` list (currently ends with `"um_athletics"`) and append `"aadl"`:

```python
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
```

- [ ] **Step 10: Run the full test suite one more time**

```bash
python -m pytest --tb=short 2>&1
```

Expected: all tests pass.

- [ ] **Step 11: Run the scraper live against the real site**

```bash
python -c "
import logging, json
logging.basicConfig(level=logging.INFO)
from scrapers.aadl import scrape
events = scrape()
print(f'Events found: {len(events)}')
if events:
    e = events[0]
    print(f'First event: {e[\"title\"]} | {e[\"date\"]} | {e[\"venue\"]}')
    print(f'  url: {e[\"url\"]}')
    print(f'  tags: {e[\"tags\"]}')
" 2>&1
```

Expected: 20–60 events, dates within 30 days, no errors. Verify at least one event has a non-empty tag.

- [ ] **Step 12: Regenerate `docs/events.json` and verify AADL events appear**

```bash
python merge.py 2>&1
python -c "
import json
from collections import Counter
data = json.load(open('docs/events.json'))
cats = Counter(e['category'] for e in data['events'])
print('Total:', data['event_count'])
for k, v in sorted(cats.items()):
    print(f'  {k}: {v}')
" 2>&1
```

Expected: `community` count is higher than before; AADL events are present (check by filtering `source == "aadl"`).

- [ ] **Step 13: Commit and push**

```bash
git add run_scrapers.py docs/events.json data/raw/aadl.json
git commit -m "feat: register AADL scraper in run_scrapers.py and regenerate events"
git push
```
