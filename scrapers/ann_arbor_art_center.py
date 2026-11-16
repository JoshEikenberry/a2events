"""Scrape public events from Ann Arbor Art Center's events API."""
import re
from datetime import datetime, timedelta
from html import unescape

from bs4 import BeautifulSoup

from scrapers.base import RateLimitedSession, WINDOW_DAYS, local_today, make_event

SOURCE = "ann_arbor_art_center"
CATEGORY = "arts_culture"
API_URL = "https://www.annarborartcenter.org/wp-json/tribe/events/v1/events"


def _is_announcement_or_members_only(item: dict) -> bool:
    if any(
        category.get("name", "").strip().casefold() == "education term launches"
        for category in item.get("categories", [])
    ):
        return True
    return bool(re.search(
        r"\b(?:members?[- ]only|for members only|registration (?:opens|opening))\b",
        unescape(item.get("title", "")), re.IGNORECASE,
    ))


def scrape() -> list[dict]:
    """Fetch all pages of public events starting in the local 30-day window."""
    today = local_today()
    end = today + timedelta(days=WINDOW_DAYS)
    session = RateLimitedSession()
    events = []
    page = 1
    while True:
        data = session.get(API_URL, params={
            "start_date": today.isoformat(), "end_date": end.isoformat(),
            "per_page": 100, "page": page,
        }).json()
        for item in data["events"]:
            if (item.get("status") != "publish" or item.get("hide_from_listings")
                    or _is_announcement_or_members_only(item)):
                continue
            start = datetime.fromisoformat(item["start_date"])
            if not today <= start.date() <= end:
                continue
            title = unescape(item.get("title", "")).strip()
            url = item.get("url", "").strip()
            if not title or not url:
                continue
            venue = item.get("venue") or {}
            location = ", ".join(filter(None, (
                venue.get("venue"), venue.get("address"), venue.get("city"), venue.get("state")
            )))
            events.append(make_event(
                title=title, date=start.date().isoformat(),
                time="" if item.get("all_day") else start.strftime("%I:%M %p").lstrip("0"),
                venue=location, url=url, source=SOURCE, category=CATEGORY,
                description=BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True),
            ))
        if page >= data["total_pages"]:
            break
        page += 1
    return events
