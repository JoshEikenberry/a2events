"""Scraper for Ann Arbor District Library (AADL) events calendar."""
import logging
import re

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from scrapers.base import make_event, is_in_window, parse_date, RateLimitedSession

logger = logging.getLogger(__name__)

SOURCE = "aadl"
CATEGORY = "community"
BASE_URL = "https://www.aadl.org"
FEED_URL = "https://www.aadl.org/events-feed/upcoming"
FALLBACK_URL = "https://www.aadl.org/events"


def _normalize_tag(label: str) -> str:
    """Normalize event type label to a tag string.

    Examples:
        "Preschool Storytimes"        -> "preschool_storytimes"
        "Lectures & Panel Discussions" -> "lectures_panel_discussions"
    """
    return re.sub(r"[&\s_]+", "_", label.lower().strip()).strip("_")


def _parse_page(html: str) -> tuple[list[dict], int, int]:
    """Parse events from one page of feed HTML.

    Returns (in_window_events, total_rows_on_page, dates_parsed).
    total_rows == 0 means no more pages exist.
    dates_parsed > 0 with len(in_window_events) == 0 means all dates were past the window.
    """
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(".views-row.search-result")
    total = len(rows)
    events = []
    dates_parsed = 0

    for row in rows:
        # --- Title and URL ---
        title_link = row.select_one("h2.no-margin a")
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        if not title:
            continue

        href = (title_link.get("href") or "").strip()
        url = (BASE_URL + href) if href else FALLBACK_URL

        # --- Date, time, venue from .node-body p ---
        body_p = row.select_one(".node-body p")
        if not body_p:
            logger.warning("aadl: no body paragraph for %r, skipping", title)
            continue

        # Split on <br>: text before = date/time, text after = venue
        br = body_p.find("br")
        if br:
            # previous_siblings yields reverse-DOM order; reverse to restore reading order
            before = [
                s.get_text() if hasattr(s, "get_text") else str(s)
                for s in reversed(list(br.previous_siblings))
            ]
            after = [
                s.get_text() if hasattr(s, "get_text") else str(s)
                for s in br.next_siblings
            ]
            date_time_text = " ".join("".join(before).split())
            venue = " ".join("".join(after).split())
        else:
            date_time_text = " ".join(body_p.get_text().split())
            venue = ""

        # --- Parse date ---
        if ": " in date_time_text:
            date_part, time_part = date_time_text.split(": ", 1)
        else:
            date_part = date_time_text
            time_part = ""

        parsed_date = parse_date(date_part)
        if not parsed_date:
            logger.warning("aadl: unparseable date %r for %r, skipping", date_part, title)
            continue

        dates_parsed += 1
        date_str = parsed_date.isoformat()
        if not is_in_window(date_str):
            continue

        # --- Parse time (start time only, e.g. "10:30am to 11:00am" -> "10:30 AM") ---
        time_str = ""
        if time_part:
            start_time = time_part.split(" to ")[0].strip()
            if start_time:
                try:
                    dt = dateutil_parser.parse(start_time)
                    time_str = dt.strftime("%I:%M %p").lstrip("0")
                except (ValueError, OverflowError):
                    pass

        # --- Event type tag ---
        type_el = row.select_one(".mat-type-icon p")
        tags = []
        if type_el:
            label = type_el.get_text(strip=True)
            if label:
                tags = [_normalize_tag(label)]

        try:
            events.append(make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=tags,
            ))
        except ValueError as exc:
            logger.warning("aadl: skipping %r: %s", title, exc)

    return events, total, dates_parsed


def scrape() -> list[dict]:
    """Fetch and parse AADL upcoming events within the 30-day window."""
    session = RateLimitedSession()
    all_events: list[dict] = []
    page = 0

    while True:
        url = f"{FEED_URL}?page={page}"
        try:
            response = session.get(url)
        except Exception as exc:
            logger.error("aadl: failed to fetch page %d: %s", page, exc)
            break

        events, total_rows, dates_parsed = _parse_page(response.text)
        all_events.extend(events)

        # No more pages
        if total_rows == 0:
            break

        # Stop early only when we've confirmed we've passed the 30-day horizon
        # (dates_parsed > 0 means it's a date issue, not a parse/HTML error)
        if len(events) == 0 and dates_parsed > 0:
            break

        page += 1

    logger.info("aadl: %d events in window", len(all_events))
    return all_events
