"""Read-only core audit: passing probes reproduce findings, not fixed behavior.

Run with pytest -p tests.conftest. Real isolated FalkorDB/embedded Qdrant;
deterministic fixture embeddings, no remote model calls in these probes.
"""

from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from examples.nvidia_memory_agents import TravelIntake, check_plan, parse_object
from memory.lifecycle.models import ClaimInput
from tests.test_context_service import contexts, actor, context, seed_ready

OUT = Path(__file__).parent / "probe-results"
FIXTURE = Path(__file__).parents[1] / "travel_agent_fixes_20261015_final/travel_fixture.json"


def record(name, **data):
    OUT.mkdir(exist_ok=True)
    (OUT / (name + ".json")).write_text(
        json.dumps(data, indent=2, allow_nan=False), encoding="utf-8"
    )


def submit(contexts, eid, claims, text="Explicit audit fixture"):
    service, _ = contexts
    service.submit(actor(contexts, "user"), dict(
        event_id=eid, subject="Traveller", text=text, confirmed=True,
        scope={"trip_id": "summer"}, claims=claims,
    ))
    while service.process_one():
        pass
    assert service.receipt(actor(contexts, "user"), eid)["status"] == "ready"


def claim(predicate, value, **extra):
    return dict(subject="Traveller", predicate=predicate, value=value,
                kind="rule", scope={"trip_id": "summer"}, **extra)


def test_new_restriction_invalidates_context_but_not_existing_work(contexts):
    seed_ready(contexts)
    service, _ = contexts
    old = context(contexts)
    assert old["status"] == "ready"
    service.record_work(actor(contexts), "boat-plan", old["claim_ids"],
                        description="An existing boat-trip plan")
    assert service.handoff(actor(contexts), ["boat-plan"])["can_continue"]
    submit(contexts, "new-no-boats", [claim("avoid_boats", True)])
    fresh = context(contexts)
    proof_valid = service.validate_context(actor(contexts), old["context_token"])["valid"]
    handoff = service.handoff(actor(contexts), ["boat-plan"])
    lease = service.claim_work(actor(contexts), "boat-plan")["work"]["lease_token"]
    completion = service.complete_work(actor(contexts), "boat-plan", lease)
    record("new-restriction", old_proof_valid=proof_valid,
           new_rule_in_fresh_context="avoid_boats" in fresh["prompt"], handoff=handoff,
           completed_after_new_restriction=completion["status"])
    assert not proof_valid and "avoid_boats" in fresh["prompt"]
    assert handoff["can_continue"]  # Finding: new requirement not an old USES edge.
    assert completion["status"] == "completed"


def test_expired_completed_prerequisite_not_revalidated(contexts, monkeypatch):
    seed_ready(contexts)
    service, _ = contexts
    now = int(time.time())
    submit(contexts, "expiring-field", [claim("audit_access", "step-free", valid_until=now + 100)])
    source = service.recall(actor(contexts), query="Audit access?", subject="Traveller", predicate="audit_access",
                            scope={"trip_id": "summer"})
    cid = source["evidence"][0]["claim_id"]
    other = service.recall(actor(contexts), query="Destination?", subject="Traveller", predicate="destination",
                           scope={"trip_id": "summer"})["evidence"][0]["claim_id"]
    service.record_work(actor(contexts), "access-check", [cid])
    lease = service.claim_work(actor(contexts), "access-check")["work"]["lease_token"]
    service.complete_work(actor(contexts), "access-check", lease)
    service.record_work(actor(contexts), "dependent-plan", [other], depends_on=["access-check"])
    assert service.handoff(actor(contexts), ["dependent-plan"])["can_continue"]
    monkeypatch.setattr(time, "time", lambda: now + 101)
    expired = service.handoff(actor(contexts), ["access-check"])
    dependent = service.handoff(actor(contexts), ["dependent-plan"])
    record("expired-prerequisite", as_of=now + 101,
           prerequisite=expired, dependent=dependent)
    assert not expired["can_continue"]
    assert dependent["can_continue"]  # Finding: status checked, evidence not recursed.


class FakeModel:
    def __init__(self, claims):
        self.claims = claims

    def json(self, *args, **kwargs):
        return {"claims": deepcopy(self.claims)}


def intake(text, fields):
    adapter = TravelIntake(FakeModel([
        dict(predicate=k, value=v, action="supersede", reason="User requests change")
        for k, v in fields.items()
    ]))
    result = adapter(text, {"subject": "Traveller", "scope": {"trip_id": "summer"}})
    for value in result:
        ClaimInput.model_validate(value)
    return result


@pytest.mark.parametrize("name,text,fields,expected", [
    ("polite-change", "Please change my budget to INR 65000.", {"budget": 65000}, {"budget": "assert"}),
    ("two-changes", "Change my budget to INR 65000 and walking limit to 50 metres.",
     {"budget": 65000, "max_walk_metres": 50}, {"budget": "supersede", "max_walk_metres": "assert"}),
    ("diet-change", "Change my dietary requirement to vegan.", {"dietary": "vegan"}, {"dietary": "assert"}),
])
def test_valid_changes_downgraded(name, text, fields, expected):
    result = intake(text, fields)
    actions = {c["predicate"]: c["action"] for c in result}
    record(name, input=text, output=result, observed_actions=actions)
    assert actions == expected


