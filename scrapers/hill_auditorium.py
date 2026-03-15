"""Scraper for Hill Auditorium via University Musical Society (ums.org)."""
import logging
import re

from bs4 import BeautifulSoup

from scrapers.base import RateLimitedSession, is_in_window, make_event, parse_date

logger = logging.getLogger(__name__)

SOURCE = "hill_auditorium"
CATEGORY = "arts_culture"
VENUE = "Hill Auditorium"
PERFORMANCES_URL = "https://www.ums.org/performances/"


def scrape() -> list[dict]:
    """Fetch the UMS performances page and return events in the 30-day window."""
    session = RateLimitedSession()
    response = session.get(PERFORMANCES_URL)

    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    for block in soup.select("div.event_block"):
        # --- URL ---
        img_link = block.select_one("div.left_image a")
        if not img_link:
            continue
        url = img_link.get("href", "").strip()
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://ums.org" + url

        # --- Title ---
        right = block.select_one("div.right_content_block")
        if not right:
            continue
        h3 = right.select_one("h3")
        if not h3:
            continue
        title = h3.get_text(separator=" ", strip=True)
        if not title:
            continue

        # --- Date text ---
        # The date appears as a NavigableString immediately after the <a> wrapping the h3
        a_tag = right.find("a", href=True)
        date_text = ""
        if a_tag:
            for sibling in a_tag.next_siblings:
                text = str(sibling).strip()
                if text and not text.startswith("<"):
                    date_text = text
                    break

        if not date_text:
            logger.debug("hill_auditorium: no date text found for %r, skipping", title)
            continue

        # Extract month+day from strings like:
        #   "Friday, March 20"
        #   "Thursday, April 9 - Thursday, April 9"
        #   "Tuesday, April 14, 7:30-9:30pm"
        month_day = re.search(
            r"(January|February|March|April|May|June|July|August|"
            r"September|October|November|December)\s+\d+",
            date_text,
        )
        if not month_day:
            logger.debug("hill_auditorium: could not extract date from %r, skipping", date_text)
            continue

        # Append the current year so parse_date can handle it
        date_with_year = month_day.group(0) + ", 2026"
        date_parsed = parse_date(date_with_year)
        if not date_parsed:
            logger.debug("hill_auditorium: parse_date failed for %r, skipping", date_with_year)
            continue

        date_str = date_parsed.isoformat()
        if not is_in_window(date_str):
            continue

        # --- Time (optional) ---
        time_match = re.search(r"\d{1,2}:\d{2}(?:am|pm)?", date_text, re.IGNORECASE)
        time_str = time_match.group(0) if time_match else ""

        try:
            event = make_event(
                title=title,
                date=date_str,
                time=time_str,
                venue=VENUE,
                url=url,
                source=SOURCE,
                category=CATEGORY,
            )
        except ValueError as exc:
            logger.warning("hill_auditorium: skipping event %r: %s", title, exc)
            continue

        events.append(event)

    return events
