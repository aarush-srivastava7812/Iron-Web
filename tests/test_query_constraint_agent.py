"""Acceptance cases for facts, wishes, mandatory rules and real model failures."""
# ruff: noqa: F811 -- Imported application fixture is selected by pytest.
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stitch_ai_travel_booking_platform/backend"))
from app.query_intake import interpret  # noqa: E402
from agents.query_constraint_agent import describe_draft  # noqa: E402

PLACES = [{"name": name} for name in ("Kerala", "Goa", "New Delhi", "Jaipur")]


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr("app.conversation_intake.today", lambda: dt.date(2026, 10, 22))


def test_demo_query_keeps_facts_separate_from_preferences():
    text = ("Plan a trip to Kerala from New Delhi on 1 December 2026 for 5 days, "
            "two adults, INR 100000 total; I prefer quiet hotels and nature; ideally a window seat")
    turn, result = interpret(text, {}, PLACES)
    assert not turn.issue
    assert result.facts == dict(destination="Kerala", origin="New Delhi", start_date="2026-12-01",
                                duration_days=5, traveller_count=2, budget=100000)
    assert not result.hard_constraints
    assert len(result.soft_preferences) == 2
    assert result.updates["seat_preference"] == "window"
    assert result.updates["interests"] == ["nature"]
    assert all(e["source"] in text for e in result.evidence)


@pytest.mark.parametrize("message", ["I prefer quiet hotels", "Ideally travel by train", "I would like a budget around INR 50000"])
def test_optional_wishes_never_become_hard_filters(message):
    _, result = interpret(message, {}, PLACES)
    assert not result.facts
    assert not result.hard_constraints
    assert result.soft_preferences


def test_mandatory_rules_and_allergies_survive_soft_language():
    _, result = interpret("I prefer a quiet hotel; wheelchair access is mandatory; I have a peanut allergy; avoid boats", {}, PLACES)
    assert len(result.hard_constraints) == 3
    assert result.soft_preferences == ["I prefer a quiet hotel"]
    assert "quiet hotel" not in str(result.hard_constraints)


def test_earlier_rules_survive_a_correction_and_budget_math_is_deterministic():
    _, result = interpret("INR 15000 per person, two adults; I prefer nature", {"hard_requirements": ["no boats"]}, PLACES)
    assert result.facts["budget"] == 30000
    assert "hard_requirements" not in result.updates
    assert result.preferences["interests"] == ["nature"]


def test_readonly_questions_and_uncertain_facts_do_not_change_the_draft():
    _, result = interpret("Show hotels in Kerala", {"destination": "Goa"}, PLACES)
    assert result.updates == {}
    turn, result = interpret("Maybe Kerala instead of Goa", {"destination": "Goa"}, PLACES)
    assert turn.issue and not result.updates


def test_fact_and_optional_clause_can_coexist_without_guessing():
    turn, result = interpret("two adults; ideally a quiet hotel if possible", {}, PLACES)
    assert not turn.issue
    assert result.facts == {"traveller_count": 2}
    assert len(result.soft_preferences) == 1


class Model:
    def __init__(self, response):
        self.response = response
    def chat_json(self, *args, **kwargs):
        return self.response


def test_hosted_misclassification_does_not_promote_a_preference():
    _, result = interpret("I prefer quiet hotels", {}, PLACES,
                          client=Model({"updates": {"budget": 80000, "hard_requirements": ["I prefer quiet hotels"]}}))
    assert result.mode == "nvidia"
    assert not result.facts and not result.hard_constraints
    assert result.soft_preferences == ["I prefer quiet hotels"]


def test_hosted_failure_stays_visibly_unavailable():
    _, result = interpret("Plan Kerala for 5 days", {}, PLACES, client=Model(None))
    assert result.status == "unavailable" and not result.updates


def test_hosted_preference_cannot_demote_an_accessibility_requirement():
    _, result = interpret("I need wheelchair access", {}, PLACES,
                          client=Model({"updates": {}, "soft_preferences": ["wheelchair access"]}))
    assert result.hard_constraints and not result.soft_preferences


