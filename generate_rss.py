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


def build_item_description(event: dict) -> str:
    """Build HTML description block for an RSS item."""
    date_str = event.get("date", "")
    time_str = (event.get("time") or "").strip()
    venue = (event.get("venue") or "").strip()
    address = (event.get("address") or "").strip()
    description = (event.get("description") or "").strip()

    header = f"<strong>{format_date_long(date_str)}"
    if time_str:
        header += f" — {time_str}"
    header += "</strong>"

    if venue and address:
        venue_line = f"{venue} · {address}"
    elif venue:
        venue_line = venue
    elif address:
        venue_line = address
    else:
        venue_line = ""

    first_para = f"<p>{header}"
    if venue_line:
        first_para += f"<br>\n{venue_line}"
    first_para += "</p>"

    parts = [first_para]
    if description:
        parts.append(f"<p>{description}</p>")

    return "\n".join(parts)
