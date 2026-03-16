"""Scraper for City of Ypsilanti public calendar (cityofypsilanti.com)."""
import logging
import re
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)

SOURCE = "ypsilanti"
CATEGORY = "ypsilanti"
EVENTS_URL = "https://www.cityofypsilanti.com/calendar"
FALLBACK_URL = EVENTS_URL

# Plain substring match (no \b word boundaries): the live site has titles like
# "Administrative Hearings Bureau" where word boundaries fail on the trailing space in HTML.
MEETING_KEYWORDS = re.compile(
    r"council|commission|board|meeting|hearing", re.IGNORECASE
)


def scrape() -> list[dict]:
    """Fetch and parse the City of Ypsilanti public calendar."""
    session = RateLimitedSession()
    try:
        response = session.get(EVENTS_URL)
        soup = BeautifulSoup(response.text, "lxml")
    except Exception as exc:
        logger.error("Failed to fetch Ypsilanti calendar: %s", exc)
        return []

    events = []
    # Events are in <li> elements inside .calendars .calendar containers.
    # Each <li> has:
    #   - h3 > a > span  (title)
    #   - [itemprop="startDate"]  (ISO datetime text)
    #   - h3 > a[href]  (relative URL)
    #   - .eventLocation .name  (venue, optional)
    for item in soup.select(".calendars .calendar li"):
        try:
            title_el = item.select_one("h3 a span")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            date_el = item.select_one("[itemprop='startDate']")
            if not date_el:
                continue
            date_text = date_el.get_text(strip=True)
            date_parsed = parse_date(date_text)
            if not date_parsed or not is_in_window(date_parsed.isoformat()):
                continue

            link_el = item.select_one("h3 a[href]")
            href = link_el["href"] if link_el else None
            if href and href.startswith("/"):
                url = "https://www.cityofypsilanti.com" + href
            elif href and href.startswith("http"):
                url = href
            else:
                url = FALLBACK_URL

            venue_el = item.select_one(".eventLocation .name")
            venue = venue_el.get_text(strip=True) if venue_el else ""

            # Extract time from the visible date text in .subHeader .date
            time_str = ""
            date_display_el = item.select_one(".subHeader .date")
            if date_display_el:
                display_text = date_display_el.get_text(" ", strip=True)
                # Look for time pattern like "6:30 PM" or "7:00 PM - 9:00 PM"
                time_match = re.search(
                    r"\d{1,2}:\d{2}\s*[AP]M(?:\s*[-\u2009\s]+\s*\d{1,2}:\d{2}\s*[AP]M)?",
                    display_text,
                    re.IGNORECASE,
                )
                if time_match:
                    time_str = time_match.group(0).strip()

            tags = ["public_meeting"] if MEETING_KEYWORDS.search(title) else []

            events.append(make_event(
                title=title,
                date=date_parsed.isoformat(),
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
                tags=tags,
            ))
        except Exception as exc:
            logger.warning("Skipping ypsilanti event: %s", exc)

    logger.info("ypsilanti: %d events in window", len(events))
    return events
