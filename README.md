# Ann Arbor / Ypsilanti Events Calendar

A daily-updating public events calendar for Ann Arbor, Ypsilanti, and Washtenaw County. It aggregates local venues and public calendars, deduplicates listings, and publishes a static site.

**Live site:** `https://josheikenberry.github.io/a2events/`

---

## Architecture

```
scrapers/*.py
    └── data/raw/<source>.json   (one file per source)
         └── merge.py
              └── docs/events.json
                   └── docs/index.html  (static site, served by GitHub Pages)
```

1. Each scraper module fetches events from one source and writes `data/raw/<source>.json`.
2. `merge.py` reads all raw files, deduplicates events with fuzzy matching (rapidfuzz), and writes `docs/events.json`.
3. `docs/index.html` is a static page that reads `events.json` at load time and renders the calendar client-side.
4. GitHub Actions runs the full pipeline daily at 6 AM UTC and pushes the updated data files back to `main`, triggering a GitHub Pages deployment.

If a scraper raises an error or returns an invalid result, the runner retains its last raw file; expired events are removed during the merge. A successful empty result replaces the previous file. Individual malformed listings may be skipped, so retained data can still be incomplete or stale.

Event dates and rolling windows use the `America/Detroit` timezone. Events with different known start times are not merged; listings with unknown or ambiguous times are kept separately to avoid losing performances. Event IDs include occurrence details, so the first refresh after this change can cause RSS readers to treat existing events as new.

---

## Setup

**Requirements:** Python 3.11+

```bash
pip install -r requirements.txt
playwright install chromium --with-deps
```

---

## Running locally

**Run all scrapers** (writes to `data/raw/`):

```bash
python run_scrapers.py
```

**Merge and deduplicate** (writes to `docs/events.json`):

```bash
python merge.py
```

**Run both in sequence:**

```bash
python run_scrapers.py && python merge.py
```

Serve the site locally (browsers may block `fetch` when opening the file directly):

```bash
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000/`.

The calendar defaults to a dark theme. Search titles, venues, descriptions, and tags, or combine the source and date-range filters with a category, tag, or calendar day. The RSS links provide all-events, arts and community feeds.

---

## Running tests

```bash
python -m pytest tests/ -v
```

---

## Adding a new scraper

1. Create `scrapers/<name>.py`. The module must expose a single function:

   ```python
   def scrape() -> list[dict]:
       ...
   ```

2. Build each event dict using `make_event()` from `scrapers/base.py`:

   ```python
   from scrapers.base import make_event, RateLimitedSession

   def scrape() -> list[dict]:
       session = RateLimitedSession()
       # fetch and parse your source...
       return [
           make_event(
               title="Event Name",
               date="2026-03-15",       # ISO 8601 (YYYY-MM-DD)
               time="7:00 PM",
               venue="Venue Name",
               url="https://...",
               source="<name>",         # matches your module name
               category="arts_culture", # or "community", "sports", etc.
               tags=["music"],
               description="...",
               address="...",
               image_url=None,
           )
       ]
   ```

   - Use `RateLimitedSession` for HTTP requests (built-in retry + 1.5 s delay).
   - Use `parse_ical_feed()` from `scrapers/base.py` if the source provides an iCal feed.
   - Use `is_in_window()` to filter events outside the 30-day window.

3. Add the module name (string) to `SCRAPER_NAMES` in `run_scrapers.py`.

4. That's it. The orchestrator will pick it up automatically on the next run.

---

## Data sources

| Source | URL |
|---|---|
| The Ark | https://theark.org |
| Michigan Theater | https://michtheater.org |
| Hill Auditorium (UMS) | https://ums.org |
| Kerrytown Concert House | https://kerrytownconcerthouse.com |
| The Blind Pig | https://blindpigmusic.com |
| Conor O'Neill's | https://conoroneills.com |
| Blue Llama Jazz Club | https://bluellamaclub.com |
| Detroit Street Filling Station | https://detroitstreetfillingstation.com |
| Resident Advisor | https://ra.co |
| Ann Arbor Observer | https://annarborobserver.com |
| Eventbrite | https://eventbrite.com |
| Ann Arbor District Library | https://aadl.org |
| City of Ann Arbor | https://www.a2gov.org |
| Washtenaw County | https://www.washtenaw.org |
| City of Ypsilanti | https://cityofypsilanti.com |
| Eastern Michigan University | https://www.emich.edu |
| University of Michigan events | https://events.umich.edu |
| University of Michigan athletics | https://mgoblue.com |
| Ann Arbor Art Center | https://www.annarborartcenter.org/events/list/ |
| Riverside Arts Center | https://www.riversidearts.org/events/ |

The Art Center scraper pages through its public events API for the full 30-day window. Coverage is limited to events published by that API. The shared iCalendar parser expands recurrence rules and exceptions within the window; it does not invent daily occurrences for a multi-day event.

### Additional source research

- [Dexter District Library](https://dexter.lib.mi.us/events/) offers an RSS feed, but the observed feed only contained ten events; 30-day coverage needs investigation.
- [Chelsea District Library](https://chelseadistrictlibrary.libnet.info/events) and [Matthaei Botanical Gardens and Nichols Arboretum](https://mbgna.umich.edu/events/all) have public event pages; pagination and recurring occurrences need investigation.
- [Ypsilanti District Library](https://ypsilibrary.events.mylibrary.digital/) blocked automated access during research; an authorized feed or access arrangement is needed.

---

## GitHub Pages setup

1. Push the repository to GitHub.
2. Go to **Settings → Pages**.
3. Under **Source**, select **Deploy from a branch**.
4. Set branch to `main` and folder to `/docs`.
5. Save. The site will be live at `https://<username>.github.io/<repo>/`.

The **Scrape & Deploy** GitHub Actions workflow (`.github/workflows/scrape.yml`) runs daily at 6 AM UTC and also supports manual triggers via **Actions → Scrape & Deploy → Run workflow**.
