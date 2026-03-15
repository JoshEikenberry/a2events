"""Scraper for Resident Advisor (Ann Arbor / Michigan electronic/club events)."""
import logging

import requests

from scrapers.base import is_in_window, make_event

logger = logging.getLogger(__name__)

SOURCE = "resident_advisor"
CATEGORY = "arts_culture"
RA_GRAPHQL_URL = "https://ra.co/graphql"

# RA area IDs: 19 = Detroit metro, 360 = Michigan statewide
# Ann Arbor is not a standalone RA area; we use Michigan (360) and filter by address.
RA_AREA_ID = 360

RA_QUERY = """
query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $pageSize: Int) {
  eventListings(filters: $filters, pageSize: $pageSize, page: 1) {
    data {
      id
      event {
        title
        date
        startTime
        venue { name address }
        contentUrl
        images { filename }
      }
    }
  }
}
"""

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ra.co/events/us/annarbor",
    "Origin": "https://ra.co",
}

# Keywords to identify Ann Arbor events from the broader Michigan area
ANN_ARBOR_KEYWORDS = ["ann arbor", "48104", "48105", "48106", "48107", "48108", "48109"]


def _is_ann_arbor(address: str) -> bool:
    """Return True if the address appears to be in Ann Arbor."""
    addr_lower = (address or "").lower()
    return any(kw in addr_lower for kw in ANN_ARBOR_KEYWORDS)


def scrape() -> list[dict]:
    """Fetch RA Michigan-area events and return those in Ann Arbor within the window."""
    from datetime import date, timedelta

    today = date.today()
    end_date = today + timedelta(days=30)

    payload = {
        "query": RA_QUERY,
        "variables": {
            "filters": {
                "areas": {"eq": RA_AREA_ID},
                "listingDate": {
                    "gte": today.isoformat(),
                    "lte": end_date.isoformat(),
                },
            },
            "pageSize": 100,
        },
    }

    try:
        resp = requests.post(
            RA_GRAPHQL_URL, json=payload, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("resident_advisor: request failed: %s", exc)
        return []

    try:
        data = resp.json()
    except ValueError as exc:
        logger.error("resident_advisor: failed to parse JSON: %s", exc)
        return []

    listings = (
        data.get("data", {})
        .get("eventListings", {})
        .get("data", [])
    ) or []

    events = []
    for listing in listings:
        ev = listing.get("event") or {}

        date_str = (ev.get("date") or "")[:10]
        if not is_in_window(date_str):
            continue

        venue = ev.get("venue") or {}
        address = venue.get("address") or ""

        # Filter to Ann Arbor venues only
        if not _is_ann_arbor(address):
            continue

        content_url = ev.get("contentUrl") or ""
        if not content_url:
            logger.debug("resident_advisor: skipping event with no contentUrl: %s", ev.get("title"))
            continue
        url = f"https://ra.co{content_url}"

        title = ev.get("title") or ""
        if not title:
            continue

        images = ev.get("images") or []
        image_url = images[0].get("filename") if images else None

        # Parse time from startTime ISO string (e.g. "2026-03-21T22:00:00.000")
        start_time = ev.get("startTime") or ""
        time_str = ""
        if start_time and "T" in start_time:
            time_part = start_time.split("T")[1][:5]  # "22:00"
            try:
                from datetime import datetime as dt
                t = dt.strptime(time_part, "%H:%M")
                time_str = t.strftime("%-I:%M %p").lstrip("0") if hasattr(t, "strftime") else time_part
            except Exception:
                time_str = time_part

        try:
            event = make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=venue.get("name") or "",
                address=address,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=["music", "electronic"],
                image_url=image_url,
            )
        except ValueError as exc:
            logger.warning("resident_advisor: skipping event %r: %s", title, exc)
            continue

        events.append(event)

    logger.info("resident_advisor: found %d Ann Arbor events", len(events))
    return events
