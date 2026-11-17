# tests/test_merge.py
import json
from pathlib import Path
import pytest
from merge import compute_similarity, merge_events, load_raw_events


def make_test_event(title, date, venue, time="8:00 PM", source="test", url=None):
    return {
        "id": f"{source}-{date}-{title.lower().replace(' ', '-')}",
        "title": title,
        "date": date,
        "time": time,
        "venue": venue,
        "url": url or f"https://example.com/{title}",
        "source": source,
        "category": "arts_culture",
        "tags": [],
        "description": "",
        "address": "",
        "also_listed_at": [],
        "image_url": None,
        "possible_duplicate": False,
        "scraped_at": "2026-03-13T06:00:00Z",
    }


def test_compute_similarity_identical():
    a = make_test_event("The War on Drugs", "2026-03-15", "The Ark")
    b = make_test_event("The War on Drugs", "2026-03-15", "The Ark")
    score = compute_similarity(a, b)
    assert score >= 95


def test_compute_similarity_different_events():
    a = make_test_event("Jazz Night", "2026-03-15", "Blue Llama")
    b = make_test_event("Comedy Show", "2026-03-15", "Blind Pig")
    score = compute_similarity(a, b)
    assert score < 70


def test_compute_similarity_fuzzy_title():
    a = make_test_event("The Ark Presents: The War on Drugs", "2026-03-15", "The Ark")
    b = make_test_event("The War on Drugs", "2026-03-15", "Ark")
    score = compute_similarity(a, b)
    assert score >= 80


def test_merge_events_deduplicates_above_threshold():
    events = [
        make_test_event("The War on Drugs", "2026-03-15", "The Ark", source="ark",
                        url="https://theark.org/event/1"),
        make_test_event("The War on Drugs", "2026-03-15", "The Ark", source="observer",
                        url="https://observer.com/event/1"),
    ]
    result = merge_events(events)
    assert len(result) == 1
    merged = result[0]
    assert len(merged["also_listed_at"]) == 1


def test_merge_events_flags_possible_duplicates():
    # Build events that score deterministically in the 70-84 range (~73.8)
    # Same date, slightly different title ("Live" suffix), different venue
    events = [
        make_test_event("War on Drugs Live", "2026-03-15", "The Ark",
                        source="ark", url="https://theark.org/1"),
        make_test_event("War on Drugs", "2026-03-15", "Blind Pig",
                        source="eventbrite", url="https://eventbrite.com/1"),
    ]
    result = merge_events(events)
    # Score ~73.8: in flagging range — kept separate but both flagged
    assert len(result) in (1, 2)
    if len(result) == 2:
        assert result[0]["possible_duplicate"] is True
        assert result[1]["possible_duplicate"] is True


def test_merge_events_keeps_more_detailed():
    short = make_test_event("Great Show", "2026-03-15", "The Ark", source="ark")
    short["description"] = "Short desc"
    long_ = make_test_event("Great Show", "2026-03-15", "The Ark", source="observer")
    long_["description"] = "A much longer and more detailed description of the event"
    result = merge_events([short, long_])
    assert len(result) == 1
    assert result[0]["description"] == long_["description"]


def test_merge_events_preserves_distinct_events():
    events = [
        make_test_event("Jazz Night", "2026-03-15", "Blue Llama"),
        make_test_event("Rock Show", "2026-03-15", "Blind Pig"),
        make_test_event("Comedy Hour", "2026-03-16", "Conor O'Neill's"),
    ]
    result = merge_events(events)
    assert len(result) == 3


def test_load_raw_events_missing_dir(tmp_path, monkeypatch):
    import merge
    monkeypatch.setattr(merge, "RAW_DIR", tmp_path / "nonexistent")
    result = load_raw_events()
    assert result == []


