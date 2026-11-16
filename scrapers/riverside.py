"""Public Riverside Arts Center events from The Events Calendar API.

The site's robots.txt disallows its iCalendar export, so use the permitted
REST endpoint instead. The API supplies individual dated occurrences.
"""
from datetime import datetime, timedelta
from html import unescape

from bs4 import BeautifulSoup

from scrapers.base import RateLimitedSession, WINDOW_DAYS, is_in_window, local_today, make_event

SOURCE = "riverside"
CATEGORY = "arts_culture"
API_URL = "https://www.riversidearts.org/wp-json/tribe/events/v1/events"


def scrape() -> list[dict]:
    """Fetch each API page in the upcoming event window."""
    session = RateLimitedSession()
    today = local_today()
    params = {
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=WINDOW_DAYS)).isoformat(),
        "per_page": 50,
    }
    events = []
    page = 1
    while True:
        data = session.get(API_URL, params={**params, "page": page}).json()
        for item in data["events"]:
            title = unescape(item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            try:
                start = datetime.fromisoformat(item.get("start_date") or "")
            except (TypeError, ValueError):
                continue
            event_date = start.date().isoformat()
            if not title or not url or not is_in_window(event_date):
                continue
            venue = item.get("venue") or {}
            image = item.get("image") or {}
            events.append(make_event(
                title=title,
                date=event_date,
                time="" if item.get("all_day") else start.strftime("%I:%M %p").lstrip("0"),
                venue=unescape(venue.get("venue") or "").strip(),
                address=", ".join(filter(None, (venue.get("address"), venue.get("city"), venue.get("state"), venue.get("zip")))),
                url=url,
                source=SOURCE,
                category=CATEGORY,
                description=BeautifulSoup(item.get("excerpt") or "", "html.parser").get_text(" ", strip=True),
                image_url=image.get("url"),
            ))
        if page >= data["total_pages"]:
            return events
        page += 1
