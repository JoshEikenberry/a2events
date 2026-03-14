# scrapers/base.py
import re
import time
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from dateutil import parser as dateutil_parser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def make_event(
    *,
    title: str,
    date: str,
    time: str,
    venue: str,
    url: Optional[str],
    source: str,
    category: str,
    tags: list = None,
    description: str = "",
    address: str = "",
    image_url: Optional[str] = None,
) -> dict:
    """Build a validated event dict conforming to the event schema."""
    if not url or not url.strip():
        raise ValueError("url is required and must not be None or empty")

    event_id = f"{source}-{date}-{slugify(title)}"

    return {
        "id": event_id,
        "title": title,
        "date": date,
        "time": time,
        "venue": venue,
        "address": address,
        "category": category,
        "tags": tags or [],
        "description": description,
        "url": url,
        "source": source,
        "also_listed_at": [],
        "image_url": image_url,
        "possible_duplicate": False,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def make_session() -> requests.Session:
    """Create an HTTP session with retry logic and rate limiting built in."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,  # exponential: 1s, 2s, 4s
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; A2EventsBot/1.0; +https://github.com/your-org/a2events)"
    })
    return session


class RateLimitedSession:
    """Wraps requests.Session with per-domain rate limiting (1-2s delay)."""

    def __init__(self):
        self._session = make_session()
        self._last_request_time: float = 0.0
        self._delay: float = 1.5  # seconds between requests

    def get(self, url: str, **kwargs) -> requests.Response:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_request_time = time.time()
        response = self._session.get(url, timeout=15, **kwargs)
        response.raise_for_status()
        return response


def parse_date(text: str) -> Optional[date]:
    """Parse a date string in any common format. Returns None on failure."""
    if not text:
        return None
    try:
        return dateutil_parser.parse(text, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


def is_in_window(date_str: str, window_days: int = WINDOW_DAYS) -> bool:
    """Return True if date_str falls within today + window_days."""
    parsed = parse_date(date_str)
    if not parsed:
        return False
    today = date.today()
    return today <= parsed <= today + timedelta(days=window_days)


def parse_ical_feed(ical_bytes: bytes, source: str, category: str) -> list[dict]:
    """Parse an iCal feed and return a list of event dicts within the window."""
    from icalendar import Calendar
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
        url = str(component.get("URL", "")).strip() or None
        if not url or not title:
            continue
        events.append(make_event(
            title=title,
            date=date_str,
            time=(
                (lambda s: s[1:] if s[0] == "0" else s)(dtstart.dt.strftime("%I:%M %p"))
                if isinstance(dtstart.dt, datetime)
                else ""
            ),
            venue=str(component.get("LOCATION", "")).strip(),
            url=url,
            source=source,
            category=category,
            description=str(component.get("DESCRIPTION", "")).strip(),
        ))
    return events
