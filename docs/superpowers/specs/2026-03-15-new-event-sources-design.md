# New Event Sources Design Spec

**Date:** 2026-03-15
**Status:** Draft

---

## Overview

This spec covers the expansion of the Ann Arbor local events aggregator with 6 new scrapers across 2 phases, plus frontend updates to support new category tabs. The goal is to broaden coverage to include government entities, the University of Michigan, and the broader Washtenaw County area.

---

## New Categories (Data Model)

Six new `category` values are added to the event schema. No schema migration is required — existing fields are unchanged.

| `category` value | Tab label |
|---|---|
| `city_ann_arbor` | City of Ann Arbor |
| `washtenaw_county` | Washtenaw County |
| `ypsilanti` | Ypsilanti |
| `university_of_michigan` | University of Michigan |
| `um_athletics` | U-M Athletics |
| `eastern_michigan` | Eastern Michigan University |

### Tags

- Government meetings are tagged `["public_meeting"]` in the `tags` array.
- Event cards with this tag display a **"Meeting" badge** in the UI.
- The 30-day event window is unchanged.
- `merge.py` and `run_scrapers.py` are unchanged; new scrapers are auto-discovered by the existing orchestrator.

### Missing URL Fallback

`make_event()` raises `ValueError` if `url` is `None` or empty. When a source does not provide a per-event deep-link URL, implementers must fall back to the source's main events/calendar page URL (e.g. `https://www.washtenaw.org/calendar`). Events with no title or no parseable date are silently dropped (logged at WARNING level).

### Error Handling for HTML Scrapers

When a required field (`title` or `date`) cannot be parsed from an HTML element, the event is dropped and a `logger.warning()` is emitted. This is consistent with the orchestrator's failure-isolation model — individual bad events do not raise exceptions.

---

## Phase 1: API-Based Scrapers

### 1. `scrapers/city_ann_arbor.py`

- **Source:** `https://www.a2gov.org/calendar.aspx` (HTML) — the city's public calendar. At implementation time, also check `https://data.a2gov.org/browse` for a Socrata events dataset; if one exists with date/title/URL fields, prefer the API. If not, fall back to HTML scraping.
- **Method:** HTML scraping (BeautifulSoup + `lxml`) unless a Socrata dataset is confirmed available.
- **Category:** `city_ann_arbor`
- **Tags:** Tag public meetings with `["public_meeting"]` (detect by title keywords: "council", "commission", "board", "meeting", "hearing")
- **Notes:** Filter to 30-day window. Missing venue falls back to `""`. Missing per-event URL falls back to `"https://www.a2gov.org/calendar.aspx"`.

### 2. `scrapers/um_events.py`

- **Source:** `events.umich.edu` public REST API
- **Method:** GET `https://events.umich.edu/list/json` (paginated). Pass `filter=upcoming` and date range params. At implementation time, verify the sort order of results (ascending vs. descending). If ascending: stop fetching when all events on a page exceed the 30-day window. If descending or unsorted: fetch all pages within the date range params and filter client-side with `is_in_window()`.
- **Category:** `university_of_michigan`
- **Notes:** Missing venue falls back to `""`.

### 3. `scrapers/um_athletics.py`

- **Source:** `mgoblue.com` per-sport iCal feeds (Sidearm Sports platform)
- **Method:** iCal feed per sport at `https://mgoblue.com/calendar.ashx/calendar.ics?sport_id=<id>` or equivalent. Inspect `https://mgoblue.com/sports/` at implementation time to confirm feed URLs and sport IDs.
- **Category:** `um_athletics`
- **Sports covered (exhaustive list):** football, men's basketball, women's basketball, men's hockey, women's hockey, baseball, softball, men's soccer, women's soccer, volleyball
- **Tags:** Each event is tagged with its sport name as a post-processing step after parsing (e.g. tag all events from the football feed with `["football"]`). `parse_ical_feed()` itself is not modified.
- **URL-less iCal events:** Athletics iCal feeds frequently omit the `URL` field. Because `parse_ical_feed()` silently drops URL-less VEVENTs, `um_athletics.py` must NOT use `parse_ical_feed()` directly. Instead, it must parse the iCal bytes manually (using `icalendar.Calendar.from_ical()`) and supply the sport's schedule page URL (e.g. `https://mgoblue.com/sports/football/schedule`) as the fallback `url` when the VEVENT has no `URL` property.
- **Fixtures:** One combined fixture file `tests/fixtures/um_athletics.ics` containing representative VEVENT blocks from multiple sports — some with `URL` fields, some without — to exercise the fallback logic. The scraper consolidates all sports into a single returned list.
- **Notes:** If a sport's feed URL returns a non-200 response, log a warning and continue with remaining sports.

