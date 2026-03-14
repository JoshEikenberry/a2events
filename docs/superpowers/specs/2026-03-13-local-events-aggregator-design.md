# Local Events Aggregator — Design Spec
**Date:** 2026-03-13
**Status:** Approved

## Overview

A public-facing events aggregator for the Washtenaw County / Ann Arbor / Ypsilanti area, hosted on GitHub Pages. Daily Python scrapers run via GitHub Actions, collect events from multiple sources, deduplicate, and publish a static site with a hybrid calendar UI.

---

## Goals

- Aggregate local events from multiple sources into one place
- Organize events by category (Arts & Culture, Community, with City/Gov and University planned for later)
- Deduplicate events that appear on multiple sources
- Display events on a public website with links back to original listings
- Update automatically every day with no manual intervention

## Non-Goals (for now)

- User accounts or personalization
- Event submission by the public
- City/government API integration (planned later)
- University of Michigan API integration (planned later)
- Push notifications or email digests

---

## Architecture

```
GitHub Actions (daily cron: 6 AM UTC)
        │
        ▼
┌─────────────────────────────────┐
│  scrapers/                      │
│    ark.py                       │
│    michigan_theater.py          │
│    hill_auditorium.py           │
│    kerrytown.py                 │
│    blind_pig.py                 │
│    conor_oneills.py             │
│    blue_llama.py                │
│    detroit_street_filling.py    │
│    resident_advisor.py          │
│    observer.py                  │
│    eventbrite.py                │
└──────────────┬──────────────────┘
               │ saves to data/raw/<source>.json
               ▼
┌─────────────────────────────────┐
│  merge.py                       │
│  - loads all per-source JSONs   │
│  - fuzzy deduplication          │
│  - writes docs/events.json      │
└──────────────┬──────────────────┘
               ▼
        docs/events.json   (committed to repo)
        docs/index.html    (static frontend)
               │
               ▼
        GitHub Pages (public site)
```

**Key architectural decisions:**
- Each scraper is an independent Python module — failures are logged but don't block other scrapers
- Per-source raw JSON saved to `data/raw/` for auditing and debugging
- Only `docs/` is served by GitHub Pages
- Pipeline can be triggered manually via `workflow_dispatch` for testing

---

## Event Sources

### Arts & Culture / Music
| Source | Scraping Strategy |
|---|---|
| The Ark | HTML parsing or iCal feed |
| Michigan Theater | HTML parsing or JSON-LD |
| Hill Auditorium | HTML parsing |
| Kerrytown Concert House | HTML parsing |
| Blind Pig | HTML parsing |
| Conor O'Neill's | HTML parsing |
| Blue Llama Jazz Club | HTML parsing |
| Detroit Street Filling Station (+ jazz club) | HTML parsing |
| Resident Advisor (Ann Arbor filtered) | Public API or structured search |

### Community / Neighborhood
| Source | Scraping Strategy |
|---|---|
| Ann Arbor Observer | HTML parsing |
| Eventbrite (filtered to Ann Arbor/Ypsi) | Public API |

### Planned Future Sources
- Ann Arbor city calendar (API available)
- University of Michigan events (API available)

---

## Data Model

### Event Schema

```json
{
  "id": "ark-2026-03-15-the-war-on-drugs",
  "title": "The War on Drugs",
  "date": "2026-03-15",
  "time": "8:00 PM",
  "venue": "The Ark",
  "address": "316 S Main St, Ann Arbor, MI",
  "category": "arts_culture",
  "tags": ["music", "rock"],
  "description": "An evening with The War on Drugs...",
  "url": "https://theark.org/events/...",
  "source": "ark",
  "also_listed_at": [],
  "image_url": "https://...",
  "possible_duplicate": false,
  "scraped_at": "2026-03-13T06:00:00Z"
}
```

**Field notes:**
- `id` — deterministic slug (`source-date-title-slug`), stable across runs
- `category` — one of `arts_culture`, `community` (extensible)
- `tags` — freeform per-source labels (e.g. `jazz`, `comedy`, `family-friendly`)
- `url` — always the original event listing; never null
- `also_listed_at` — additional source URLs if event was merged from multiple sources
- `possible_duplicate` — flagged but not hidden on frontend (reserved for future admin view)
- `image_url` — optional, used for card thumbnails

### events.json Envelope

```json
{
  "generated_at": "2026-03-13T06:05:00Z",
  "event_count": 142,
  "events": [ ... ]
}
```

