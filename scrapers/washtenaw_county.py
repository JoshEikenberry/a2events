"""Scraper for Washtenaw County public meetings calendar (washtenaw.org).

The county's calendar page (washtenaw.org/calendar) redirects to a 404.
The actual meeting data is served via the CivicClerk JSON API at
https://washtenawcomi.api.civicclerk.com/v1/Events. Events are linked via
the public portal at https://washtenawcomi.portal.civicclerk.com/event/{id}.
"""
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date, WINDOW_DAYS

logger = logging.getLogger(__name__)

SOURCE = "washtenaw_county"
CATEGORY = "washtenaw_county"
FALLBACK_URL = "https://www.washtenaw.org/calendar"
PORTAL_BASE = "https://washtenawcomi.portal.civicclerk.com/event"

MEETING_KEYWORDS = re.compile(
    r"\b(council|commission|board|committee|meeting|hearing)\b", re.IGNORECASE
)


def _build_api_params() -> dict:
    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=WINDOW_DAYS)
    start_str = today.isoformat() + "T00:00:00Z"
    end_str = end.isoformat() + "T23:59:59Z"
    return {
        "$filter": f"startDateTime ge {start_str} and startDateTime le {end_str}",
        "$orderby": "startDateTime asc",
    }


def _parse_venue(event_location: dict | None) -> str:
    """Build a venue string from the eventLocation object."""
    if not event_location or not isinstance(event_location, dict):
        return ""
    parts = [
        event_location.get("address1") or "",
        event_location.get("address2") or "",
        event_location.get("city") or "",
        event_location.get("state") or "",
    ]
    return ", ".join(p for p in parts if p).strip(", ")


def scrape() -> list[dict]:
    """Fetch and parse Washtenaw County public meeting events from the CivicClerk API."""
    session = RateLimitedSession()

    try:
        response = session.get(
            "https://washtenawcomi.api.civicclerk.com/v1/Events",
            params=_build_api_params(),
        )
        data = json.loads(response.text)
    except Exception as exc:
        logger.error("Failed to fetch Washtenaw County calendar: %s", exc)
        return []

    raw_events = data.get("value", [])
    if not isinstance(raw_events, list):
        logger.error("Unexpected response format from CivicClerk API")
        return []

    events = []
    for item in raw_events:
        try:
            title = (item.get("eventName") or "").strip()
            if not title:
                continue

            # Skip cancelled events
            if item.get("isDeleted"):
                continue
            if title.upper().startswith("CANCELLED"):
                continue

            start_dt_str = item.get("startDateTime") or item.get("eventDate") or ""
            if not start_dt_str:
                continue
            date_parsed = parse_date(start_dt_str)
            if not date_parsed:
                continue
            date_str = date_parsed.isoformat()
            if not is_in_window(date_str):
                continue

            # Extract time
            # CivicClerk appends Z but times are actually local Eastern — strip it
            time_str = ""
            raw_dt = start_dt_str
            if raw_dt:
                raw_dt_local = raw_dt.rstrip("Z")
                if "T" in raw_dt_local:
                    time_part = raw_dt_local.split("T", 1)[1]
                    if time_part and time_part != "00:00:00":
                        try:
                            dt = datetime.fromisoformat(raw_dt_local)
                            time_str = dt.strftime("%I:%M %p").lstrip("0")
                        except (ValueError, TypeError):
                            pass

            event_id = item.get("id")
            if event_id:
                url = f"{PORTAL_BASE}/{event_id}"
            else:
                url = FALLBACK_URL

            venue = _parse_venue(item.get("eventLocation"))

            tags = ["public_meeting"] if MEETING_KEYWORDS.search(title) else []

            events.append(make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=tags,
            ))
        except Exception as exc:
            logger.warning("washtenaw_county: skipping event %r: %s", item.get("eventName"), exc)

    logger.info("washtenaw_county: %d events in window", len(events))
    return events
