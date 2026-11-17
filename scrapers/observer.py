"""Scraper for the Ann Arbor Observer's public events API."""
import logging
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from scrapers.base import RateLimitedSession, local_today, make_event

SOURCE = "observer"
CATEGORY = "community"
logger = logging.getLogger(__name__)
API_URL = "https://annarborobserver.com/wp-json/tribe/events/v1/events"


def _event(item: dict) -> dict:
    """Convert one published occurrence, retaining its local start and venue."""
    if not isinstance(item, dict):
        raise ValueError("observer: invalid event record")
    try:
        title = BeautifulSoup(item["title"], "lxml").get_text(" ", strip=True)
        url = item["url"]
        start = datetime.strptime(item["start_date"], "%Y-%m-%d %H:%M:%S")
        if not title or not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError("missing event title or URL")
        venue = item.get("venue") or {}
        if not isinstance(venue, dict):
            raise ValueError("invalid venue")
        categories = item.get("categories", [])
        if not isinstance(categories, list):
            raise ValueError("invalid categories")
        tags = [category["slug"].replace("-", "_") for category in categories
                if isinstance(category, dict) and isinstance(category.get("slug"), str)]
        description = BeautifulSoup(item.get("description") or "", "lxml").get_text(" ", strip=True)
        address = ", ".join(part for part in (venue.get("address", ""), venue.get("city", ""))
                            if part)
        return make_event(
            title=title, date=start.date().isoformat(),
            time="" if item.get("all_day") else start.strftime("%I:%M %p").lstrip("0"),
            venue=venue.get("venue", ""), address=address, url=url, source=SOURCE,
            category=CATEGORY, tags=tags, description=description,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"observer: invalid event record: {exc}") from exc


def scrape() -> list[dict]:
    """Read every API page for the inclusive 30-day window.

    The publisher's robots.txt specifies a 600-second crawl delay. Its API caps
    pages at 50, so a complete crawl can take hours.
    """
    session = RateLimitedSession()
    session._delay = 600
    # The shared session retries immediately on some HTTP errors; those retries
    # would bypass the publisher's crawl delay.
    session._session.mount("https://", HTTPAdapter(max_retries=0))
    today = local_today()
    end = today + timedelta(days=30)
    page = 1
    expected_total = expected_pages = None
    records_seen = 0
    seen_ids = set()
    events = []
    while True:
        response = session.get(API_URL, params={
            "start_date": today.isoformat(), "end_date": end.isoformat(),
            "per_page": 50, "page": page,
        })
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("observer: invalid API response")
        items = payload.get("events")
        total, pages = payload.get("total"), payload.get("total_pages")
        if (not isinstance(items, list) or type(total) is not int or total < 0
                or type(pages) is not int or pages < 0
                or (total > 0 and pages < 1)
                or (total == 0 and (items or pages > 1))):
            raise ValueError("observer: invalid pagination metadata")
        if expected_total is None:
            expected_total, expected_pages = total, pages
            if pages > 36:
                logger.warning("observer: %s pages require over six hours at the publisher's crawl delay", pages)
        elif (total, pages) != (expected_total, expected_pages):
            raise ValueError("observer: pagination changed during crawl")
        if total and not items:
            raise ValueError("observer: unexpectedly empty page")
        records_seen += len(items)
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                raise ValueError("observer: event missing ID")
            if item["id"] in seen_ids:
                raise ValueError("observer: duplicate event across API pages")
            seen_ids.add(item["id"])
            event = _event(item)
            event_date = date.fromisoformat(event["date"])
            if today <= event_date <= end and not item.get("hide_from_listings", False):
                events.append(event)
        if page >= pages:
            if records_seen != total:
                raise ValueError("observer: incomplete API pagination")
            return events
        page += 1