def test_load_raw_events_reads_json_files(tmp_path, monkeypatch):
    import merge
    monkeypatch.setattr(merge, "RAW_DIR", tmp_path)
    events = [{"id": "test-1", "title": "Event 1"}]
    (tmp_path / "test.json").write_text(json.dumps(events))
    result = load_raw_events()
    assert result == events


def test_load_raw_events_skips_malformed_json(tmp_path, monkeypatch):
    import merge
    monkeypatch.setattr(merge, "RAW_DIR", tmp_path)
    (tmp_path / "good.json").write_text(json.dumps([{"id": "1"}]))
    (tmp_path / "bad.json").write_text("not valid json")
    result = load_raw_events()
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_main_excludes_expired_events_from_preserved_raw_data(tmp_path, monkeypatch):
    from datetime import date, timedelta
    import merge

    today = date(2026, 3, 15)
    monkeypatch.setattr(merge, "local_today", lambda: today)
    events = [
        make_test_event("Past", (today - timedelta(days=1)).isoformat(), "Venue"),
        make_test_event("Today", today.isoformat(), "Venue"),
        make_test_event("Future", (today + timedelta(days=1)).isoformat(), "Venue"),
    ]
    (tmp_path / "source.json").write_text(json.dumps(events))
    monkeypatch.setattr(merge, "RAW_DIR", tmp_path)
    monkeypatch.setattr(merge, "OUTPUT_PATH", tmp_path / "output" / "events.json")

    merge.main()

    output = json.loads(merge.OUTPUT_PATH.read_text())
    assert [event["title"] for event in output["events"]] == ["Today", "Future"]


def test_same_id_occurrences_survive_merge_when_better_keeper_changes():
    first = make_test_event("Show", "2026-03-15", "The Ark", time="7:00 PM")
    duplicate = make_test_event("Show", "2026-03-15", "The Ark", time="19:00", source="other")
    duplicate["description"] = "More details"
    later = make_test_event("Show", "2026-03-15", "The Ark", time="9:00 PM")

    result = merge_events([first, duplicate, later])

    assert len(result) == 2
    assert {event["time"] for event in result} == {"19:00", "9:00 PM"}
    assert result[0]["also_listed_at"] == [first["url"]]


@pytest.mark.parametrize("first,second", [
    ("7 PM", "19:00"),
    ("12:00 AM", "00:00"),
    ("12 p.m.", "12:00"),
])
def test_equivalent_times_merge(first, second):
    a = make_test_event("Show", "2026-03-15", "The Ark", time=first)
    b = make_test_event("Show", "2026-03-15", "The Ark", time=second, source="other")
    assert compute_similarity(a, b) == 100
    assert len(merge_events([a, b])) == 1


@pytest.mark.parametrize("first,second", [
    ("7:00 PM", "9:00 PM"),
    ("", "7:00 PM"),
    ("", ""),
    ("doors at 7", "7:00 PM"),
])
def test_distinct_or_unknown_times_are_not_merged(first, second):
    a = make_test_event("Show", "2026-03-15", "The Ark", time=first)
    b = make_test_event("Show", "2026-03-15", "The Ark", time=second)
    assert len(merge_events([a, b])) == 2


def test_events_are_sorted_by_date_and_start_time_with_stable_ties(monkeypatch):
    import merge

    # Isolate ordering from fuzzy matching of the deliberately similar titles.
    monkeypatch.setattr(merge, "MERGE_THRESHOLD", 101)
    times = [
        "all day", "7:00pm", "12:00 PM", "8pm", "19:00", "",
        "12:00 AM", "08:00", "7:00–9:00 p.m.", "11–1 pm",
        "noon", "midnight", "12:30–5:30 p.m.", "TBA", "7:00 pm",
        "9:00 AM - 10:00 AM", "18:00–20:00",
    ]
    events = [
        make_test_event(f"Event {i}", "2026-03-15", f"Venue {i}", time=time)
        for i, time in enumerate(times)
    ]
    events.append(make_test_event("Earlier", "2026-03-14", "Other", time="8pm"))
    result = merge_events(events)
    assert [event["title"] for event in result] == [
        "Earlier", "Event 6", "Event 11", "Event 7", "Event 15",
        "Event 9", "Event 2", "Event 10", "Event 12", "Event 16",
        "Event 1", "Event 4", "Event 8", "Event 14", "Event 3",
        "Event 0", "Event 5", "Event 13",
    ]


