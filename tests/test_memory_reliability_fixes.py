"""Regressions from the live-agent reliability audit, using real stores."""

# ruff: noqa: F811 -- Imported pytest fixture is resolved by parameter name.

import time

import pytest

from memory.context.compiler import compile_field
from memory.lifecycle.fuzzy import score_memory
from memory.models import EngineStorageError
from tests.test_context_service import actor, context, seed_ready
from tests.test_context_service import contexts as contexts


def submit(contexts, eid, predicate, value, *, scope=None, **extra):
    service, _ = contexts
    scope = {"trip_id": "summer"} if scope is None else scope
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id=eid,
            subject="Traveller",
            text=f"{predicate}: {value}",
            confirmed=True,
            scope=scope,
            claims=[
                dict(
                    subject="Traveller",
                    predicate=predicate,
                    value=value,
                    kind="rule",
                    scope=scope,
                    **extra,
                )
            ],
        ),
    )
    while service.process_one():
        pass
    assert service.receipt(actor(contexts, "user"), eid)["status"] == "ready"


def test_new_rule_blocks_existing_work_and_completion(contexts):
    seed_ready(contexts)
    service, _ = contexts
    packet = context(contexts)
    service.record_work(actor(contexts), "plan", packet["claim_ids"])
    owned = service.claim_work(actor(contexts), "plan")["work"]
    submit(contexts, "new-rule", "avoid_boats", True)
    assert not service.handoff(actor(contexts), ["plan"])["can_continue"]
    with pytest.raises((ValueError, EngineStorageError)):
        service.complete_work(actor(contexts), "plan", owned["lease_token"])
    assert "avoid_boats" in context(contexts)["prompt"]


def test_new_unrelated_trip_rule_keeps_work_current(contexts):
    seed_ready(contexts)
    service, _ = contexts
    service.record_work(actor(contexts), "plan", context(contexts)["claim_ids"])
    submit(contexts, "other-rule", "avoid_boats", True, scope={"trip_id": "other"})
    assert service.handoff(actor(contexts), ["plan"])["can_continue"]
    submit(contexts, "global-rule", "dietary", "vegetarian", scope={})
    assert not service.handoff(actor(contexts), ["plan"])["can_continue"]


def test_expiry_rechecks_completed_prerequisite_recursively(contexts, monkeypatch):
    seed_ready(contexts)
    service, _ = contexts
    now = int(time.time())
    submit(contexts, "access", "accessibility", "step-free", valid_until=now + 100)
    access = service.recall(
        actor(contexts),
        query="accessibility",
        subject="Traveller",
        predicate="accessibility",
        scope={"trip_id": "summer"},
    )["evidence"][0]["claim_id"]
    destination = service.recall(
        actor(contexts),
        query="destination",
        subject="Traveller",
        predicate="destination",
        scope={"trip_id": "summer"},
    )["evidence"][0]["claim_id"]
    service.record_work(actor(contexts), "parent", [access])
    lease = service.claim_work(actor(contexts), "parent")["work"]["lease_token"]
    service.complete_work(actor(contexts), "parent", lease)
    service.record_work(actor(contexts), "child", [destination], depends_on=["parent"])
    lease = service.claim_work(actor(contexts), "child")["work"]["lease_token"]
    service.complete_work(actor(contexts), "child", lease)
    service.record_work(
        actor(contexts), "grandchild", [destination], depends_on=["child"]
    )
    assert service.handoff(actor(contexts), ["grandchild"])["can_continue"]
    monkeypatch.setattr(time, "time", lambda: now + 101)
    for wid in ("parent", "child", "grandchild"):
        assert not service.handoff(actor(contexts), [wid])["can_continue"]


def test_source_events_reach_cards_and_legacy_metadata(contexts):
    seed_ready(contexts)
    service, _ = contexts
    submit(contexts, "food-source", "interests", ["food"])
    cards = context(contexts)["cards"]
    assert any("food-source" in c["source_event_ids"] for c in cards)
    answer = dict(
        answer_status="supported",
        evidence=[
            dict(
                claim_id="c",
                predicate="interests",
                value=["food"],
                accepted_for_current_use=True,
                scope={},
                valid_until=999,
                sources=[dict(metadata_json='{"service_receipt":"legacy-event"}')],
            )
        ],
    )
    assert compile_field("interests", answer)["source_event_ids"] == ["legacy-event"]


def test_work_proof_requires_complete_context_and_watches_new_session_rules(contexts):
    seed_ready(contexts)
    service, _ = contexts
    packet = context(contexts, session_id="call")
    with pytest.raises(ValueError, match="complete"):
        service.record_work(
            actor(contexts),
            "incomplete",
            packet["claim_ids"][:1],
            context_token=packet["context_token"],
        )
    service.record_work(
        actor(contexts),
        "session-plan",
        packet["claim_ids"],
        context_token=packet["context_token"],
    )
    submit(
        contexts,
        "session-rule",
        "avoid_boats",
        True,
        scope={"trip_id": "summer", "session_id": "call"},
    )
    assert not service.handoff(actor(contexts), ["session-plan"])["can_continue"]
    with pytest.raises(ValueError, match="current"):
        service.record_work(
            actor(contexts),
            "stale",
            packet["claim_ids"],
            context_token=packet["context_token"],
        )


def test_completed_work_cannot_be_reused_after_a_new_rule(contexts):
    seed_ready(contexts)
    service, _ = contexts
    service.record_work(actor(contexts), "done", context(contexts)["claim_ids"])
    lease = service.claim_work(actor(contexts), "done")["work"]["lease_token"]
    service.complete_work(actor(contexts), "done", lease)
    assert service.claim_work(actor(contexts), "done")["status"] == "already_completed"
    submit(contexts, "new-after-completion", "avoid_boats", True)
    with pytest.raises((ValueError, EngineStorageError)):
        service.claim_work(actor(contexts), "done")
    assert (
        service.handoff(actor(contexts), ["done"])["work"][0]["work"]["status"]
        == "completed"
    )


def test_future_rules_and_legacy_work_fail_closed(contexts, monkeypatch):
    seed_ready(contexts)
    service, _ = contexts
    now = int(time.time())
    submit(contexts, "later-rule", "avoid_boats", True, valid_from=now + 10)
    service.record_work(actor(contexts), "future", context(contexts)["claim_ids"])
    assert service.handoff(actor(contexts), ["future"])["can_continue"]
    monkeypatch.setattr(time, "time", lambda: now + 11)
    assert not service.handoff(actor(contexts), ["future"])["can_continue"]
    service.engine("A").graph_store.execute(
        "MATCH(w:MemoryWork {id:'future'}) SET w.requirement_watches_json=null"
    )
    packet = service.handoff(actor(contexts), ["future"])
    assert not packet["can_continue"] and "Legacy" in packet["work"][0]["warnings"][0]


@pytest.mark.parametrize(
    "days,groups,conflicts", [(30, 1, 3), (0, 1, 6), (30, 2, 4), (365, 3, 10)]
)
def test_fuzzy_quality_and_conflicts_move_in_expected_direction(
    days, groups, conflicts
):
    def score(q, n):
        return score_memory(
            age_seconds=days * 86400,
            half_life_days=90,
            source_quality=q,
            independent_groups=groups,
            conflicts=n,
        )["score"]

    qualities = [score(q / 100, conflicts) for q in range(101)]
    disagreements = [score(0.1, n) for n in range(21)]
    assert all(a <= b + 1e-12 for a, b in zip(qualities, qualities[1:]))
    assert all(a + 1e-12 >= b for a, b in zip(disagreements, disagreements[1:]))
