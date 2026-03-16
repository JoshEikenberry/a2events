"""Scraper for City of Ann Arbor public calendar (a2gov.org via Trumba API)."""
import logging
import re

import requests

from scrapers.base import make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)

SOURCE = "city_ann_arbor"
CATEGORY = "city_ann_arbor"
FALLBACK_URL = "https://www.a2gov.org/calendar.aspx"
TRUMBA_JSON_URL = "https://www.trumba.com/calendars/city-of-ann-arbor.json"

MEETING_KEYWORDS = re.compile(
    r"\b(council|commission|board|meeting|hearing)\b", re.IGNORECASE
)


def _is_meeting(title: str) -> bool:
    return bool(MEETING_KEYWORDS.search(title))


def scrape() -> list[dict]:
    """Fetch and parse City of Ann Arbor events from the Trumba JSON API."""
    try:
        response = requests.get(TRUMBA_JSON_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.error("Failed to fetch City of Ann Arbor calendar: %s", exc)
        return []

    if not isinstance(data, list):
        logger.error("Unexpected response format from Trumba API")
        return []

    events = []
    for item in data:
        try:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            # Skip canceled events
            if item.get("canceled"):
                continue

            start_dt_str = item.get("startDateTime") or ""
            if not start_dt_str:
                continue
            date_parsed = parse_date(start_dt_str)
            if not date_parsed:
                continue
            date_str = date_parsed.isoformat()
            if not is_in_window(date_str):
                continue

            # Extract time from startDateTime (e.g. "2026-03-16T19:00:00")
            time_str = ""
            if "T" in start_dt_str:
                time_part = start_dt_str.split("T", 1)[1]
                # Only include time if it's not midnight (allDay events)
                if not item.get("allDay") and time_part and time_part != "00:00:00":
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(time_part, "%H:%M:%S")
                        time_str = dt.strftime("%-I:%M %p").lstrip("0") or dt.strftime("%I:%M %p")
                    except ValueError:
                        time_str = time_part

            url = (item.get("permaLinkUrl") or "").strip() or FALLBACK_URL

            venue = (item.get("location") or "").strip()

            tags = ["public_meeting"] if _is_meeting(title) else []

            events.append(make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=tags,
                description=(item.get("description") or "").strip(),
            ))
        except Exception as exc:
            logger.warning("city_ann_arbor: skipping event %r: %s", item.get("title"), exc)

    logger.info("city_ann_arbor: %d events in window", len(events))
    return events
