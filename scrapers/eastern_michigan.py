"""Scraper for Eastern Michigan University events (emich.edu).

The EMU events calendar at https://www.emich.edu/events/ is served through
a Localist-based widget embedded in a Drupal CMS. The page is protected by
Cloudflare, so programmatic access returns 403. The scraper handles this
gracefully: on any fetch/parse failure it logs a warning and returns [].
"""
import logging
from bs4 import BeautifulSoup
from scrapers.base import RateLimitedSession, make_event, is_in_window, parse_date

logger = logging.getLogger(__name__)

SOURCE = "eastern_michigan"
CATEGORY = "eastern_michigan"
EVENTS_URL = "https://www.emich.edu/events/"


def scrape() -> list[dict]:
    """Fetch and parse EMU campus events."""
    session = RateLimitedSession()
    try:
        response = session.get(EVENTS_URL)
        soup = BeautifulSoup(response.text, "lxml")
    except Exception as exc:
        logger.error("eastern_michigan: failed to fetch events page: %s", exc)
        return []

    events = []
    # Localist calendar widget: each event is in .lw_cal_event_list_item > .lw_cal_event
    for item in soup.select(".lw_cal_event_list_item .lw_cal_event"):
        try:
            title_el = item.select_one(".lw_events_event_title a, .lw_events_event_title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            # Prefer datetime attribute on <time>, fall back to full text
            date_el = item.select_one("time[datetime]")
            if date_el:
                date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            else:
                date_block = item.select_one(".lw_events_date, .lw_events_time")
                date_text = date_block.get_text(strip=True) if date_block else ""

            date_parsed = parse_date(date_text)
            if not date_parsed or not is_in_window(date_parsed.isoformat()):
                continue

            # Build URL from link href
            link_el = item.select_one(".lw_events_event_title a[href]")
            url = link_el["href"] if link_el else EVENTS_URL
            if url and not url.startswith("http"):
                url = "https://www.emich.edu" + url
            if not url:
                url = EVENTS_URL

            # Venue from Localist location field
            venue_el = item.select_one(
                ".lw_events_location_name, .lw_events_location, .location, .venue"
            )
            venue = venue_el.get_text(strip=True) if venue_el else ""

            # Time string
            time_parts = []
            for sel in (".lw_events_time_s", ".lw_events_time_e"):
                t = item.select_one(sel)
                if t:
                    time_parts.append(t.get_text(strip=True).strip(" -"))
            time_str = " - ".join(p for p in time_parts if p)

            events.append(make_event(
                title=title,
                date=date_parsed.isoformat(),
                time=time_str,
                venue=venue,
                url=url,
                source=SOURCE,
                category=CATEGORY,
            ))
        except Exception as exc:
            logger.warning("eastern_michigan: skipping event: %s", exc)

    if not events:
        logger.warning(
            "eastern_michigan: no events parsed — page may be JS-rendered or Cloudflare-blocked"
        )
    else:
        logger.info("eastern_michigan: %d events in window", len(events))
    return events
