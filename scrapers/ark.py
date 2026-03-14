"""Scraper for The Ark (theark.org)."""
import logging
from scrapers.base import RateLimitedSession, parse_ical_feed

logger = logging.getLogger(__name__)

SOURCE = "ark"
CATEGORY = "arts_culture"
ICAL_URL = "https://theark.org/events/list/?ical=1"


def scrape() -> list[dict]:
    """Fetch and parse The Ark's iCal event feed."""
    session = RateLimitedSession()
    response = session.get(ICAL_URL)
    events = parse_ical_feed(response.content, SOURCE, CATEGORY)
    # Tag all events as music
    for event in events:
        if "music" not in event["tags"]:
            event["tags"].append("music")
    return events
