"""Public Sun Times News community calendar, including paginated listings.

The list view hides subsequent recurrences by default; only explicitly listed
starts are emitted, not inferred dates within multi-day events. The calendar
also occasionally includes events outside Washtenaw County.
"""
import logging
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.base import RateLimitedSession, WINDOW_DAYS, local_today, make_event

logger = logging.getLogger(__name__)
SOURCE = "sun_times_news"
CALENDAR_URL = "https://thesuntimesnews.com/events/list/"


def _text(node, selector):
    element = node.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


def scrape() -> list[dict]:
    session = RateLimitedSession()
    today = local_today()
    end = today + timedelta(days=WINDOW_DAYS)
    url = CALENDAR_URL
    visited = set()
    events = []
    seen = set()

    while url:
        if url in visited:
            raise ValueError("Sun Times News calendar pagination loop")
        visited.add(url)
        soup = BeautifulSoup(session.get(url).text, "html.parser")
        view = soup.select_one(".tribe-events-view--list")
        if view is None:
            raise ValueError("Sun Times News calendar list not found")
        rows = view.select(".tribe-events-calendar-list__event-row")
        page_dates = []
        for row in rows:
            tag = row.select_one(".tribe-events-calendar-list__event-date-tag-datetime[datetime]")
            if tag:
                try:
                    page_dates.append(date.fromisoformat(tag["datetime"]))
                except ValueError:
                    pass
            item = row.select_one("article.tribe-events-calendar-list__event")
            if item is None:
                continue
            link = item.select_one("a.tribe-events-calendar-list__event-title-link[href]")
            when = item.select_one("time.tribe-events-calendar-list__event-datetime[datetime]")
            if not link or not when:
                continue
            title = link.get_text(" ", strip=True)
            try:
                event_date = date.fromisoformat(when["datetime"][:10])
            except ValueError:
                continue
            if not title or not today <= event_date <= end:
                continue
            event_url = urljoin(CALENDAR_URL, link["href"])
            key = (event_url, event_date)
            if key in seen:
                continue
            seen.add(key)
            start = _text(when, ".tribe-event-date-start")
            time_text = start.split("@", 1)[1].strip() if "@" in start else ""
            if time_text:
                try:
                    time_text = datetime.strptime(time_text, "%I:%M %p").strftime("%H:%M")
                except ValueError:
                    pass
            description = item.select_one(".tribe-events-calendar-list__event-description")
            if description:
                for more in description.select("a.read-more"):
                    more.decompose()
            events.append(make_event(
                title=title, date=event_date.isoformat(), time=time_text,
                venue=_text(item, ".tribe-events-calendar-list__event-venue-title"),
                address=_text(item, ".tribe-events-calendar-list__event-venue-address"),
                url=event_url, source=SOURCE, category="community",
                description=description.get_text(" ", strip=True) if description else "",
            ))
        if rows and len(page_dates) == len(rows) and min(page_dates) > end:
            break
        next_link = view.select_one("a.tribe-events-c-nav__next[href]")
        if not next_link:
            break
        next_url = urljoin(url, next_link["href"])
        parts = urlsplit(next_url)
        if parts.scheme != "https" or parts.netloc != "thesuntimesnews.com" or not parts.path.startswith("/events/list/"):
            raise ValueError("Sun Times News calendar has an unexpected next page")
        url = next_url
    logger.info("%s: %d events in window", SOURCE, len(events))
    return events
