"""Scraper for Blue Llama Jazz Club (bluellamaclub.com)."""
import logging
from scrapers.base import RateLimitedSession, parse_ical_feed

logger = logging.getLogger(__name__)

SOURCE = "blue_llama"
CATEGORY = "arts_culture"
VENUE = "Blue Llama Jazz Club"
ICAL_URL = "https://bluellamaclub.com/tickets-calendar/?ical=1"
TAGS = ["music", "jazz"]


def scrape() -> list[dict]:
    """Fetch and parse Blue Llama Jazz Club's iCal event feed."""
    session = RateLimitedSession()
    response = session.get(ICAL_URL)
    events = parse_ical_feed(response.content, SOURCE, CATEGORY)
    for event in events:
        event["venue"] = VENUE
        for tag in TAGS:
            if tag not in event["tags"]:
                event["tags"].append(tag)
    return events