---

## Phase 2: HTML Scrapers

All Phase 2 scrapers follow the same error handling rule: drop events missing title or date, log at WARNING level. Fall back to the source's calendar page URL when no per-event URL is available. Missing venue falls back to `""`.

### 4. `scrapers/washtenaw_county.py`

- **Source:** `https://www.washtenaw.org/calendar`
- **Method:** HTML scraping (BeautifulSoup + `lxml`)
- **Category:** `washtenaw_county`
- **Tags:** Tag public meetings with `["public_meeting"]`
- **Notes:** At implementation time, inspect the page structure and capture representative fixture HTML. Parse date, title, location, and description.

### 5. `scrapers/ypsilanti.py`

- **Source:** `https://www.cityofypsilanti.com/calendar`
- **Method:** HTML scraping (BeautifulSoup + `lxml`)
- **Category:** `ypsilanti`
- **Tags:** Tag public meetings with `["public_meeting"]`
- **Notes:** At implementation time, inspect the page structure and capture representative fixture HTML.

### 6. `scrapers/eastern_michigan.py`

- **Source:** `https://www.emich.edu/events/` (verify at implementation time)
- **Method:** HTML scraping (BeautifulSoup + `lxml`)
- **Category:** `eastern_michigan`
- **Notes:** No meeting-tag required unless EMU events warrant it in future iterations. Capture representative fixture HTML at implementation time. If the page is JavaScript-rendered and returns no parseable events, log a warning and return `[]` — do not raise.

---

## Frontend Changes (`docs/index.html`)

### Navigation Tabs

Expand from 3 tabs to 9 tabs:

| Tab label | Filter value (`category`) |
|---|---|
| All | _(no filter)_ |
| Arts & Culture | `arts_culture` |
| Community | `community` |
| City of A2 | `city_ann_arbor` |
| Washtenaw County | `washtenaw_county` |
| Ypsilanti | `ypsilanti` |
| U-M | `university_of_michigan` |
| U-M Athletics | `um_athletics` |
| EMU | `eastern_michigan` |

### Mobile Responsiveness

- On mobile viewports (≤720px), the horizontal tab bar collapses to a `<select>` dropdown.
- The dropdown options mirror the tab labels and filter values above.
- This replaces the current horizontal overflow scrolling on small screens.

### New CSS Variables

Six new category color variables are added to `:root`. The `university_of_michigan` maize color requires a navy text override (`#00274c`) applied to **both** the category badge on event cards and the active state of the tab/dropdown — anywhere the background color is `#ffcb05`.

| Category | Background color | Text color |
|---|---|---|
| `city_ann_arbor` | `#1565c0` | white |
| `washtenaw_county` | `#00695c` | white |
| `ypsilanti` | `#b71c1c` | white |
| `university_of_michigan` | `#ffcb05` (maize) | `#00274c` (navy) |
| `um_athletics` | `#00274c` (navy) | white |
| `eastern_michigan` | `#215732` | white |

### Meeting Badge

Event cards display a **"Meeting" badge** when the event's `tags` array includes `"public_meeting"`. The badge is a visual indicator only — no filtering by tag is added in this phase. The Meeting badge is rendered **after** the category badge (e.g. category badge first, then Meeting badge). Both badges may appear simultaneously on the same card.

---

## Testing

Each new scraper requires:

- **Fixture file** in `tests/fixtures/<source>.json` (API/JSON-based) or `tests/fixtures/<source>.html` (HTML scrapers), captured from the live source at time of implementation. For `um_athletics`, use a single combined `tests/fixtures/um_athletics.ics` file containing VEVENTs from multiple sports.
- **3–5 tests** per scraper covering:
  1. Returns a list (not `None`, not a dict)
  2. Correct `source` and `category` fields on returned events
  3. In-window filtering (events outside 30 days are excluded) — fixtures must include at least one in-window and one out-of-window event to make this test non-vacuous
  4. Required fields present (`title`, `date`, `url`, `source`, `category`)
  5. Tag correctness where applicable (e.g., `"public_meeting"` or sport name tags)

All existing **104 tests** must continue to pass without modification.

---

## Non-Goals

- Extending the 30-day event window for any source.
- Adding user-facing tag filtering (e.g., a "Meetings only" toggle) beyond the Meeting badge.
- Any additional event sources beyond the 6 specified in this spec.
- Modifying `parse_ical_feed()`, `make_event()`, `merge.py`, or `run_scrapers.py`.
