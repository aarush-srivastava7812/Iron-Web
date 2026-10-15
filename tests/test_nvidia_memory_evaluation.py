"""Check evaluator plumbing before spending remote tokens; no API credentials."""

import json
from pathlib import Path
import pytest

from examples.nvidia_memory_agents import (
    parse_object,
    check_plan,
    TravelIntake,
    offer_catalog,
)


def fixture():
    return json.loads(
        (
            Path(__file__).parents[1] / "examples/fixtures/travel_catalog.json"
        ).read_text()
    )


def test_model_json_is_not_silently_repaired_or_guessed():
    assert parse_object('```json\n{"ok":true}\n```') == {"ok": True}
    for raw in ["[]", "not JSON", '{"ok":true} trailing text']:
        with pytest.raises(ValueError):
            parse_object(raw)


def test_agent_catalog_excludes_expected_answers_and_future_user_changes():
    catalog = offer_catalog(fixture())
    assert set(catalog) == {
        "quote_terms",
        "flight_offers",
        "hotel_offers",
        "activity_offers",
        "fixed_costs",
    }
    assert (
        "initial_total_budget" not in catalog and "revised_total_budget" not in catalog
    )
    assert "requirements" not in catalog


def test_oracle_distinguishes_good_stale_and_inaccessible_plans():
    plan = dict(
        decision="plan",
        flight_id="F-AM-SAVER",
        hotel_id="H-GARDEN",
        activity_ids=["A-ACCESSIBLE-BEACH", "A-TERRACE"],
        total_inr=58600,
        activity_days={"A-ACCESSIBLE-BEACH": "2026-12-11", "A-TERRACE": "2026-12-12"},
        budget_inr=65000,
        max_walk_metres=500,
    )

    assert all(check_plan(plan, fixture(), budget=65000, walking=500).values())
    arrival_day = dict(
        plan,
        activity_days={"A-ACCESSIBLE-BEACH": "2026-12-10", "A-TERRACE": "2026-12-11"},
    )
    assert check_plan(arrival_day, fixture(), budget=65000, walking=500)[
        "one_activity_per_day"
    ]
    same_day = dict(
        plan,
        activity_days={"A-ACCESSIBLE-BEACH": "2026-12-11", "A-TERRACE": "2026-12-11"},
    )
    assert not check_plan(same_day, fixture(), budget=65000, walking=500)[
        "one_activity_per_day"
    ]
    assert not all(
        check_plan(
            dict(plan, budget_inr=90000), fixture(), budget=65000, walking=500
        ).values()
    )
    assert not check_plan(plan, fixture(), budget=65000, walking=50)["hotel_walking"]
    assert all(
        check_plan(
            dict(
                decision="pause",
                flight_id=None,
                hotel_id=None,
                budget_inr=65000,
                max_walk_metres=50,
                activity_ids=[],
                activity_days={},
                total_inr=None,
            ),
            fixture(),
            budget=65000,
            walking=50,
        ).values()
    )


def test_intake_does_not_invent_a_change_when_source_only_asserts_a_preference():
    class FakeModel:
        def json(self, *args, **kwargs):
            return {
                "claims": [
                    dict(
                        predicate="hotel_preference",
                        value="resort",
                        action="supersede",
                        reason="preferred",
                        source_quote="Prefer a resort when budget permits.",
                    )
                ]
            }

    parsed = TravelIntake(FakeModel())(
        "Prefer a resort when budget permits.",
        dict(subject="Riya", scope={"trip_id": "goa"}),
    )
    assert parsed[0]["action"] == "assert"


def test_intake_canonicalization_preserves_preference_and_requirement_strength():
    class FakeModel:
        def json(self, *args, **kwargs):
            source = args[1][1]["content"]
            return {
                "claims": [
                    dict(
                        predicate="dietary",
                        value="Vegetarian",
                        action="assert",
                        reason="",
                        source_quote=source,
                    ),
                ]
            }

    intake = TravelIntake(FakeModel())
    claims = intake("Usually I prefer vegetarian food.", dict(subject="Riya", scope={}))
    assert (
        len(claims) == 1
        and claims[0]["kind"] == "preference"
        and claims[0]["value"] == "vegetarian"
    )
    assert intake.normalizations[0]["changes"][0]["grounded"]
    claims = intake(
        "Vegetarian food is mandatory.", dict(subject="Riya", scope={"trip_id": "goa"})
    )
    assert claims[0]["kind"] == "rule"
    assert (
        intake("Vegetarian food is mandatory.", dict(subject="Riya", scope={}))[0][
            "kind"
        ]
        == "rule"
    )
