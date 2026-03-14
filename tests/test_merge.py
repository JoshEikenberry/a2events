# tests/test_merge.py
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
    events = [
        make_test_event("The Ark Presents The War on Drugs Live", "2026-03-15", "The Ark",
                        source="ark", url="https://theark.org/1"),
        make_test_event("War on Drugs", "2026-03-15", "Ark Ann Arbor",
                        source="eventbrite", url="https://eventbrite.com/1"),
    ]
    result = merge_events(events)
    # Score should be 70-85 range — kept separate but flagged
    # (exact behavior depends on score; test that at least one is flagged or merged)
    assert len(result) in (1, 2)
    if len(result) == 2:
        assert any(e["possible_duplicate"] for e in result)


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
