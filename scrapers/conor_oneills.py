"""Scraper for Conor O'Neill's Irish Pub (conoroneills.com) in Ann Arbor."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from scrapers.base import RateLimitedSession, make_event, is_in_window

logger = logging.getLogger(__name__)

SOURCE = "conor_oneills"
CATEGORY = "arts_culture"
VENUE = "Conor O'Neill's"
ADDRESS = "318 South Main Street, Ann Arbor, MI 48104"
BASE_URL = "https://www.conoroneills.com"
EVENTS_URL = f"{BASE_URL}/events?format=json"
DETROIT = ZoneInfo("America/Detroit")


def _parse_event(item: dict) -> dict | None:
    """Parse a single event item from the Squarespace JSON API response."""
    title = (item.get("title") or "").strip()
    if not title:
        return None

    start_ms = item.get("startDate")
    if not start_ms:
        return None

    dt = datetime.fromtimestamp(start_ms / 1000, tz=DETROIT)
    date_str = dt.date().isoformat()
    time_str = dt.strftime("%I:%M %p").lstrip("0")

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
    response = session.get(EVENTS_URL)
    data = response.json()
    if not isinstance(data, dict) or not any(section in data for section in ("upcoming", "past")):
        raise ValueError("Conor O'Neill's response has no event sections")

    events = []
    # "upcoming" contains future events; "past" may contain recently-started multi-day events
    for section in ("upcoming", "past"):
        items = data.get(section, [])
        if not isinstance(items, list):
            raise ValueError(f"Conor O'Neill's {section} section is not a list")
        for item in items:
            event = _parse_event(item)
            if event:
                events.append(event)

    logger.info("Conor O'Neill's: %d events in window", len(events))
    return events
