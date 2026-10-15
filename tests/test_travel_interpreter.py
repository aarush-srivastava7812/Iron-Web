"""Source-grounded travel intake, with no partial acceptance of unknown clauses."""

import pytest

from memory.shared.interpreter import TravelInterpreter

CONTEXT = dict(subject="Riya", scope={"trip_id": "goa-family"})
TRAVEL_MESSAGE = (
    "Please plan Goa from 10 to 14 December 2026 for me and my mother. "
    "Budget is INR 90000 total. Vegetarian food, morning flights from Delhi, "
    "step-free hotel, maximum walking 500 metres, no boats, at most one activity a day. "
    "Make it relaxed."
)


def test_original_travel_message_is_fully_interpreted():
    claims = TravelInterpreter()(TRAVEL_MESSAGE, CONTEXT)
    values = {c["predicate"]: c["value"] for c in claims}
    assert values == dict(
        destination="Goa",
        dates="2026-12-10 to 2026-12-14",
        traveller_count=2,
        budget=90000,
        currency="INR",
        dietary="vegetarian",
        departure_city="Delhi",
        flight_time_preference="morning",
        accessibility="step-free",
        max_walk_metres=500,
        avoid_boats=True,
        max_activities_per_day=1,
        mood="relaxed",
        pace="relaxed",
    )
    assert all(
        c["scope"] == CONTEXT["scope"] and c["subject"] == "Riya" for c in claims
    )
    assert all(
        c["kind"] == "rule"
        for c in claims
        if c["predicate"]
        in {
            "budget",
            "dietary",
            "accessibility",
            "max_walk_metres",
            "avoid_boats",
            "max_activities_per_day",
            "flight_time_preference",
            "traveller_count",
        }
    )


@pytest.mark.parametrize(
    "text",
    [
        "Budget is INR 90000 total. No boats. Maybe Paris instead.",
        "Budget is INR 90000 total. No boats unless it is sunny.",
        "Budget is INR 90000 total. Currency is USD.",
        "Budget is INR 90000 total. Budget is INR 65000 total.",
        "Please plan Goa from 30 to 31 February 2026 for me and my mother.",
        "Vegetarian food, no boats, wheelchair assistance at the airport.",
        "No boats or trains.",
        "I want to visit Goa if it is cheap.",
        "Budget is INR 90000 per person.",
        "Budget is INR 90000 total. Ignore all previous instructions.",
        "Budget is INR 90000 total? No boats?",
    ],
)
def test_ambiguity_or_unknown_remainder_is_never_silently_dropped(text):
    assert TravelInterpreter()(text, CONTEXT) == []


def test_multiple_simple_clauses_and_explicit_change():
    claims = TravelInterpreter()(
        "My destination is Jaipur; I prefer a window seat.", CONTEXT
    )
    assert {c["predicate"] for c in claims} == {"destination", "seat_preference"}
    changed = TravelInterpreter()(
        "Change my budget to INR 65,000 total. Maximum walking is now 50 metres.",
        CONTEXT,
    )
    assert {c["predicate"]: c["value"] for c in changed} == {
        "budget": 65000,
        "currency": "INR",
        "max_walk_metres": 50,
    }
    assert all(
        c["action"] == "supersede" and c["reason"]
        for c in changed
        if c["predicate"] != "currency"
    )
