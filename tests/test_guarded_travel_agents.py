"""Business acceptance, independent expected totals, and lifecycle integration."""

# ruff: noqa: F811 -- Imported pytest fixture is resolved by parameter name.

from copy import deepcopy

import pytest

from examples.nvidia_memory_agents import TravelAgent, check_plan
from examples.travel_planning import canonical_plan, requirements_from_context
from memory.context.contracts import AgentProfile
from memory.context.runtime import ContextRuntime
from tests.test_context_service import actor
from tests.test_context_service import contexts as contexts
from tests.test_nvidia_memory_evaluation import fixture


def good_plan():
    return dict(
        decision="plan",
        flight_id="F-AM-SAVER",
        hotel_id="H-GARDEN",
        activity_ids=["A-ACCESSIBLE-BEACH", "A-TERRACE"],
        activity_days={"A-ACCESSIBLE-BEACH": "2026-12-10", "A-TERRACE": "2026-12-11"},
        total_inr=58600,
        budget_inr=65000,
        max_walk_metres=500,
        reasons=[],
        evidence_claim_ids=[],
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"decision": "banana"},
        {
            "activity_days": {
                "A-ACCESSIBLE-BEACH": "2026-12-110",
                "A-TERRACE": "2026-12-11",
            }
        },
        {
            "activity_days": {
                "A-ACCESSIBLE-BEACH": "2026-02-30",
                "A-TERRACE": "2026-12-11",
            }
        },
        {"total_inr": float("nan")},
        {"budget_inr": True},
        {"activity_ids": [{}]},
        {"activity_ids": ["A-TERRACE", "A-TERRACE"]},
        {"flight_id": []},
        {"unexpected": "override"},
        {"total_inr": 58601},
    ],
)
def test_checker_rejects_malformed_or_wrong_plans(patch):
    assert not all(
        check_plan(
            dict(good_plan(), **patch), fixture(), budget=65000, walking=500
        ).values()
    )


def test_pause_checks_affordability_and_requires_empty_selection():
    pause = dict(
        decision="pause",
        flight_id=None,
        hotel_id=None,
        activity_ids=[],
        activity_days={},
        total_inr=None,
        budget_inr=100,
        max_walk_metres=500,
    )
    assert all(check_plan(pause, fixture(), budget=100, walking=500).values())
    assert not all(
        check_plan(
            dict(pause, activity_ids=["A-CRUISE"], total_inr=999999),
            fixture(),
            budget=100,
            walking=500,
        ).values()
    )


def test_return_flight_and_dynamic_calendar_dates_are_checked():
    quotes = fixture()
    quotes["flight_offers"][1]["return_departure"] = "22:00"
    assert not check_plan(good_plan(), quotes, budget=65000, walking=500)["morning"]
    quotes = fixture()
    quotes["quote_terms"]["dates"] = "2027-01-10 to 2027-01-14"
    p = dict(
        good_plan(),
        activity_days={"A-ACCESSIBLE-BEACH": "2027-01-10", "A-TERRACE": "2027-01-11"},
    )
    assert all(check_plan(p, quotes, budget=65000, walking=500).values())


def test_food_activity_requires_explicit_dietary_evidence():
    quotes = fixture()
    quotes["activity_offers"][1]["vegetarian_food"] = False
    assert not check_plan(good_plan(), quotes, budget=65000, walking=500)["vegetarian"]
    del quotes["activity_offers"][1]["vegetarian_food"]
    assert not all(check_plan(good_plan(), quotes, budget=65000, walking=500).values())


class LocalClient:
    def __init__(self, service, principal):
        self.service, self.principal = service, principal

    def context(self, **request):
        return self.service.context(self.principal, **request)

    def validate_context(self, token):
        return self.service.validate_context(self.principal, token)

    def call(self, path, **body):
        fn = {
            "/v1/work": self.service.record_work,
            "/v1/work/claim": self.service.claim_work,
            "/v1/work/complete": self.service.complete_work,
        }[path]
        return fn(self.principal, **body)


class BadModel:
    def json(self, *args, **kwargs):
        return dict(good_plan(), total_inr=79000, budget_inr=90000)


@pytest.fixture
def travel(contexts):
    service, _ = contexts
    old = service.context_access.runtime
    service.context_access.runtime = ContextRuntime(
        profiles=list(old.profiles.values())
        + [AgentProfile(actor_id="reviewer", version="1", instructions="Check trips.")],
        tokens=old.tokens,
        policy=old.policy,
    )
    values = dict(
        destination="Goa",
        dates="2026-12-10 to 2026-12-14",
        budget=90000,
        currency="INR",
        departure_city="Delhi",
        traveller_count=2,
        accessibility="step-free",
        dietary="vegetarian",
        max_walk_metres=500,
        avoid_boats=True,
        max_activities_per_day=1,
        flight_time_preference="morning",
    )
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="trip",
            subject="Traveller",
            text="Explicit structured trip fields",
            scope={"trip_id": "summer"},
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate=p,
                    value=v,
                    kind="fact"
                    if p in {"destination", "dates", "currency", "departure_city"}
                    else "rule",
                    scope={"trip_id": "summer"},
                )
                for p, v in values.items()
            ],
        ),
    )
    while service.process_one():
        pass
    request = dict(
        subject="Traveller", scope={"trip_id": "summer"}, task_type="itinerary"
    )
    agents = {
        role: TravelAgent(role, LocalClient(service, actor(contexts, role)), BadModel())
        for role in ("planner", "reviewer")
    }
    return service, contexts, request, agents


