"""Scraper for Eventbrite (Ann Arbor/Ypsilanti area events)."""
import logging
import requests

from scrapers.base import make_event, is_in_window

logger = logging.getLogger(__name__)

SOURCE = "eventbrite"
CATEGORY = "community"

# Bounding box covering Ann Arbor and Ypsilanti, MI
# west, south, east, north
BBOX = "-84.3,42.2,-83.6,42.4"

SEARCH_URL = "https://www.eventbrite.com/api/v3/destination/search/"
HOME_URL = "https://www.eventbrite.com/d/mi--ann-arbor/events/"


def _get_locality(locations: list) -> str:
    """Extract city name from the locations list."""
    for loc in locations:
        if loc.get("type") == "locality":
            return loc.get("name", "")
    return ""


def scrape() -> list[dict]:
    """Fetch events from the Eventbrite internal search API and return a list of event dicts."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Referer": HOME_URL,
        "Origin": "https://www.eventbrite.com",
    })

    # Fetch homepage to acquire session cookies (including csrftoken)
    session.get(HOME_URL, timeout=15)

    csrf = next(
        (c.value for c in session.cookies if c.name == "csrftoken"),
        None,
    )
    if csrf:
        session.headers["X-CSRFToken"] = csrf

    payload = {
        "event_search": {
            "q": "",
            "dates": "current_future",
            "bbox": BBOX,
            "page": 1,
            "page_size": 50,
        }
    }

    resp = session.post(SEARCH_URL, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    events = []
    for item in data.get("events", {}).get("results", []):
        date_str = item.get("start_date", "")
        if not is_in_window(date_str):
            continue

        url = item.get("url", "") or ""
        if not url:
            logger.debug("Skipping event with no URL: %s", item.get("name"))
            continue

        locality = _get_locality(item.get("locations", []))

        try:
            event = make_event(
                title=item.get("name", ""),
                date=date_str,
                time=item.get("start_time", ""),
                venue=locality,
                address=locality,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                description=item.get("summary", "") or "",
                image_url=None,
            )
        except ValueError as exc:
            logger.warning("Skipping event due to error: %s", exc)
            continue

        events.append(event)

    logger.info("Eventbrite: found %d events in window", len(events))
    return events
