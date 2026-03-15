"""Scraper for Ann Arbor Observer events calendar (annarborobserver.com)."""
import logging
import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from scrapers.base import RateLimitedSession, is_in_window, make_event, parse_date

logger = logging.getLogger(__name__)

SOURCE = "observer"
CATEGORY = "community"
BASE_URL = "https://annarborobserver.com"
CALENDAR_URL = "https://annarborobserver.com/calendar/"


def _week_url(week_start: date) -> str:
    """Build the calendar week-view URL for the week containing week_start."""
    return (
        f"{CALENDAR_URL}?time=week"
        f"&month={week_start.month:02d}"
        f"&yr={week_start.year}"
        f"&dy={week_start.day}"
    )


def _parse_events_from_html(html: str) -> list[dict]:
    """Parse .mc-event articles from a calendar week-view HTML page."""
    soup = BeautifulSoup(html, "lxml")
    events = []

    for article in soup.select(".mc-event"):
        # Title and URL come from the h5 > a element
        title_link = article.select_one("h5 a")
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        if not title:
            continue

        url = title_link.get("href", "").strip()
        if not url:
            continue
        if not url.startswith("http"):
            url = BASE_URL + url

        # Date comes from the Google Calendar link's dates= parameter
        gcal_link = article.select_one("a.gcal")
        date_str = ""
        if gcal_link:
            href = gcal_link.get("href", "")
            m = re.search(r"dates=(\d{8})", href)
            if m:
                raw = m.group(1)
                date_str = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

        if not date_str:
            continue

        if not is_in_window(date_str):
            continue

        # Time comes from the .event-time span
        time_el = article.select_one(".event-time")
        time_str = ""
        if time_el:
            # Remove any nested span text (e.g. " - end time") and clean up
            time_str = time_el.get_text(strip=True)

        # Category name for tags — from .mc-category span text
        category_el = article.select_one(".mc-category span:not(svg):last-child")
        category_text = category_el.get_text(strip=True) if category_el else ""
        tags = [category_text.lower().replace(" ", "_")] if category_text else []

        try:
            event = make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue="",
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=tags,
            )
        except ValueError as exc:
            logger.warning("observer: skipping %r: %s", title, exc)
            continue

        events.append(event)

    return events


def scrape() -> list[dict]:
    """Fetch Ann Arbor Observer calendar events for the next 30 days."""
    session = RateLimitedSession()
    today = date.today()
    window_end = today + timedelta(days=30)

    # Collect events from weekly pages covering today through window_end.
    # The calendar week view shows Sun-Sat; step by 7 days.
    all_events: list[dict] = []
    seen_ids: set[str] = set()

    # Determine the first Sunday on or before today
    week_start = today - timedelta(days=today.weekday() + 1)  # Monday=0, so Sunday=6
    if today.weekday() == 6:
        week_start = today  # today is already Sunday

    # Iterate through weeks until we've covered the full window
    current = week_start
    while current <= window_end:
        if current == week_start:
            # First week: use the default URL (no dy/month/yr needed, reduces one param)
            url = f"{CALENDAR_URL}?time=week"
        else:
            url = _week_url(current)

        logger.debug("observer: fetching %s", url)
        try:
            response = session.get(url)
            week_events = _parse_events_from_html(response.text)
        except Exception as exc:
            logger.error("observer: failed to fetch %s: %s", url, exc)
            week_events = []

        for ev in week_events:
            if ev["id"] not in seen_ids:
                seen_ids.add(ev["id"])
                all_events.append(ev)

        current += timedelta(weeks=1)

    return all_events