def test_bad_model_outputs_are_replaced_by_explicit_checked_results(travel):
    service, contexts, request, agents = travel
    plan = agents["planner"].respond("plan", request, fixture())
    assert (
        plan["status"] == "ready"
        and plan["decision_source"] == "deterministic_catalog_solver"
    )
    assert plan["model_output"]["total_inr"] == 79000
    assert plan["output"]["total_inr"] == 72600
    review = agents["reviewer"].respond("review", request, fixture(), plan["output"])
    assert review["output"]["decision"] == "approve"
    assert review["decision_source"] == "deterministic_constraint_review"
    result = agents["planner"].complete_reviewed(
        plan, agents["reviewer"], review, fixture(), "accepted"
    )
    assert result["status"] == "completed"
    retry = agents["planner"].complete_reviewed(
        plan, agents["reviewer"], review, fixture(), "accepted"
    )
    assert retry["status"] == "completed" and retry["already_completed"]


@pytest.mark.parametrize(
    "budget,walking,expected",
    [(65000, 500, 64600), (100, 500, None), (90000, 50, None), (100000, 90, 72000)],
)
def test_solver_totals_and_infeasibility_controls(travel, budget, walking, expected):
    _, _, request, agents = travel
    packet = agents["planner"].memory.context(**request)
    req = requirements_from_context(packet, fixture())
    req.update(budget=budget, max_walk_metres=walking)
    plan, _, _ = canonical_plan(fixture(), req, packet["claim_ids"])
    # Expected totals are manually computed independently of the checker.
    assert plan["total_inr"] == expected
    assert plan["decision"] == ("plan" if expected is not None else "pause")


def test_model_error_is_reported_and_does_not_bypass_program_checks(travel):
    _, _, request, agents = travel

    def fail(*args, **kwargs):
        raise ValueError("truncated")

    agents["planner"].model.json = fail
    result = agents["planner"].respond("bad-json", request, fixture())
    assert result["model_error_type"] == "ValueError"
    assert result["output"]["total_inr"] == 72600


def test_unknown_mandatory_requirement_stops_for_review(travel):
    service, contexts, request, agents = travel
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="unsupported",
            subject="Traveller",
            text="Need a ramp vehicle",
            confirmed=True,
            scope={"trip_id": "summer"},
            claims=[
                dict(
                    subject="Traveller",
                    predicate="ramp_vehicle",
                    value=True,
                    kind="rule",
                    scope={"trip_id": "summer"},
                )
            ],
        ),
    )
    while service.process_one():
        pass
    result = agents["planner"].respond("unsupported", request, fixture())
    assert result["status"] == "needs_review" and result["output"] is None


def test_changed_plan_or_stale_context_cannot_be_completed(travel):
    service, contexts, request, agents = travel
    plan = agents["planner"].respond("p", request, fixture())
    review = agents["reviewer"].respond("r", request, fixture(), plan["output"])
    altered = deepcopy(plan)
    altered["output"]["total_inr"] += 1
    with pytest.raises(ValueError, match="exact plan"):
        agents["planner"].complete_reviewed(
            altered, agents["reviewer"], review, fixture(), "bad"
        )
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="new",
            subject="Traveller",
            text="New rule",
            confirmed=True,
            scope={"trip_id": "summer"},
            claims=[
                dict(
                    subject="Traveller",
                    predicate="no_transfers",
                    value=True,
                    kind="rule",
                    scope={"trip_id": "summer"},
                )
            ],
        ),
    )
    while service.process_one():
        pass
    with pytest.raises(ValueError, match="Memory changed"):
        agents["planner"].complete_reviewed(
            plan, agents["reviewer"], review, fixture(), "stale"
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("currency", "USD"),
        ("traveller_count", 3),
        ("dates", "2027-01-10 to 2027-01-14"),
    ],
)
def test_quote_terms_cannot_be_reused_for_another_trip_or_party(travel, field, value):
    _, _, request, agents = travel
    packet = deepcopy(agents["planner"].memory.context(**request))
    next(f for f in packet["fields"] if f["predicate"] == field)["values"] = [value]
    with pytest.raises(ValueError):
        requirements_from_context(packet, fixture())


def test_change_during_model_generation_discards_the_answer(travel):
    service, contexts, request, agents = travel

    def changing_model(*args, **kwargs):
        service.submit(
            actor(contexts, "user"),
            dict(
                event_id="during-generation",
                subject="Traveller",
                text="New rule",
                confirmed=True,
                scope={"trip_id": "summer"},
                claims=[
                    dict(
                        subject="Traveller",
                        predicate="new_limit",
                        value=True,
                        kind="rule",
                        scope={"trip_id": "summer"},
                    )
                ],
            ),
        )
        while service.process_one():
            pass
        return good_plan()

    agents["planner"].model.json = changing_model
    result = agents["planner"].respond("race", request, fixture())
    assert result["status"] == "context_changed" and result["output"] is None
