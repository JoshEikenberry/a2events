"""Source failures must not be published as successful empty or partial calendars."""
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from scrapers import (
    aadl, blind_pig, city_ann_arbor, eastern_michigan, eventbrite,
    michigan_theater, resident_advisor, um_events, washtenaw_county, ypsilanti,
)


@pytest.mark.parametrize("module", [city_ann_arbor, eastern_michigan, um_events, washtenaw_county, ypsilanti, aadl, michigan_theater])
def test_fetch_failure_propagates(module):
    with patch.object(module, "RateLimitedSession") as session:
        session.return_value.get.side_effect = ConnectionError("offline")
        with pytest.raises(ConnectionError, match="offline"):
            module.scrape()


@pytest.mark.parametrize("module,payload", [
    (city_ann_arbor, {}),
    (um_events, None),
    (eastern_michigan, {}),
    (eastern_michigan, {"groupedByDay": {"Monday": None}}),
    (washtenaw_county, {}),
    (washtenaw_county, {"value": [], "@odata.nextLink": "next"}),
])
def test_invalid_json_response_is_failure(module, payload):
    with patch.object(module, "RateLimitedSession") as session:
        response = session.return_value.get.return_value
        response.json.return_value = payload
        response.text = json.dumps(payload)
        with pytest.raises(ValueError):
            module.scrape()


@pytest.mark.parametrize("module,payload", [
    (city_ann_arbor, []),
    (um_events, {}),
    (eastern_michigan, {"groupedByDay": {}}),
    (washtenaw_county, {"value": []}),
])
def test_valid_empty_json_calendar(module, payload):
    with patch.object(module, "RateLimitedSession") as session:
        response = session.return_value.get.return_value
        response.json.return_value = payload
        response.text = json.dumps(payload)
        assert module.scrape() == []


def test_aadl_later_page_failure_does_not_return_partial_data():
    with patch.object(aadl, "RateLimitedSession") as session, patch.object(aadl, "_parse_page", return_value=([{"title": "event"}], 1, 1)):
        session.return_value.get.side_effect = [MagicMock(text='<div id="search-results"></div>'), ConnectionError("page 2")]
        with pytest.raises(ConnectionError, match="page 2"):
            aadl.scrape()


@pytest.mark.parametrize("module,empty_html", [
    (aadl, '<div id="search-results"></div>'),
    (ypsilanti, '<div class="calendars"></div>'),
    (michigan_theater, '<script>var calendarEvents = [];</script>'),
])
def test_html_empty_calendar_and_error_page(module, empty_html):
    with patch.object(module, "RateLimitedSession") as session:
        response = session.return_value.get.return_value
        response.text = empty_html
        assert module.scrape() == []
        response.text = "<html><body>Service unavailable</body></html>"
        with pytest.raises(ValueError):
            module.scrape()


def test_michigan_theater_invalid_embedded_json_fails():
    with patch.object(michigan_theater, "RateLimitedSession") as session:
        session.return_value.get.return_value.text = '<script>var calendarEvents = [invalid];</script>'
        with pytest.raises(ValueError):
            michigan_theater.scrape()


def test_resident_advisor_failures_and_empty_calendar():
    with patch.object(resident_advisor.requests, "post") as post:
        post.side_effect = ConnectionError("offline")
        with pytest.raises(ConnectionError):
            resident_advisor.scrape()
        post.side_effect = None
        post.return_value.json.return_value = {"errors": [{"message": "unavailable"}], "data": {"eventListings": {"data": []}}}
        with pytest.raises(ValueError):
            resident_advisor.scrape()
        post.return_value.json.return_value = {"data": {"eventListings": {"data": []}}}
        assert resident_advisor.scrape() == []


def test_resident_advisor_later_page_failure_propagates():
    first = MagicMock()
    first.json.return_value = {"data": {"eventListings": {"data": [{}] * 100}}}
    with patch.object(resident_advisor.requests, "post", side_effect=[first, ConnectionError("page 2")]):
        with pytest.raises(ConnectionError, match="page 2"):
            resident_advisor.scrape()


def test_eventbrite_pagination_failure_and_empty_calendar():
    with patch.object(eventbrite.requests, "Session") as cls:
        session = cls.return_value
        session.cookies = []
        session.headers = {}
        first = MagicMock()
        first.json.return_value = {"events": {"results": [], "pagination": {"page_count": 2, "page_number": 1}}}
        session.post.side_effect = [first, ConnectionError("page 2")]
        with pytest.raises(ConnectionError, match="page 2"):
            eventbrite.scrape()
        session.post.side_effect = None
        session.post.return_value.json.return_value = {"events": {"results": [], "pagination": {"page_count": 0, "page_number": 1}}}
        assert eventbrite.scrape() == []
        session.post.return_value.json.return_value = {"events": {}}
        with pytest.raises(ValueError):
            eventbrite.scrape()


def test_local_date_used_for_source_queries():
    today = date(2026, 12, 31)
    with patch.object(eastern_michigan, "local_today", return_value=today), patch.object(eastern_michigan, "RateLimitedSession") as session:
        session.return_value.get.return_value.json.return_value = {"groupedByDay": {}}
        eastern_michigan.scrape()
        assert session.return_value.get.call_args_list[0].args[0].endswith("/2026/12/31")
    with patch.object(washtenaw_county, "local_today", return_value=today):
        assert "2026-12-31T00:00:00Z" in washtenaw_county._build_api_params()["$filter"]
    with patch.object(blind_pig, "local_today", return_value=today):
        assert blind_pig._parse_event_date("Dec 31") == "2026-12-31"
    with patch.object(resident_advisor, "local_today", return_value=today), patch.object(resident_advisor.requests, "post") as post:
        post.return_value.json.return_value = {"data": {"eventListings": {"data": []}}}
        resident_advisor.scrape()
        dates = post.call_args.kwargs["json"]["variables"]["filters"]["listingDate"]
        assert dates["gte"] == "2026-12-31"