def test_mixed_hosted_query_cannot_promote_an_optional_budget():
    _, result = interpret("two adults; ideally budget INR 50000", {}, PLACES,
                          client=Model({"updates": {"traveller_count": 2, "budget": 50000}}))
    assert result.facts == {"traveller_count": 2}
    assert "budget" not in result.updates
    assert result.soft_preferences == ["ideally budget INR 50000"]


def test_current_draft_drives_machine_constraints_after_manual_edit():
    result = describe_draft({"budget": 60000, "traveller_count": 3, "soft_preferences": ["quiet hotels"]},
                            {"facts": {"budget": 100000}})
    assert result["facts"]["budget"] == 60000
    assert {"field": "budget", "operator": "lte", "value": 60000, "enforcement": "hard", "unit": "INR_total"} in result["constraints"]


def test_no_dietary_restrictions_is_not_a_new_mandatory_rule():
    _, result = interpret("no dietary restrictions", {"dietary": "vegetarian"}, PLACES)
    assert result.updates["dietary"] is None
    assert not result.hard_constraints


def test_common_budget_ceiling_and_evidence_ranking():
    from agents.query_constraint_agent import preference_score
    _, result = interpret("under 50k for two adults", {}, PLACES)
    assert result.facts["budget"] == 50000
    assert preference_score(["I prefer a pool"], "Pool and breakfast") > preference_score(["I prefer a pool"], "Breakfast")


def test_polite_request_does_not_make_exact_trip_details_optional():
    turn, result = interpret("I would like a relaxed 5-day holiday in Kerala", {}, PLACES)
    assert not turn.issue
    assert result.facts == {"destination": "Kerala", "duration_days": 5}
    assert result.preferences["pace"] == "relaxed"


def test_hosted_query_agent_can_be_selected_independently(connected_app, monkeypatch):
    from tests.test_application_integration import user, trip
    from agents.config import settings
    from app import journey
    monkeypatch.setattr(settings, "agent_mode", "tinyfish")
    monkeypatch.setattr(settings, "query_agent_mode", "nvidia")
    monkeypatch.setattr(journey, "get_nim_client", lambda: Model({"updates": {"destination": "Kerala"}, "reply": "Review Kerala.", "cards": []}))
    client, _ = connected_app
    headers = user(client, "query_nvidia")
    result = client.post(trip(client, headers) + "/chat", headers=headers, json={"content": "Plan Kerala"}).json()
    assert result["status"] == "ok", result
    assert result["mode"] == "nvidia"
    assert result["workspace"]["constraint_analysis"]["mode"] == "nvidia"
    assert result["workspace"]["draft"]["destination"] == "Kerala"


def test_http_agent_review_persists_and_preferences_allow_a_manual_plan(connected_app, monkeypatch):
    from tests.test_application_integration import user, trip
    from agents.config import settings
    monkeypatch.setattr(settings, "agent_mode", "offline")
    client, _ = connected_app
    headers = user(client, "constraint_demo")
    path = trip(client, headers)
    response = client.post(path + "/chat", headers=headers, json={"content":
        "Kerala, 1 December 2026 for 3 days, two adults, INR 200000 total; I prefer nature and quiet hotels"})
    assert response.status_code == 200, response.text
    work = response.json()["workspace"]
    assert not work["draft"]["hard_requirements"]
    assert work["constraint_analysis"]["soft_preferences"]
    assert work["constraint_analysis"]["facts"]["budget"] == 200000
    assert client.get(path + "/workspace", headers=headers).json()["constraint_analysis"] == work["constraint_analysis"]
    confirmed = client.post(path + "/confirm", headers=headers,
                            json={"expected_revision": work["revision"], "mode": "manual"})
    assert confirmed.status_code == 200, confirmed.text
    brief = confirmed.json()["orchestration"]["trip_brief"]
    assert brief["preferences"] and not brief["hard_constraints"]


from tests.test_application_integration import connected_app  # noqa: E402,F401
