"""Scraper for Detroit Street Filling Station / North Star Lounge (Ann Arbor, MI).

Detroit Street Filling Station is a vegan restaurant. The upstairs jazz club,
North Star Lounge, hosts live music events scraped here from nstarlounge.com.
"""
import html
import json
import logging
from datetime import datetime

from scrapers.base import RateLimitedSession, is_in_window, make_event

logger = logging.getLogger(__name__)

SOURCE = "detroit_street_filling"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.nstarlounge.com/events?format=json"
VENUE = "Detroit Street Filling Station / North Star Lounge"
BASE_URL = "https://www.nstarlounge.com"


def scrape() -> list[dict]:
    """Fetch North Star Lounge events (upstairs at Detroit Street Filling Station)."""
    session = RateLimitedSession()
    response = session.get(EVENTS_URL)

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        logger.error("detroit_street_filling: failed to parse JSON response: %s", exc)
        return []

    upcoming = data.get("upcoming", [])
    if not isinstance(upcoming, list):
        logger.warning("detroit_street_filling: 'upcoming' field is not a list")
        return []

    events = []
    for entry in upcoming:
        start_ms = entry.get("startDate")
        if not start_ms:
            continue

        try:
            dt = datetime.fromtimestamp(start_ms / 1000)
        except (OSError, OverflowError, ValueError) as exc:
            logger.warning("detroit_street_filling: invalid startDate %r: %s", start_ms, exc)
            continue

        date_str = dt.date().isoformat()
        if not is_in_window(date_str):
            continue

        title = html.unescape(entry.get("title", "")).strip()
        if not title:
            continue

        full_url = entry.get("fullUrl", "").strip()
        if not full_url:
            continue
        if not full_url.startswith("http"):
            full_url = BASE_URL + full_url

        # Format time string, stripping leading zero (e.g., "7:30 PM" not "07:30 PM")
        time_str = dt.strftime("%I:%M %p").lstrip("0") or "12:00 AM"

        image_url = entry.get("assetUrl") or None

        try:
            event = make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=VENUE,
                url=full_url,
                source=SOURCE,
                category=CATEGORY,
                tags=["music"],
                image_url=image_url,
            )
        except ValueError as exc:
            logger.warning("detroit_street_filling: skipping event %r: %s", title, exc)
            continue

        events.append(event)

    return events
