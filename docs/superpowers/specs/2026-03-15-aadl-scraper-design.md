# AADL Scraper Design Spec

**Date:** 2026-03-15
**Status:** Approved

---

## Overview

Add a scraper for the Ann Arbor District Library (AADL) public events calendar. AADL hosts a wide variety of community events — storytimes, author talks, crafts, ESL groups, lectures, and more — that belong in the `community` category alongside Observer and Eventbrite events.

---

## Source

- **URL:** `https://www.aadl.org/events-feed/upcoming`
- **Pagination:** `?page=N` (0-indexed); ~20 events per page; pages are in ascending date order
- **Method:** HTML scraping with BeautifulSoup + lxml
- **No API or iCal feed available**

---

## Scraper: `scrapers/aadl.py`

### Constants

| Name | Value |
|---|---|
| `SOURCE` | `"aadl"` |
| `CATEGORY` | `"community"` |
| `BASE_URL` | `"https://www.aadl.org"` |
| `FEED_URL` | `"https://www.aadl.org/events-feed/upcoming"` |
| `FALLBACK_URL` | `"https://www.aadl.org/events"` |

### HTML Structure (per event)

Each event is a `.views-row.search-result` div containing:

```
.mat-type-icon p          → event type label (e.g. "Preschool Storytimes", "Author Events")
h2.no-margin > a          → title text + href="/node/XXXXX"
.node-body p              → date/time line + venue line (separated by <br>)
```

**Date/time format:** `"Monday March 16, 2026: 10:30am to 11:00am"`
- Date parsed from the portion before the first `: ` (e.g. `"Monday March 16, 2026"`)
- Time: take the start time from after the `: `, before ` to ` (e.g. `"10:30am"`); parse with `dateutil` and format as `"10:30 AM"` using `strftime("%I:%M %p").lstrip("0")` — matching the convention in other scrapers
- If the line has no `: `, treat the whole line as a date and leave time as `""`

**Venue extraction:** text after the `<br>` in `.node-body p`. If no `<br>` is present, venue falls back to `""`.

**Venue:** text after the `<br>` in the `.node-body p` element.

**URL:** prepend `BASE_URL` to the relative `/node/XXXXX` href. Fall back to `FALLBACK_URL` if href is missing.

### Tags

The event type label from `.mat-type-icon p` is normalized to a tag:
- Strip whitespace, lowercase, replace spaces and `&` with `_`
- Example: `"Lectures & Panel Discussions"` → `"lectures_panel_discussions"`
- Tag is omitted if the label is empty

No `public_meeting` tagging — AADL does not host government meetings.

### Pagination Logic

```
page = 0
loop:
    fetch /events-feed/upcoming?page={page}
    parse events from page
    filter to in-window events (is_in_window)
    if page had 0 rows total → stop (no more pages)
    if all rows on page are past the 30-day window → stop early
    else → page += 1, continue
```

This avoids fetching all ~16 pages when only the first few fall within the 30-day window.

### Error Handling

- Fetch failure (non-200 or exception): log `logger.error`, return `[]`
- Missing title or unparseable date: skip event, log `logger.warning`
- Missing venue: falls back to `""`

---

## Testing: `tests/test_aadl.py`

**Fixture:** `tests/fixtures/aadl.html` — captured from live `/events-feed/upcoming` page, trimmed to ~4 events including:
- At least 1 in-window event
- At least 1 out-of-window event (date > 30 days out)
- At least 1 event with a venue
- At least 1 event with an event-type tag

**Tests (7):**

1. `test_returns_list` — `scrape()` returns a list (mocked HTTP, single page)
2. `test_source_and_category` — all events have `source="aadl"`, `category="community"`
3. `test_in_window_filtering` — out-of-window event from fixture is excluded
4. `test_required_fields` — all events have non-empty `title`, `date`, `url`, `source`, `category`
5. `test_event_type_tag` — event with type label produces a normalized tag in `tags`
6. `test_url_fallback` — event with missing href in fixture produces `url=FALLBACK_URL`
7. `test_pagination_stops` — mock two pages: page 0 has in-window events, page 1 returns empty (0 rows); verify scraper fetches exactly 2 pages and stops

---

## Non-Goals

- Filtering by AADL event category/type (all types are included)
- Scraping individual event detail pages for richer descriptions
- Any changes to `merge.py`, `run_scrapers.py`, the frontend, or existing scrapers