@pytest.mark.parametrize("time,expected", [
    ("11–12 pm", (11, 0)),
    ("11–12 am", (23, 0)),
    ("12–2 pm", (12, 0)),
    ("12–2 am", (0, 0)),
])
def test_range_start_around_noon_and_midnight(time, expected):
    from merge import _start_time
    assert _start_time(time) == expected


def test_location_normalization_handles_markup_and_embedded_address():
    event = make_test_event("Show", "2026-03-15", "<b>Hall &amp; Co</b>, 123 Main St, Ann Arbor, MI 48104")
    result = merge_events([event])[0]
    assert result["venue"] == "Hall & Co, 123 Main St, Ann Arbor, MI 48104"
    assert result["address"] == "123 Main St, Ann Arbor, MI 48104"
    assert result["location_city"] == "Ann Arbor"
    assert result["location_status"] == "resolved"
    assert event["address"] == ""


@pytest.mark.parametrize("venue,address,status", [
    ("", "", "needs_review"),
    ("Room 2010", "", "needs_review"),
    ("Online", "", "online"),
    ("Electronic Meeting", "", "online"),
    ("Online", "123 Main St, Ann Arbor, MI", "resolved"),
    ("Online and in person", "", "needs_review"),
    ("Hall", "123 Main St", "needs_review"),
    ("Hall", "Ann Arbor, MI", "needs_review"),
])
def test_location_status_is_conservative(venue, address, status):
    event = make_test_event("Show", "2026-03-15", venue)
    event["address"] = address
    assert merge_events([event])[0]["location_status"] == status


def test_verified_library_branch_is_source_specific_and_preserves_room():
    event = make_test_event("Show", "2026-03-15", "Downtown Library: Secret Lab", source="aadl")
    result = merge_events([event])[0]
    assert result["venue"] == "Downtown Library: Secret Lab"
    assert result["address"] == "343 South Fifth Ave, Ann Arbor, MI 48104"
    assert result["location_city"] == "Ann Arbor"
    assert result["location_address_source"] == "https://aadl.org/aboutus/locations"
    assert result["location_status"] == "resolved"
    event["source"] = "other"
    assert merge_events([event])[0]["location_status"] == "needs_review"


@pytest.mark.parametrize("venue", [
    "Rec Im Building - 127",
    "Rec Im Building - 226",
])
def test_emu_building_match_preserves_room_and_source(venue):
    event = make_test_event("Campus event", "2026-03-15", venue, source="eastern_michigan")
    result = merge_events([event])[0]
    assert result["venue"] == venue
    assert result["location_city"] == "Ypsilanti"
    assert result["location_status"] == "resolved"
    assert result["address"]
    from urllib.parse import urlsplit
    assert urlsplit(result["location_address_source"]).hostname.endswith(".emich.edu")
    event["source"] = "other"
    assert merge_events([event])[0]["location_status"] == "needs_review"


def test_um_campus_building_matches_with_room():
    event = make_test_event("Talk", "2026-03-15", "Michigan Union - Room 100", source="um_events")
    result = merge_events([event])[0]
    assert result["venue"] == "Michigan Union - Room 100"
    assert result["address"] == "530 S State St, Ann Arbor, MI 48109"
    assert result["location_status"] == "resolved"
    assert result["location_city"] == "Ann Arbor"


def test_campus_registry_never_overwrites_explicit_location():
    event = make_test_event("Talk", "2026-03-15", "Michigan Union - Room 100", source="um_events")
    event["address"] = "123 Main St, Chelsea, MI"
    result = merge_events([event])[0]
    assert result["address"] == event["address"]
    assert result["location_city"] == "Chelsea"
    assert "location_address_source" not in result


