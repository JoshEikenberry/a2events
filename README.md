# Ann Arbor / Ypsilanti Events Calendar

A daily-updating public events calendar for Ann Arbor, Ypsilanti, and Washtenaw County. Aggregates events from 11 local venues and listing sites, deduplicates them, and publishes a static site updated every morning.

**Live site:** `https://<username>.github.io/<repo>/`

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

Then open `docs/index.html` in a browser to view the result.

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

---

## GitHub Pages setup

1. Push the repository to GitHub.
2. Go to **Settings → Pages**.
3. Under **Source**, select **Deploy from a branch**.
4. Set branch to `main` and folder to `/docs`.
5. Save. The site will be live at `https://<username>.github.io/<repo>/`.

The **Scrape & Deploy** GitHub Actions workflow (`.github/workflows/scrape.yml`) runs daily at 6 AM UTC and also supports manual triggers via **Actions → Scrape & Deploy → Run workflow**.