---

## Scraper Interface

Every scraper is a Python module in `scrapers/` exposing one function:

```python
def scrape() -> list[dict]:
    """Fetch events from this source. Returns list of Event dicts."""
```

Shared utilities in `scrapers/base.py`:
- `make_event(**kwargs) -> dict` — validates schema, generates `id` slug
- HTTP session with retry logic and polite rate limiting
- Date/time parsing helpers
- iCal feed parser helper

Scraping strategies used across sources:
- **HTML + BeautifulSoup** — most venue sites
- **JSON-LD / structured data** — where available (faster, more reliable)
- **iCal feed** — where venues publish `.ics` feeds
- **Playwright (headless browser)** — for JS-rendered pages
- **Public APIs** — Eventbrite, Resident Advisor, future city/UofM

---

## Deduplication

Handled in `merge.py` after all scrapers complete.

**Algorithm:**
1. Group all events by date
2. Within each date, compare all pairs using weighted fuzzy score:
   - Title similarity via `rapidfuzz` — 60% weight
   - Venue name similarity — 30% weight
   - Time match — 10% weight
3. Score ≥ 85%: merge into one event
   - Keep the version with more detail (longer description, has image)
   - Collect all source URLs into `also_listed_at`
4. Score 70–85%: keep both events, set `possible_duplicate: true` on both
5. Score < 70%: treat as distinct events

---

## Frontend

Single-page static site at `docs/index.html`. Vanilla HTML, CSS, and JavaScript — no framework or build tools.

**Layout:**
- **Top nav** — site title + category tabs: `All | Arts & Culture | Community`
- **Left sidebar** — mini month calendar; clicking a day filters the list; prev/next month navigation; collapses on mobile
- **Main area** — scrollable event cards sorted chronologically, filtered by active category + selected date
- **Event card** — title, venue, date/time, category badge, optional thumbnail, "More Info →" link to original listing

**Behavior:**
- `events.json` fetched once on page load, all filtering done client-side in memory
- Default view: today's date selected, showing next 30 days worth of events
- Category tabs filter across all dates; date selection filters within active category
- Design follows established calendar UI conventions (FullCalendar-inspired mini calendar, clean card grid)

**GitHub Pages config:**
- `docs/` folder served as site root
- `docs/CNAME` for custom domain (optional)
- `.gitignore` excludes `data/raw/` if desired (or keep for audit trail)

---

## GitHub Actions Pipeline

File: `.github/workflows/scrape.yml`

```yaml
on:
  schedule:
    - cron: '0 6 * * *'   # Daily at 6 AM UTC
  workflow_dispatch:        # Manual trigger for testing

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: playwright install chromium  # for JS-heavy sites
      - run: python run_scrapers.py       # runs all scrapers, logs failures
      - run: python merge.py             # dedup + write docs/events.json
      - run: |
          git config user.name "events-bot"
          git config user.email "bot@github.com"
          git add docs/events.json data/raw/
          git diff --cached --quiet || git commit -m "chore: update events $(date -u +%Y-%m-%d)"
          git push
```

**Dependencies (requirements.txt):**
- `requests` — HTTP
- `beautifulsoup4` — HTML parsing
- `rapidfuzz` — fuzzy string matching for dedup
- `playwright` — headless browser for JS-rendered sites
- `icalendar` — iCal feed parsing
- `python-dateutil` — robust date parsing

---

## Project Structure

```
/
├── .github/
│   └── workflows/
│       └── scrape.yml
├── scrapers/
│   ├── base.py
│   ├── ark.py
│   ├── michigan_theater.py
│   ├── hill_auditorium.py
│   ├── kerrytown.py
│   ├── blind_pig.py
│   ├── conor_oneills.py
│   ├── blue_llama.py
│   ├── detroit_street_filling.py
│   ├── resident_advisor.py
│   ├── observer.py
│   └── eventbrite.py
├── data/
│   └── raw/              # per-source JSON output (gitignored optional)
├── docs/
│   ├── index.html        # static frontend
│   └── events.json       # merged/deduped events (committed daily)
├── run_scrapers.py       # orchestrator: runs all scrapers, saves raw JSON
├── merge.py              # merge + dedup → events.json
├── requirements.txt
└── README.md
```

---

## Time Range

Scrapers fetch events within a **rolling 30-day window** from today. Events outside this window are excluded from `events.json`. This keeps the payload small and the site focused on actionable upcoming events.
