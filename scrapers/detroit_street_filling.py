"""Scraper for Detroit Street Filling Station / North Star Lounge (Ann Arbor, MI).

Detroit Street Filling Station is a vegan restaurant. The upstairs jazz club,
North Star Lounge, hosts live music events scraped here from nstarlounge.com.
"""
import html
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from scrapers.base import RateLimitedSession, is_in_window, make_event


SOURCE = "detroit_street_filling"
CATEGORY = "arts_culture"
EVENTS_URL = "https://www.nstarlounge.com/events?format=json"
VENUE = "Detroit Street Filling Station / North Star Lounge"
BASE_URL = "https://www.nstarlounge.com"
DETROIT = ZoneInfo("America/Detroit")


def scrape() -> list[dict]:
    """Fetch North Star Lounge events (upstairs at Detroit Street Filling Station)."""
    session = RateLimitedSession()
    response = session.get(EVENTS_URL)

    data = json.loads(response.text)
    if not isinstance(data, dict) or not isinstance(data.get("upcoming"), list):
        raise ValueError("detroit_street_filling: 'upcoming' field is not a list")
    upcoming = data["upcoming"]

    events = []
    for entry in upcoming:
        start_ms = entry.get("startDate")
        if not start_ms:
            continue

        dt = datetime.fromtimestamp(start_ms / 1000, tz=DETROIT)

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

        events.append(make_event(
            title=title,
            date=date_str,
            time=time_str,
            venue=VENUE,
            url=full_url,
            source=SOURCE,
            category=CATEGORY,
            tags=["music"],
            image_url=image_url,
        ))

    return events
