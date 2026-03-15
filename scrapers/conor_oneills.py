"""Scraper for Conor O'Neill's Irish Pub (conoroneills.com) in Ann Arbor."""
import logging
from datetime import datetime, timezone

from scrapers.base import RateLimitedSession, make_event, is_in_window

logger = logging.getLogger(__name__)

SOURCE = "conor_oneills"
CATEGORY = "arts_culture"
VENUE = "Conor O'Neill's"
ADDRESS = "318 South Main Street, Ann Arbor, MI 48104"
BASE_URL = "https://www.conoroneills.com"
EVENTS_URL = f"{BASE_URL}/events?format=json"


def _parse_event(item: dict) -> dict | None:
    """Parse a single event item from the Squarespace JSON API response."""
    title = (item.get("title") or "").strip()
    if not title:
        return None

    start_ms = item.get("startDate")
    if not start_ms:
        return None

    try:
        dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).astimezone()
        date_str = dt.date().isoformat()
        time_str = dt.strftime("%I:%M %p").lstrip("0")
    except (OSError, OverflowError, ValueError) as exc:
        logger.warning("Could not parse startDate %s: %s", start_ms, exc)
        return None

    if not is_in_window(date_str):
        return None

    url_id = item.get("urlId") or item.get("fullUrl") or ""
    if not url_id:
        return None

    # Build absolute URL
    full_url = item.get("fullUrl", "")
    if full_url.startswith("/"):
        event_url = BASE_URL + full_url
    elif full_url.startswith("http"):
        event_url = full_url
    else:
        event_url = f"{BASE_URL}/events/{url_id}"

    # Strip HTML tags from excerpt for description
    excerpt = item.get("excerpt") or ""
    import re
    description = re.sub(r"<[^>]+>", "", excerpt).strip()

    image_url = item.get("assetUrl") or None

    return make_event(
        title=title,
        date=date_str,
        time=time_str,
        venue=VENUE,
        address=ADDRESS,
        url=event_url,
        source=SOURCE,
        category=CATEGORY,
        description=description,
        image_url=image_url,
        tags=["irish", "live-entertainment"],
    )


def scrape() -> list[dict]:
    """Fetch and parse Conor O'Neill's events from the Squarespace JSON API."""
    session = RateLimitedSession()
    try:
        response = session.get(EVENTS_URL)
        data = response.json()
    except Exception as exc:
        logger.error("Failed to fetch Conor O'Neill's events: %s", exc)
        return []

    events = []
    # "upcoming" contains future events; "past" may contain recently-started multi-day events
    for section in ("upcoming", "past"):
        for item in data.get(section, []):
            try:
                event = _parse_event(item)
                if event:
                    events.append(event)
            except Exception as exc:
                logger.warning("Skipping event %r: %s", item.get("title"), exc)

    logger.info("Conor O'Neill's: %d events in window", len(events))
    return events
