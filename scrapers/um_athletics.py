"""Scraper for University of Michigan Athletics schedules (mgoblue.com)."""
import logging
from datetime import datetime, timezone

from icalendar import Calendar

from scrapers.base import RateLimitedSession, make_event, is_in_window

logger = logging.getLogger(__name__)

SOURCE = "um_athletics"
CATEGORY = "um_athletics"

# Map sport tag → (iCal URL, fallback schedule page URL)
# sportId values are global_sport_id from the Sidearm Sports platform embedded JS state.
# scheduleId values are the season-specific scheduleId values from the same state.
# The old /calendar.ashx/calendar.ics endpoint was replaced by /api/v2/Calendar/subscribe
# (Sidearm Sports platform migration, March 2026).
# Verified via mgoblue.com schedule pages (March 2026).
_CAL = "https://mgoblue.com/api/v2/Calendar/subscribe?type=ics"
SPORTS: dict[str, tuple[str, str]] = {
    "football": (
        f"{_CAL}&sportId=5&scheduleId=1894",
        "https://mgoblue.com/sports/football/schedule",
    ),
    "mens-basketball": (
        f"{_CAL}&sportId=7&scheduleId=1872",
        "https://mgoblue.com/sports/mens-basketball/schedule",
    ),
    "womens-basketball": (
        f"{_CAL}&sportId=267&scheduleId=1881",
        "https://mgoblue.com/sports/womens-basketball/schedule",
    ),
    "mens-hockey": (
        f"{_CAL}&sportId=13&scheduleId=1866",
        "https://mgoblue.com/sports/mens-ice-hockey/schedule",
    ),
    "womens-hockey": (
        f"{_CAL}&sportId=476&scheduleId=1882",
        "https://mgoblue.com/sports/womens-ice-hockey/schedule",
    ),
    "baseball": (
        f"{_CAL}&sportId=1&scheduleId=1880",
        "https://mgoblue.com/sports/baseball/schedule",
    ),
    "softball": (
        f"{_CAL}&sportId=17&scheduleId=1885",
        "https://mgoblue.com/sports/softball/schedule",
    ),
    "mens-soccer": (
        f"{_CAL}&sportId=253&scheduleId=281",
        "https://mgoblue.com/sports/mens-soccer/schedule",
    ),
    "womens-soccer": (
        f"{_CAL}&sportId=224&scheduleId=395",
        "https://mgoblue.com/sports/womens-soccer/schedule",
    ),
    "volleyball": (
        f"{_CAL}&sportId=436&scheduleId=443",
        "https://mgoblue.com/sports/volleyball/schedule",
    ),
}


def _parse_sport_ical(ical_bytes: bytes, sport_tag: str, fallback_url: str) -> list[dict]:
    """Parse iCal bytes for one sport, supplying fallback URL for URL-less events."""
    cal = Calendar.from_ical(ical_bytes)
    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        dtstart = component.get("DTSTART")
        if not dtstart:
            continue
        event_date = dtstart.dt
        if hasattr(event_date, "date"):
            event_date = event_date.date()
        date_str = event_date.isoformat()
        if not is_in_window(date_str):
            continue

        title = str(component.get("SUMMARY", "")).strip()
        if not title:
            continue

        # Use URL field if present; fall back to sport schedule page
        url = str(component.get("URL", "")).strip() or fallback_url

        time_str = ""
        if isinstance(dtstart.dt, datetime):
            local_dt = dtstart.dt.astimezone()
            time_str = local_dt.strftime("%I:%M %p").lstrip("0")

        venue = str(component.get("LOCATION", "")).strip()
        description = str(component.get("DESCRIPTION", "")).strip()

        try:
            events.append(make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                description=description,
                tags=[sport_tag],
            ))
        except Exception as exc:
            logger.warning("Skipping %s event %r: %s", sport_tag, title, exc)
    return events


def scrape() -> list[dict]:
    """Fetch iCal feeds for all tracked U-M varsity sports."""
    session = RateLimitedSession()
    all_events = []

    for sport_tag, (ical_url, fallback_url) in SPORTS.items():
        try:
            resp = session.get(ical_url)
            sport_events = _parse_sport_ical(resp.content, sport_tag, fallback_url)
            all_events.extend(sport_events)
            logger.info("um_athletics %s: %d events", sport_tag, len(sport_events))
        except Exception as exc:
            logger.warning("Failed to fetch um_athletics feed for %s: %s", sport_tag, exc)

    return all_events
