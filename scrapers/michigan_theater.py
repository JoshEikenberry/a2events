"""Scraper for Michigan Theater Ann Arbor (marquee-arts.org)."""
import json
import logging
import re

from scrapers.base import RateLimitedSession, is_in_window, make_event

logger = logging.getLogger(__name__)

SOURCE = "michigan_theater"
CATEGORY = "arts_culture"
CALENDAR_URL = "https://marquee-arts.org/calendar/"


def scrape() -> list[dict]:
    """Fetch the Marquee Arts calendar and return Michigan Theater events in window."""
    session = RateLimitedSession()
    response = session.get(CALENDAR_URL)

    # The calendar page embeds a JS variable: var calendarEvents = [...];
    match = re.search(r"var calendarEvents = (\[.*?\]);", response.text, re.DOTALL)
    if not match:
        logger.warning("michigan_theater: calendarEvents variable not found on calendar page")
        return []

    try:
        raw_events = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.error("michigan_theater: failed to parse calendarEvents JSON: %s", exc)
        return []

    events = []
    for entry in raw_events:
        date_str = entry.get("start", "")[:10]
        if not is_in_window(date_str):
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        venue = entry.get("venue", "").strip() or "Michigan Theater"
        thumbnail = entry.get("thumbnail") or None

        times = entry.get("times") or []
        if not times:
            # No showings listed — skip (no URL available)
            continue

        # Each showing becomes its own event
        for showing in times:
            url = showing.get("link", "").strip()
            if not url:
                continue

            time_str = showing.get("time", "").strip()

            try:
                event = make_event(
                    title=title,
                    date=date_str,
                    time=time_str,
                    venue=venue,
                    url=url,
                    source=SOURCE,
                    category=CATEGORY,
                    tags=["film"] if "theatre" in venue.lower() or "theater" in venue.lower() else [],
                    image_url=thumbnail,
                )
            except ValueError as exc:
                logger.warning("michigan_theater: skipping event %r: %s", title, exc)
                continue

            events.append(event)

    return events