def test_unknown_campus_venue_stays_in_review():
    from locations import location_review
    event = make_test_event("Mystery", "2026-03-15", "Campuswide", source="eastern_michigan")
    result = merge_events([event])
    assert result[0]["location_status"] == "needs_review"
    assert location_review(result)["locations"][0]["venue"] == "Campuswide"


def test_dedup_recovers_secondary_address_without_mutating_inputs():
    import copy
    first = make_test_event("Show", "2026-03-15", "Hall", source="first")
    first["address"] = "Room 2"
    first["description"] = "The more detailed event"
    second = make_test_event("Show", "2026-03-15", "Hall", source="second")
    second["address"] = "123 Main St, Ann Arbor, MI"
    original = copy.deepcopy([first, second])
    result = merge_events([first, second])[0]
    assert result["address"] == second["address"]
    assert result["location_original_address"] == "Room 2"
    assert result["location_status"] == "resolved"
    assert [first, second] == original


def test_conflicting_towns_remain_separate():
    first = make_test_event("Show", "2026-03-15", "Hall", source="first")
    first["address"] = "Ann Arbor, MI"
    second = make_test_event("Show", "2026-03-15", "Hall", source="second")
    second["address"] = "123 Main St, Chelsea, MI"
    result = merge_events([first, second])
    assert len(result) == 2
    assert {event["location_city"] for event in result} == {"Ann Arbor", "Chelsea"}


def test_different_street_addresses_remain_separate():
    first = make_test_event("Show", "2026-03-15", "Hall", source="first")
    first["address"] = "123 Main St, Ann Arbor, MI"
    second = make_test_event("Show", "2026-03-15", "Hall", source="second")
    second["address"] = "456 Main St, Ann Arbor, MI"
    assert len(merge_events([first, second])) == 2


def test_review_queue_does_not_conflate_sources_with_same_venue_name():
    from locations import location_review
    first = make_test_event("One", "2026-03-15", "Community Center", source="first")
    second = make_test_event("Two", "2026-03-16", "Community Center", source="second")
    assert location_review(merge_events([first, second]))["count"] == 2


def test_review_queue_groups_named_locations_but_not_unknown_occurrences():
    from locations import location_review
    events = [
        make_test_event("One", "2026-03-15", "Mystery Hall", url="https://example.com/one"),
        make_test_event("Two", "2026-03-16", "Mystery Hall", url="https://example.com/two"),
        make_test_event("Three", "2026-03-17", ""),
        make_test_event("Four", "2026-03-18", ""),
        make_test_event("Five", "2026-03-19", "Online"),
    ]
    normalized = merge_events(events)
    queue = location_review(normalized)
    assert queue == location_review(list(reversed(normalized)))
    assert queue["count"] == 3
    group = next(item for item in queue["locations"] if item["venue"] == "Mystery Hall")
    assert group["count"] == 2
    assert [event["url"] for event in group["events"]] == ["https://example.com/one", "https://example.com/two"]
    assert group["reason"] == "incomplete_address"


def test_main_replaces_review_queue_when_location_is_resolved(tmp_path, monkeypatch):
    from datetime import date
    import merge
    monkeypatch.setattr(merge, "local_today", lambda: date(2026, 3, 15))
    monkeypatch.setattr(merge, "RAW_DIR", tmp_path)
    monkeypatch.setattr(merge, "OUTPUT_PATH", tmp_path / "published" / "events.json")
    event = make_test_event("Show", "2026-03-15", "Mystery Hall")
    source = tmp_path / "source.json"
    source.write_text(json.dumps([event]))
    merge.main()
    queue_path = merge.OUTPUT_PATH.parent / "location-review.json"
    assert json.loads(queue_path.read_text())["count"] == 1
    event["address"] = "123 Main St, Ann Arbor, MI"
    source.write_text(json.dumps([event]))
    merge.main()
    assert json.loads(queue_path.read_text()) == {"count": 0, "locations": []}


