"""Scraper for University of Michigan events (events.umich.edu)."""
import logging
import requests
from scrapers.base import make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)

SOURCE = "um_events"
CATEGORY = "university_of_michigan"
API_URL = "https://events.umich.edu/list/json"
FALLBACK_URL = "https://events.umich.edu"


def scrape() -> list[dict]:
    """Fetch upcoming U-M events from the events.umich.edu JSON API.

    The API returns a dict keyed by occurrence ID (e.g. "143706-21893696"),
    where each value is an event object. Relevant fields:
      event_title, date_start, time_start, location_name, description, permalink
    """
    try:
        resp = requests.get(
            API_URL,
            params={"filter": "upcoming", "range": 30},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; A2EventsBot/1.0)"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Failed to fetch U-M events: %s", exc)
        return []

    # API returns a dict keyed by occurrence ID; values are event objects.
    # If for some reason it returns a list, handle that gracefully too.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = list(data.values())
    else:
        logger.error("Unexpected response type from U-M Events API: %s", type(data))
        return []

    events = []
    for item in items:
        try:
            title = (item.get("event_title") or item.get("combined_title") or "").strip()
            if not title:
                logger.warning("Skipping um_events item with no title")
                continue

            date_raw = item.get("date_start") or item.get("datetime_start") or ""
            date_parsed = parse_date(date_raw)
            if not date_parsed or not is_in_window(date_parsed.isoformat()):
                continue

            url = (item.get("permalink") or "").strip()
            if not url:
                url = FALLBACK_URL
            if not url.startswith("http"):
                url = "https://events.umich.edu" + url

            venue = (item.get("location_name") or "").strip()
            time_str = (item.get("time_start") or "").strip()
            description = (item.get("description") or "").strip()

            events.append(make_event(
                title=title,
                date=date_parsed.isoformat(),
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                description=description,
            ))
        except Exception as exc:
            logger.warning("Skipping um_events item %r: %s", item.get("event_title"), exc)

    logger.info("um_events: %d events in window", len(events))
    return events
