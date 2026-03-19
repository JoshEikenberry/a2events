import json
import sys
from calendar import month_name
from datetime import date, datetime, timezone
from email.utils import formatdate
from pathlib import Path

from lxml import etree

SITE_URL = "https://CHANGEME.github.io/a2events/"
EVENTS_PATH = Path("docs/events.json")
OUTPUT_DIR = Path("docs")
WINDOW_DAYS = 30

FEEDS = {
    "feed.xml": {"title": "A2 Events — All", "category": None},
    "feed-arts-culture.xml": {"title": "A2 Events — Arts & Culture", "category": "arts_culture"},
    "feed-community.xml": {"title": "A2 Events — Community", "category": "community"},
}


def format_rfc822(date_str: str) -> str:
    """Convert YYYY-MM-DD to RFC 822 date string at midnight UTC."""
    d = date.fromisoformat(date_str)
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return formatdate(dt.timestamp(), usegmt=True)


def format_date_long(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'March 15, 2026'."""
    d = date.fromisoformat(date_str)
    return f"{month_name[d.month]} {d.day}, {d.year}"


def build_item_title(event: dict) -> str:
    """Build RSS item title: 'Title @ Venue' or just 'Title' if no venue."""
    title = event.get("title", "")
    venue = (event.get("venue") or "").strip()
    return f"{title} @ {venue}" if venue else title
