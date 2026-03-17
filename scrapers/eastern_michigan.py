"""Scraper for Eastern Michigan University events (today.emich.edu API).

www.emich.edu/events/ is blocked by Cloudflare IUAM and cannot be scraped.
today.emich.edu exposes a public JSON API that returns the same events
with no bot protection. The API returns a 7-day window per call; we make
5 weekly calls to cover the full 30-day window.
"""
import logging
from datetime import date, timedelta

from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, WINDOW_DAYS

logger = logging.getLogger(__name__)

SOURCE = "eastern_michigan"
CATEGORY = "eastern_michigan"
BASE_URL = "https://today.emich.edu"
EVENTS_API_URL = "https://today.emich.edu/api/calendar/events/{year}/{month}/{day}"
FALLBACK_URL = "https://today.emich.edu/calendar"


def scrape() -> list[dict]:
    """Fetch EMU campus events from the today.emich.edu JSON API."""
    session = RateLimitedSession()
    today = date.today()
    seen_ids: set = set()
    all_events: list[dict] = []

    # API returns a 7-day window per call; step weekly to cover WINDOW_DAYS
    for week_offset in range(0, WINDOW_DAYS, 7):
        start = today + timedelta(days=week_offset)
        url = EVENTS_API_URL.format(year=start.year, month=start.month, day=start.day)

        try:
            response = session.get(url)
            data = response.json()
        except Exception as exc:
            logger.error("eastern_michigan: failed to fetch week starting %s: %s", start, exc)
            continue

        grouped = data.get("groupedByDay", {})
        for day_events in grouped.values():
            for item in day_events:
                event_id = item.get("id")
                if event_id and event_id in seen_ids:
                    continue

                if item.get("is_canceled"):
                    continue

                title = (item.get("title") or "").strip()
                if not title:
                    continue

                # start_date format: "2026-03-17 00:00:00" — take date portion only
                date_str = (item.get("start_date") or "")[:10].strip()
                parsed_date = parse_date(date_str)
                if not parsed_date or not is_in_window(parsed_date.isoformat()):
                    continue

                url_event = f"{BASE_URL}/calendar/{event_id}" if event_id else FALLBACK_URL
                venue = (item.get("location") or "").strip()
                time_str = (item.get("start_time") or "").strip()
                description = (item.get("description") or "").strip()

                try:
                    all_events.append(make_event(
                        title=title,
                        date=parsed_date.isoformat(),
                        time=time_str,
                        venue=venue,
                        url=url_event,
                        source=SOURCE,
                        category=CATEGORY,
                        description=description,
                    ))
                    if event_id:
                        seen_ids.add(event_id)
                except ValueError as exc:
                    logger.warning("eastern_michigan: skipping %r: %s", title, exc)

    logger.info("eastern_michigan: %d events in window", len(all_events))
    return all_events
