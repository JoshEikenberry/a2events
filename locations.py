"""Conservative, offline normalization and research queue for event locations."""
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in ("br", "p", "div", "li"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1
        elif tag in ("p", "div", "li"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_location(value):
    """Return readable source text without markup or HTML entities."""
    if not isinstance(value, str):
        return ""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return " ".join("".join(parser.parts).split())


# Deliberately require a street type or a directional street name, rather than
# interpreting room numbers, ZIP codes, and dates as street addresses.
_STREET = re.compile(
    r"\b\d{1,6}(?:-\d+)?\s+(?:[NSEW]\.?(?:orth|outh|ast|est)?\s+)?"
    r"[\w.'’#-]+(?:\s+[\w.'’#-]+){0,5}\s+"
    r"(?:street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|lane|ln|"
    r"court|ct|place|pl|parkway|pkwy|highway|hwy|way|trail|trl)\b\.?"
    r"|\b\d{1,6}\s+[NSEW]\.\s+[A-Za-z][\w.'’ -]*?(?=,|$)", re.I,
)
_CITY = re.compile(
    r"(?:^|,)\s*([A-Za-z][A-Za-z .'-]*?),\s*(?:MI|Michigan|Mich\.?)"
    r"(?:\s+\d{5}(?:-\d{4})?)?(?=\s*(?:,|$))", re.I,
)
_ONLINE = re.compile(
    r"^(?:online(?: event| meeting)?|virtual(?: event| meeting)?|"
    r"electronic meeting|webinar|zoom(?: meeting)?|livestream|live stream)$", re.I,
)

# Registry matches are source-specific; conflicting aliases must never guess.
_DATA_DIR = Path(__file__).resolve().parent / "data"
_LOCATIONS = {}
for _filename in ("locations.json", "campus_emu.json", "campus_um.json"):
    with (_DATA_DIR / _filename).open(encoding="utf-8") as registry_file:
        for _entry in json.load(registry_file):
            _key = (_entry["source"], _entry["venue"].casefold())
            if _key in _LOCATIONS and _LOCATIONS[_key] != _entry:
                _LOCATIONS[_key] = None
            else:
                _LOCATIONS[_key] = _entry


def _find_location(source, venue):
    name = venue.strip().casefold()
    if source in ("eastern_michigan", "um_events", "um_athletics"):
        name = re.sub(r"^(?:ypsilanti|ann arbor),\s*(?:mich\.?|mi),\s*", "", name)
    candidates = [name, name.split(":", 1)[0].strip()]
    if source in ("eastern_michigan", "um_events", "um_athletics"):
        candidates.append(re.split(r"\s+-\s+|\s+room\s*:", name, maxsplit=1)[0].strip())
    for candidate in candidates:
        key = (source, candidate)
        if key in _LOCATIONS:
            return _LOCATIONS[key]
    return None


def normalize_location(event):
    """Return a copy with clean location strings and conservative classification."""
    result = dict(event)
    venue = clean_location(event.get("venue"))
    address = clean_location(event.get("address"))
    # Some sources put the entire postal address in the venue field.
    if not address:
        street = _STREET.search(venue)
        if street:
            address = venue[street.start():].strip(" ,")
    if not address:
        entry = _find_location(event.get("source"), venue)
        if entry:
            address = entry["address"]
            result["location_address_source"] = entry["source_url"]
    result["venue"] = venue
    result["address"] = address
    city_match = _CITY.search(address) or _CITY.search(venue)
    result["location_city"] = city_match.group(1).strip() if city_match else ""
    if _STREET.search(address) and city_match:
        result["location_status"] = "resolved"
    elif (_ONLINE.fullmatch(venue) and not address) or (not venue and _ONLINE.fullmatch(address)):
        result["location_status"] = "online"
    else:
        result["location_status"] = "needs_review"
    return result


def location_review(events):
    """Group unresolved named locations; keep anonymous occurrences separate."""
    groups = {}
    for index, event in enumerate(events):
        if event["location_status"] != "needs_review":
            continue
        venue, address = event["venue"], event["address"]
        key = (event.get("source", "").casefold(), venue.casefold(), address.casefold(),
               event["location_city"].casefold()) if venue or address else ("", index)
        if key not in groups:
            groups[key] = {
                "venue": venue,
                "address": address,
                "location_city": event["location_city"],
                "status": "needs_review",
                "reason": "incomplete_address" if venue or address else "missing_location",
                "count": 0,
                "events": [],
            }
        group = groups[key]
        group["venue"] = min(group["venue"], venue)
        group["address"] = min(group["address"], address)
        group["location_city"] = min(group["location_city"], event["location_city"])
        group["count"] += 1
        group["events"].append({
            "id": event.get("id", ""),
            "title": event.get("title", ""),
            "date": event.get("date", ""),
            "time": event.get("time", ""),
            "url": event.get("url", ""),
            "source": event.get("source", ""),
            "also_listed_at": list(event.get("also_listed_at") or []),
        })
    items = list(groups.values())
    for item in items:
        item["events"].sort(key=lambda e: (e["date"], e["time"], e["id"], e["url"], e["title"], e["source"], e["also_listed_at"]))
    items.sort(key=lambda item: (item["venue"].casefold(), item["address"].casefold(),
                                 item["events"][0]["date"], item["events"][0]["time"],
                                 item["events"][0]["id"], item["events"][0]["url"],
                                 item["events"][0]["title"], item["events"][0]["source"]))
    return {"count": len(items), "locations": items}
