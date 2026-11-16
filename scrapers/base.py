# scrapers/base.py
import re
import time
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import json
from typing import Optional

from dateutil import parser as dateutil_parser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
LOCAL_TIMEZONE = ZoneInfo("America/Detroit")


def local_today() -> date:
    """Return today's date in the event calendar's local timezone."""
    return datetime.now(LOCAL_TIMEZONE).date()


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

    identity = json.dumps([title, time, venue, url], ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    event_id = f"{source}-{date}-{slugify(title)}-{digest}"

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
    today = local_today()
    return today <= parsed <= today + timedelta(days=window_days)


def parse_ical_feed(ical_bytes: bytes, source: str, category: str) -> list[dict]:
    """Expand explicit calendar occurrences whose local start is in the window."""
    from dateutil.rrule import rruleset, rrulestr
    from icalendar import Calendar

    def as_datetime(value):
        return value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time())

    def occurrence_key(value):
        if isinstance(value, datetime) and value.tzinfo:
            return value.astimezone(timezone.utc)
        return value

    def properties(component, name):
        value = component.get(name, [])
        return value if isinstance(value, list) else [value]

    components = [c for c in Calendar.from_ical(ical_bytes).walk() if c.name == "VEVENT"]
    overrides = {}
    for component in components:
        if component.get("UID") and component.get("RECURRENCE-ID"):
            key = (str(component["UID"]), occurrence_key(component["RECURRENCE-ID"].dt))
            overrides[key] = component

    events = []

    def emit(component, start, master=None):
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            return
        if isinstance(start, datetime) and start.tzinfo:
            start = start.astimezone(LOCAL_TIMEZONE)
        day = start.date() if isinstance(start, datetime) else start
        if not is_in_window(day.isoformat()):
            return
        def field(name):
            return str(component.get(name, master.get(name, "") if master else "")).strip()
        title, url = field("SUMMARY"), field("URL")
        if not title or not url:
            return
        events.append(make_event(
            title=title, date=day.isoformat(),
            time=start.strftime("%I:%M %p").lstrip("0") if isinstance(start, datetime) else "",
            venue=field("LOCATION"), url=url, source=source, category=category,
            description=field("DESCRIPTION"),
        ))

    for component in components:
        if component.get("RECURRENCE-ID") or not component.get("DTSTART"):
            continue
        if str(component.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = component["DTSTART"].dt
        uid = str(component.get("UID", ""))
        recurring = component.get("RRULE") or component.get("RDATE")
        if not recurring:
            if (uid, occurrence_key(start)) not in overrides:
                emit(component, start)
            continue
        all_day = not isinstance(start, datetime)
        dtstart = as_datetime(start)
        rules = rruleset()
        rules.rdate(dtstart)
        for rule in properties(component, "RRULE"):
            rules.rrule(rrulestr(rule.to_ical().decode(), dtstart=dtstart))
        for name, add in (("RDATE", rules.rdate), ("EXDATE", rules.exdate)):
            for prop in properties(component, name):
                for entry in prop.dts:
                    value = entry.dt
                    if isinstance(value, tuple):
                        value = value[0]
                    add(as_datetime(value))
        today = local_today()
        # Offset-aware events may cross local midnight; filter precisely in emit.
        lower = datetime.combine(today - timedelta(days=2), datetime.min.time(), tzinfo=dtstart.tzinfo)
        upper = datetime.combine(today + timedelta(days=WINDOW_DAYS + 3), datetime.min.time(), tzinfo=dtstart.tzinfo)
        for occurrence in rules.between(lower, upper, inc=True):
            value = occurrence.date() if all_day else occurrence
            if (uid, occurrence_key(value)) not in overrides:
                emit(component, value)

    masters = {str(c["UID"]): c for c in components if c.get("UID") and not c.get("RECURRENCE-ID")}
    for (uid, _), component in overrides.items():
        master = masters.get(uid)
        if (component.get("DTSTART")
                and (master is None or str(master.get("STATUS", "")).upper() != "CANCELLED")):
            emit(component, component["DTSTART"].dt, master)
    return events
