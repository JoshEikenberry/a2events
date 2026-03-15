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

---

## Phase 1: API-Based Scrapers

### 1. `scrapers/city_ann_arbor.py`

- **Source:** `data.a2gov.org` via the Socrata SODA API
- **Method:** REST GET returning JSON
- **Category:** `city_ann_arbor`
- **Tags:** Tag public meetings with `["public_meeting"]`
- **Notes:** Filter results to the standard 30-day window using Socrata query parameters where possible.

### 2. `scrapers/um_events.py`

- **Source:** `events.umich.edu` public REST API (`/json/feed`)
- **Method:** Paginated JSON responses; iterate pages until outside the 30-day window
- **Category:** `university_of_michigan`
- **Notes:** Filter by date range using API query parameters. Handle pagination gracefully — stop fetching when events fall outside the window.

### 3. `scrapers/um_athletics.py`

- **Source:** `mgoblue.com` schedules (REST or iCal endpoint)
- **Method:** REST or iCal, whichever provides a stable machine-readable feed
- **Category:** `um_athletics`
- **Sports covered:** Football, basketball, hockey, baseball, softball, soccer, volleyball (all major varsity sports)
- **Tags:** Tag each event with its sport name (e.g., `["hockey"]`, `["football"]`)
- **Notes:** Each sport may require a separate request. Consolidate results into a single list return.

---

## Phase 2: HTML Scrapers

### 4. `scrapers/washtenaw_county.py`

- **Source:** Washtenaw County official website
- **Method:** HTML scraping (BeautifulSoup or similar)
- **Category:** `washtenaw_county`
- **Tags:** Tag public meetings with `["public_meeting"]`
- **Notes:** Target the county's events or meetings calendar page. Parse date, title, location, and description from HTML. Be resilient to minor layout changes.

### 5. `scrapers/ypsilanti.py`

- **Source:** City of Ypsilanti official website
- **Method:** HTML scraping
- **Category:** `ypsilanti`
- **Tags:** Tag public meetings with `["public_meeting"]`
- **Notes:** Target the city's events or meetings calendar page. Parse date, title, location, and description from HTML.

### 6. `scrapers/eastern_michigan.py`

- **Source:** Eastern Michigan University campus events
- **Method:** HTML scraping
- **Category:** `eastern_michigan`
- **Notes:** Target EMU's public events calendar. No meeting-tag required unless EMU events warrant it in future iterations.

---

## Frontend Changes (`docs/index.html`)

### Navigation Tabs

Expand from 3 tabs to 9 tabs:

| Tab label | Filter value |
|---|---|
| All | _(no filter)_ |
| Arts & Culture | `arts` |
| Community | `community` |
| City of A2 | `city_ann_arbor` |
| Washtenaw County | `washtenaw_county` |
| Ypsilanti | `ypsilanti` |
| U-M | `university_of_michigan` |
| U-M Athletics | `um_athletics` |
| EMU | `eastern_michigan` |

### Mobile Responsiveness

- On mobile viewports, the horizontal tab bar collapses to a `<select>` dropdown.
- This replaces the current behavior of horizontal overflow scrolling on small screens.

### New CSS Variables

Six new category color variables are added:

| Category | CSS variable / color | Notes |
|---|---|---|
| `city_ann_arbor` | `#1565c0` (blue) | |
| `washtenaw_county` | `#00695c` (teal) | |
| `ypsilanti` | `#b71c1c` (red) | |
| `university_of_michigan` | `#ffcb05` (maize) | Text color: `#00274c` (navy) |
| `um_athletics` | `#00274c` (navy) | |
| `eastern_michigan` | `#215732` (forest green) | |

### Meeting Badge

Event cards display a **"Meeting" badge** when the event's `tags` array includes `"public_meeting"`. The badge is a visual indicator only — no filtering by tag is added in this phase.

---

## Testing

Each new scraper requires:

- **Fixture file** in `tests/fixtures/<source>.json` (API-based) or `tests/fixtures/<source>.html` (HTML scrapers), captured from the live source at time of implementation.
- **3–5 tests** per scraper covering:
  1. Returns a list (not `None`, not a dict)
  2. Correct `source` and `category` fields on returned events
  3. In-window filtering (events outside 30 days are excluded)
  4. Required fields present (`title`, `date`, `url`, `source`, `category`)
  5. Tag correctness where applicable (e.g., `"public_meeting"` or sport name tags)

All existing **104 tests** must continue to pass without modification.

---

## Non-Goals

- Extending the 30-day event window for any source.
- Adding user-facing tag filtering (e.g., a "Meetings only" toggle) beyond the Meeting badge.
- Any additional event sources beyond the 6 specified in this spec.