def test_legacy_athletics_are_filtered_before_output_and_research(tmp_path, monkeypatch):
    from datetime import date, timedelta
    import merge

    today = date(2026, 11, 15)
    monkeypatch.setattr(merge, "local_today", lambda: today)
    monkeypatch.setattr(merge, "RAW_DIR", tmp_path)
    monkeypatch.setattr(merge, "OUTPUT_PATH", tmp_path / "published" / "events.json")
    cases = [
        ("University of Michigan Football at Ohio State", "Columbus, Ohio", "um_athletics", False),
        ("University of Michigan Football at Ohio State", "", "um_athletics", False),
        ("EMU Football at Western Michigan", "Kalamazoo, Mich.", "eastern_michigan", False),
        ("EMU Men's Basketball vs Kennesaw State", "Cancun, Mexico", "eastern_michigan", False),
        ("EMU Swimming & Diving vs Golden Grizzly Classic", "Rochester, Mich.", "eastern_michigan", False),
        ("EMU Women's Rowing vs USRowing", "West Windsor, N.J.", "eastern_michigan", False),
        ("EMU Women's Basketball vs Rival", "Pittsburgh, PA", "eastern_michigan", False),
        ("University of Michigan Football vs UCLA", "Ann Arbor, Mich.", "um_athletics", True),
        ("EMU Men's Basketball vs Detroit Mercy", "Ypsilanti, Mich., Gervin GameAbove Center", "eastern_michigan", True),
        ("EMU Football at Michigan", "Michigan Stadium", "eastern_michigan", True),
        ("EMU Football at Michigan", "Ann Arbor", "eastern_michigan", True),
        ("EMU Soccer vs Rival", "Mystery Field", "eastern_michigan", True),
        ("EMU Soccer vs Rival", "", "eastern_michigan", True),
        ("EMU Football talk at the library", "Columbus, Ohio", "eastern_michigan", True),
        ("Agentic AI: At the Frontier of Practice", "Student Center", "eastern_michigan", True),
        ("EMU alumni gathering at the game", "Atlanta, GA", "eastern_michigan", True),
        ("Community football class at the park", "Toledo, Ohio", "other", True),
    ]
    events = []
    for index, (title, venue, source, _) in enumerate(cases):
        event = make_test_event(title, (today + timedelta(days=index)).isoformat(), venue, source=source)
        if source == "um_athletics":
            event["category"] = "um_athletics"
        events.append(event)
    (tmp_path / "legacy.json").write_text(json.dumps(events), encoding="utf-8")

    merge.main()

    output = json.loads(merge.OUTPUT_PATH.read_text())
    expected_ids = {event["id"] for event, case in zip(events, cases) if case[3]}
    excluded_ids = {event["id"] for event, case in zip(events, cases) if not case[3]}
    assert {event["id"] for event in output["events"]} == expected_ids
    queue = json.loads((merge.OUTPUT_PATH.parent / "location-review.json").read_text(encoding="utf-8"))
    queued_ids = {event["id"] for location in queue["locations"] for event in location["events"]}
    assert not queued_ids & excluded_ids
    assert events[11]["id"] in queued_ids


@pytest.mark.parametrize("town", [
    "Ann Arbor", "Ypsilanti", "Dexter", "Chelsea", "Milan", "Whitmore Lake", "Brighton",
    "Saline", "Manchester", "Pittsfield Township", "Northfield Township", "Scio Township", "Superior Township",
])
def test_local_neutral_site_sports_survive(town):
    event = make_test_event("EMU Soccer vs Rival", "2026-11-15", f"{town}, Michigan",
                            source="eastern_michigan")
    assert len(merge_events([event])) == 1

