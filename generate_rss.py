import json
import sys
from calendar import month_name
from datetime import date, datetime, timedelta, timezone
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


def load_events(path: Path) -> list[dict]:
    """Load events list from events.json. Exits non-zero on any failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["events"]
    except FileNotFoundError:
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: {path} contains invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError:
        print(f"ERROR: {path} has no 'events' key", file=sys.stderr)
        sys.exit(1)


def filter_events(
    events: list[dict],
    category: str | None = None,
    window_days: int = WINDOW_DAYS,
) -> list[dict]:
    """Return events within the rolling window, optionally filtered by category."""
    today = date.today()
    cutoff = today + timedelta(days=window_days)
    result = []
    for event in events:
        try:
            event_date = date.fromisoformat(event["date"])
        except (ValueError, KeyError):
            continue
        if not (today <= event_date <= cutoff):
            continue
        if category is not None and event.get("category") != category:
            continue
        result.append(event)
    return result


def build_feed(events: list[dict], title: str, site_url: str) -> etree._Element:
    """Build an lxml RSS 2.0 Element from a list of events."""
    rss = etree.Element("rss", version="2.0")
    channel = etree.SubElement(rss, "channel")

    etree.SubElement(channel, "title").text = title
    etree.SubElement(channel, "link").text = site_url
    etree.SubElement(channel, "description").text = (
        "Upcoming events in Ann Arbor, Ypsilanti, and Washtenaw County"
    )
    etree.SubElement(channel, "lastBuildDate").text = formatdate(
        datetime.now(timezone.utc).timestamp(), usegmt=True
    )
    etree.SubElement(channel, "ttl").text = "1440"

    sorted_events = sorted(events, key=lambda e: e.get("date", ""))
    for event in sorted_events:
        item = etree.SubElement(channel, "item")
        etree.SubElement(item, "title").text = build_item_title(event)
        etree.SubElement(item, "link").text = event.get("url", "")
        etree.SubElement(item, "description").text = etree.CDATA(
            build_item_description(event)
        )
        etree.SubElement(item, "pubDate").text = format_rfc822(event["date"])
        guid = etree.SubElement(item, "guid")
        guid.set("isPermaLink", "false")
        guid.text = event.get("id", "")
        etree.SubElement(item, "category").text = event.get("category", "")

    return rss


def write_feed(root: etree._Element, path: Path) -> None:
    """Write RSS feed XML to file with declaration and pretty-printing."""
    tree = etree.ElementTree(root)
    tree.write(str(path), xml_declaration=True, encoding="utf-8", pretty_print=True)


def main() -> None:
    events = load_events(EVENTS_PATH)
    for filename, config in FEEDS.items():
        filtered = filter_events(events, category=config["category"])
        feed = build_feed(filtered, title=config["title"], site_url=SITE_URL)
        write_feed(feed, OUTPUT_DIR / filename)
        print(f"Wrote {len(filtered)} events to {filename}")


if __name__ == "__main__":
    main()
