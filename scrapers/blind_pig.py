"""Scraper for The Blind Pig (blindpigmusic.com)."""
import logging
from datetime import date

from bs4 import BeautifulSoup

from scrapers.base import RateLimitedSession, is_in_window, make_event, parse_date

logger = logging.getLogger(__name__)

SOURCE = "blind_pig"
CATEGORY = "arts_culture"
VENUE = "The Blind Pig"
ADDRESS = "208 S. 1st St, Ann Arbor, MI"
EVENTS_URL = "https://www.blindpigmusic.com/calendar/"


def _parse_event_date(raw: str) -> str:
    """Parse date string like 'Mar 16' into ISO format, assuming current or next year."""
    if not raw:
        return ""
    today = date.today()
    # Try appending the current year first
    for year in (today.year, today.year + 1):
        parsed = parse_date(f"{raw} {year}")
        if parsed:
            return parsed.isoformat()
    return ""


def scrape() -> list[dict]:
    """Fetch and parse The Blind Pig's calendar page."""
    session = RateLimitedSession()
    response = session.get(EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    events = []
    for section in soup.select(".tw-section"):
        # Extract title and URL from the event name link
        name_link = section.select_one(".tw-name a")
        if not name_link:
            continue
        title = name_link.get_text(strip=True)
        url = name_link.get("href", "").strip()
        if not url or not title:
            continue

        # Extract date
        date_el = section.select_one(".tw-event-date")
        if not date_el:
            continue
        raw_date = date_el.get_text(strip=True)
        date_str = _parse_event_date(raw_date)
        if not date_str:
            logger.debug("blind_pig: could not parse date %r for %r", raw_date, title)
            continue

        if not is_in_window(date_str):
            continue

        # Extract door time
        time_el = section.select_one(".tw-event-door-time")
        time_str = time_el.get_text(strip=True) if time_el else ""

        # Extract description from event-description div
        desc_el = section.select_one(".event-description")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Extract image
        img_el = section.select_one(".tw-image img")
        image_url = img_el.get("src") if img_el else None

        try:
            event = make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=VENUE,
                address=ADDRESS,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=["music"],
                description=description,
                image_url=image_url,
            )
        except ValueError as exc:
            logger.warning("blind_pig: skipping event %r: %s", title, exc)
            continue

        events.append(event)

    return events