@pytest.mark.parametrize("predicate,value", [
    ("traveller_count", 1.5), ("traveller_count", -2),
    ("max_activities_per_day", 0.5), ("max_walk_metres", -50),
    ("budget", -65000), ("destination", ["Goa", "Delhi"]),
    ("interests", "food"), ("dates", "not a date"),
])
def test_domain_invalid_values_accepted(predicate, value):
    result = intake("Explicit test source", {predicate: value})
    record("invalid-" + predicate + "-" + str(value).replace("/", "_"), output=result)
    assert result[0]["value"] == value


def test_empty_required_value_silently_dropped():
    result = intake("Budget unclear, destination Goa", {"budget": "", "destination": "Goa"})
    record("partial-extraction", output=result)
    assert len(result) == 1 and result[0]["predicate"] == "destination"


def test_extraction_can_lock_in_unsupported_value(contexts):
    service, _ = contexts
    service.interpreter = TravelIntake(FakeModel([
        dict(predicate="budget", value=90000, action="assert", reason="")
    ]))
    service.submit(actor(contexts, "user"), dict(event_id="wrong-number", subject="Traveller",
        text="My total budget is INR 65000.", confirmed=True, scope={"trip_id": "summer"}))
    while service.process_one():
        pass
    result = service.recall(actor(contexts), query="Budget?", subject="Traveller", predicate="budget",
                            scope={"trip_id": "summer"})
    record("extraction-grounding", input="My total budget is INR 65000.", recall=result)
    assert result["evidence"][0]["value"] == 90000
    assert result["evidence"][0]["protected"]
    assert result["evidence"][0]["fuzzy_score"] == 1


def test_polite_change_blocks_context_instead_of_applying_replacement(contexts):
    seed_ready(contexts)
    service, _ = contexts
    service.interpreter = TravelIntake(FakeModel([
        dict(predicate="budget", value=65000, action="supersede", reason="Explicit change")
    ]))
    service.submit(actor(contexts, "user"), dict(event_id="polite-update", subject="Traveller",
        text="Please change my budget to INR 65000.", confirmed=True, scope={"trip_id":"summer"}))
    while service.process_one():
        pass
    packet = context(contexts)
    record("polite-change-integration", status=packet["status"], issues=packet["required_issues"])
    assert packet["status"] == "needs_information"
    assert packet["required_issues"]["budget"] == "disputed"


def test_fuzzy_more_conflicts_can_increase_score():
    from memory.lifecycle.fuzzy import score_memory
    values = [score_memory(age_seconds=30*86400, half_life_days=90,
        source_quality=0.1, independent_groups=2, conflicts=n)["score"] for n in (4, 5)]
    record("fuzzy-conflict-reversal", conflicts=[4, 5], scores=values)
    assert values[1] > values[0]


def good_plan():
    return dict(decision="plan", flight_id="F-AM-SAVER", hotel_id="H-GARDEN",
        activity_ids=["A-ACCESSIBLE-BEACH", "A-TERRACE"],
        activity_days={"A-ACCESSIBLE-BEACH": "2026-12-10", "A-TERRACE": "2026-12-11"},
        total_inr=58600, budget_inr=65000, max_walk_metres=500)


@pytest.mark.parametrize("name,patch", [
    ("invalid-decision", {"decision": "banana"}),
    ("impossible-date", {"activity_days": {"A-ACCESSIBLE-BEACH": "2026-12-110", "A-TERRACE": "2026-12-11"}}),
])
def test_oracle_accepts_invalid_candidate(name, patch):
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline = check_plan(good_plan(), fixture, budget=65000, walking=500)
    assert all(baseline.values())
    plan = dict(good_plan(), **patch)
    result = check_plan(plan, fixture, budget=65000, walking=500)
    record(name, plan=plan, oracle=result)
    assert all(result.values())


def test_pause_with_activities_and_cost_passes_oracle():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    plan = dict(decision="pause", flight_id=None, hotel_id=None, activity_ids=["A-CRUISE"],
                total_inr=999999, budget_inr=65000, max_walk_metres=50)
    result = check_plan(plan, fixture, budget=65000, walking=50)
    record("pause-with-bookings", plan=plan, oracle=result)
    assert all(result.values())


def test_pause_for_unaffordable_trip_false_negative():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    plan = dict(decision="pause", flight_id=None, hotel_id=None, activity_ids=[],
                total_inr=None, budget_inr=100, max_walk_metres=500)
    result = check_plan(plan, fixture, budget=100, walking=500)
    record("affordability-pause", plan=plan, oracle=result,
           cheapest_flight=min(f["total_for_two"] for f in fixture["flight_offers"]))
    assert not result["correct_pause"]


def test_nonfinite_json_parsed_but_core_rejects():
    parsed = parse_object('{"budget":NaN}')
    assert parsed["budget"] != parsed["budget"]
    with pytest.raises(ValueError):
        ClaimInput(subject="Traveller", predicate="budget", value=parsed["budget"])
    record("nonfinite-json", adapter_parser_accepts=True, core_rejects=True)


def test_actual_source_id_missing_from_compiled_metadata(contexts):
    seed_ready(contexts)
    service, _ = contexts
    submit(contexts, "interest-source", [dict(claim("interests", ["food"]), kind="preference")])
    packet = context(contexts)
    sources = service.recall(actor(contexts), query="Interests?", subject="Traveller", predicate="interests",
                             scope={"trip_id": "summer"})["evidence"][0]["sources"]
    cards = [c for c in packet["cards"] if "interests" in c["statuses"]]
    record("source-provenance", source=sources, cards=cards)
    assert sources and cards
    assert all(not c["source_event_ids"] for c in cards)
    assert any("interest-source" in s["metadata_json"] for s in sources)
