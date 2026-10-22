"""Behavioral turn cases: no provider calls, clocks or application database needed."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stitch_ai_travel_booking_platform/backend"))
from app.conversation_intake import understand  # noqa: E402

PLACES = [{"name": name} for name in ("Jaipur", "New Delhi", "Bengaluru", "Mumbai", "Kerala", "Goa", "Kochi")]
AT = dt.date(2026, 10, 19)


@pytest.mark.parametrize("message,current,state,expected", [
    ("from Delhi to Agra", {}, {}, {"origin": "New Delhi", "destination": "Agra"}),
    ("Delhi to Jaipur", {}, {}, {"origin": "New Delhi", "destination": "Jaipur"}),
    ("Jaipur instead of Agra", {"destination": "Agra"}, {}, {"destination": "Jaipur"}),
    ("not Jaipur, Agra", {}, {}, {"destination": "Agra"}),
    ("two", {}, {"awaiting": "traveller_count"}, {"traveller_count": 2}),
    ("for 2", {}, {"awaiting": "traveller_count"}, {"traveller_count": 2}),
    ("three", {}, {"awaiting": "duration_days"}, {"duration_days": 3}),
    ("two adults and one child", {}, {}, {"traveller_count": 3}),
    ("just me", {}, {}, {"traveller_count": 1}),
    ("both of us", {}, {}, {"traveller_count": 2}),
    ("a week", {}, {}, {"duration_days": 7}),
    ("three nights", {}, {}, {"duration_days": 4}),
    ("extend by two days", {"duration_days": 3}, {}, {"duration_days": 5}),
    ("tomorrow for three days", {}, {}, {"start_date": "2026-10-20", "duration_days": 3}),
    ("next Friday", {}, {}, {"start_date": "2026-10-23"}),
    ("1 December 2026", {}, {}, {"start_date": "2026-12-01"}),
    ("December 1, 2026", {}, {}, {"start_date": "2026-12-01"}),
    ("1 to 3 Dec 2026", {}, {}, {"start_date": "2026-12-01", "end_date": "2026-12-03"}),
    ("return on 5 December 2026", {}, {}, {"end_date": "2026-12-05"}),
    ("30k", {}, {"awaiting": "budget"}, {"budget": 30000}),
    ("1.5 lakh", {}, {"awaiting": "budget"}, {"budget": 150000}),
    ("Rs. 25,000 total", {}, {}, {"budget": 25000}),
    ("INR 10000 per person, two adults", {}, {}, {"budget": 20000, "traveller_count": 2}),
    ("two", {}, {"awaiting": "traveller_count", "per_person_budget": 12000}, {"budget": 24000, "traveller_count": 2}),
    ("three adults", {"traveller_count": 2, "budget": 30000}, {"per_person_budget": 15000}, {"budget": 45000, "traveller_count": 3}),
    ("increase my budget by 5k", {"budget": 30000}, {}, {"budget": 35000}),
    ("reduce budget by INR 5000", {"budget": 30000}, {}, {"budget": 25000}),
    ("budget INR 30000, not per person", {"traveller_count": 2}, {}, {"budget": 30000}),
    ("no dietary restrictions", {"dietary": "vegetarian"}, {}, {"dietary": None}),
    ("from Bangalore", {}, {}, {"origin": "Bengaluru"}),
    ("Mumbai", {"destination": "Agra"}, {"awaiting": "origin"}, {"origin": "Mumbai"}),
    ("15k per person", {"traveller_count": 2}, {}, {"budget": 30000}),
    ("go to Prague", {}, {}, {"destination": "Prague"}),
])
def test_explicit_or_contextual_facts(message, current, state, expected):
    turn = understand(message, current, PLACES, state, at=AT)
    assert not turn.issue, turn
    assert all(turn.updates.get(key) == value for key, value in expected.items()), turn


@pytest.mark.parametrize("message,expected_intent", [
    ("show my budget without changing my trip", "summary"),
    ("don't change my budget to INR 5000", "summary"),
    ("how many days did I choose?", "summary"),
    ("show hotels in Jaipur", "options"),
    ("tell me about Jaipur", "information"),
    ("compare Agra and Jaipur", "information"),
    ("why did research fail?", "status"),
    ("what can you do?", "help"),
    ("who can see my private trip?", "privacy"),
    ("reserve a hotel now", "booking"),
    ("recommend somewhere relaxed", "discover"),
    ("hello", "greeting"),
    ("yes", "acknowledge"),
])
def test_readonly_intents_never_become_trip_changes(message, expected_intent):
    turn = understand(message, {"destination": "Agra", "budget": 30000}, PLACES, at=AT)
    assert turn.intent == expected_intent and turn.updates == {}


@pytest.mark.parametrize("message", [
    "maybe Jaipur instead of Agra", "Jaipur or Agra", "if my friend joins, three adults",
    "INR 20000 to 40000", "budget between 20000 and 40000", "USD 3000",
    "2026-02-30", "2026-10-01", "12/11/2026", "two adults or three adults",
])
def test_ambiguous_invalid_or_hypothetical_values_need_repair(message):
    turn = understand(message, {}, PLACES, at=AT)
    assert turn.issue, turn
    assert not turn.updates, turn


def test_unscoped_bare_number_does_not_guess_and_per_person_is_pending():
    assert understand("two", {}, PLACES, at=AT).updates == {}
    turn = understand("INR 15000 per person", {}, PLACES, at=AT)
    assert turn.updates == {} and turn.pending_per_person == 15000
    assert turn.awaiting == "traveller_count"
