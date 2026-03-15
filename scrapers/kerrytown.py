"""Scraper for Kerrytown Concert House (kerrytownconcerthouse.com)."""
import logging
from scrapers.base import RateLimitedSession, parse_ical_feed

logger = logging.getLogger(__name__)

SOURCE = "kerrytown"
CATEGORY = "arts_culture"
ICAL_URL = "https://www.kerrytownconcerthouse.com/?ical=1"


def scrape() -> list[dict]:
    """Fetch and parse Kerrytown Concert House's iCal event feed."""
    session = RateLimitedSession()
    response = session.get(ICAL_URL)
    events = parse_ical_feed(response.content, SOURCE, CATEGORY)
    # Override venue name for all events (iCal LOCATION may be empty)
    for event in events:
        if not event.get("venue"):
            event["venue"] = "Kerrytown Concert House"
    return events
