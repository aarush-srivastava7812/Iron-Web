"""Real FalkorDB/Qdrant tests for memory evolution, evidence and handoffs."""

import time
import pytest

# Retained pre-migration engine contracts; native application checks live in main.py.
from memory.engine import LegacyMemoryEngine as MemoryEngine
from memory.models import EngineStorageError
from memory.tool_adapter import MemoryToolAdapter


@pytest.fixture
def engine(tmp_path):
    value = MemoryEngine(
        config={"extraction_policy": "none"}, qdrant_path=str(tmp_path / "vectors")
    )
    yield value
    value.close()


def add(
    engine,
    mid,
    value,
    *,
    predicate="budget",
    subject="North",
    at=100,
    kind="fact",
    action="assert",
    scope=None,
    origin="user",
    confirmed=True,
    reason="",
    claims=None,
    actor="north",
    **kwargs,
):
    claim = dict(
        subject=subject,
        predicate=predicate,
        value=value,
        kind=kind,
        action=action,
        scope=scope or {},
        reason=reason,
        **kwargs,
    )
    return engine.add(
        f"{subject} {predicate}: {value}",
        memory_id=mid,
        timestamp=at,
        claims=claims or [claim],
        source_info=dict(
            origin=origin,
            actor_id=actor,
            user_confirmed=confirmed,
            recorded_at=at,
            quality=0.9,
        ),
    )


def cid(engine, mid, index=0):
    return engine.get(mid).metadata["memory_claim_ids"][index]


def test_ordinary_decay_is_explainable_and_protection_is_separate(engine):
    add(engine, "ordinary", 600)
    claim = cid(engine, "ordinary")
    scores = [
        engine.inspect_claim(claim, 100 + days * 86400)["fuzzy_score"]
        for days in [0, 1, 7, 30, 90, 365]
    ]
    assert 0 < scores[0] <= 0.99 and all(a > b for a, b in zip(scores, scores[1:]))
    view = engine.inspect_claim(claim, 100)
    assert view["fuzzy_explanation"]["fired_rules"]
    assert view["fuzzy_explanation"]["memberships"]
    add(engine, "rule", "Do not exceed 600", predicate="budget_rule", kind="rule")
    protected = cid(engine, "rule")
    assert engine.inspect_claim(protected, 100 + 1000 * 86400)["fuzzy_score"] == 1
    assert not engine.inspect_claim(claim, 100)["protected"]


def test_accepted_change_retains_both_and_transfers_protection(engine):
    add(engine, "old", "1000", kind="instruction")
    old = cid(engine, "old")
    add(
        engine,
        "new",
        "600",
        kind="instruction",
        at=200,
        action="supersede",
        reason="User lowered the limit",
    )
    new = cid(engine, "new")
    assert engine.get("old").content == "North budget: 1000"
    assert engine.inspect_claim(old, 250)["fuzzy_score"] == 0
    assert engine.inspect_claim(old, 250)["previous_score"] == 1
    assert engine.inspect_claim(new, 250)["fuzzy_score"] == 1
    assert engine.inspect_claim(old, 150)["fuzzy_score"] == 1
    assert (
        engine.recall("Current budget", "North", query_time=250)["evidence"][0]["value"]
        == "600"
    )
    graph = engine.graph_store
    assert graph.execute(
        "MATCH(a:MemoryClaim)-[:SUPERSEDES]->(b:MemoryClaim) RETURN a.id,b.id"
    ).rows == [[new, old]]
    assert graph.execute(
        "MATCH(c:MemoryClaim {id:$id}) RETURN c.score_at_creation", {"id": new}
    ).rows == [[1.0]]
    assert (
        graph.execute(
            "MATCH(a:MemoryClaim)-[:CONTRADICTS]->(b:MemoryClaim) RETURN count(*)"
        ).rows[0][0]
        == 0
    )


def test_retraction_retains_history_without_an_invented_replacement_value(engine):
    add(engine, "approved", 1000, kind="rule")
    old = cid(engine, "approved")
    engine.record_work("plan", [old])
    add(
        engine,
        "withdrawn",
        None,
        kind="rule",
        action="retract",
        at=200,
        targets=[old],
        reason="User withdrew this requirement without a replacement",
    )
    assert (
        engine.recall("budget", "North", query_time=250)["answer_status"] == "missing"
    )
    view = engine.inspect_claim(old, 250)
    assert (
        view["status"] == "retracted"
        and view["fuzzy_score"] == 0
        and view["previous_score"] == 1
    )
    assert (
        view["change_reason"] == "User withdrew this requirement without a replacement"
    )
    assert engine.get("approved").content == "North budget: 1000"
    assert not engine.handoff(["plan"])["can_continue"]
    assert engine.graph_store.execute(
        "MATCH(c:MemoryClaim)-[:RETRACTS]->(old:MemoryClaim) RETURN count(*)"
    ).rows == [[1]]


def test_repeated_agent_disagreement_is_not_independent_negative_evidence(engine):
    add(engine, "fact", 600, at=100)
    add(engine, "first_guess", 900, at=200, origin="agent", confirmed=False)
    before = engine.inspect_claim(cid(engine, "fact"), 300)["fuzzy_score"]
    add(engine, "repeated_guess", 900, at=250, origin="agent", confirmed=False)
    after = engine.inspect_claim(cid(engine, "fact"), 300)
    assert after["fuzzy_score"] == before
    assert after["status"] == "disputed"


def test_unaccepted_conflict_preserves_protected_value_and_stops_answer(engine):
    add(engine, "old", 1000, kind="rule")
    add(
        engine,
        "proposal",
        600,
        at=200,
        kind="rule",
        origin="agent",
        confirmed=False,
        actor="planner",
    )
    packet = engine.recall("Current budget", "North", query_time=250)
    assert packet["answer_status"] == "disputed" and len(packet["evidence"]) == 2
    assert engine.inspect_claim(cid(engine, "old"), 250)["fuzzy_score"] == 1
    assert engine.inspect_claim(cid(engine, "proposal"), 250)["fuzzy_score"] < 1
    assert not engine.inspect_claim(cid(engine, "proposal"), 250)["accepted"]


def test_scope_and_partial_confirmation_do_not_refresh_other_fields(engine):
    add(
        engine,
        "profile",
        None,
        claims=[
            dict(subject="North", predicate="discipline", value="AI & Data Science"),
            dict(subject="North", predicate="study_year", value=3),
        ],
    )
    year = cid(engine, "profile", 1)
    before = engine.inspect_claim(year, 200)["fuzzy_score"]
    add(
        engine,
        "confirm",
        "AI & Data Science",
        predicate="discipline",
        at=200,
        action="confirm",
    )
    assert engine.inspect_claim(year, 200)["fuzzy_score"] == before
    add(engine, "general", 1000)
    add(engine, "trip", 600, scope={"trip_id": "A"}, at=200)
    assert (
        engine.recall("budget", "North", query_time=250)["evidence"][0]["value"] == 1000
    )
    assert (
        engine.recall("budget", "North", scope={"trip_id": "A"}, query_time=250)[
            "evidence"
        ][0]["value"]
        == 600
    )
    assert (
        engine.recall("budget", "North", scope={"trip_id": "B"}, query_time=250)[
            "answer_status"
        ]
        == "missing"
    )


def test_event_retries_do_not_duplicate_or_manufacture_independent_support(engine):
    add(engine, "one", 600)
    count = engine.vector_store.count()
    add(engine, "one", 600)
    assert engine.vector_store.count() == count
    add(engine, "same_author", 600, at=200, action="confirm")
    view = engine.inspect_claim(cid(engine, "same_author"), 250)
    assert view["fuzzy_explanation"]["inputs"]["support"] == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="immutable|different"):
        add(engine, "one", 700)


def test_missing_field_does_not_become_an_answer(engine):
    add(engine, "name", "North", predicate="preferred_name")
    packet = engine.recall("What is North's phone number?", "North", query_time=200)
    assert packet["answer_status"] == "missing" and packet["evidence"] == []
    packet = engine.recall("Tell me something about North", "North", query_time=200)
    assert packet["answer_status"] == "unresolved_question"


def test_alias_and_explicit_two_step_evidence_path(engine):
    add(
        engine,
        "employer",
        "Inditech Systems",
        predicate="employer",
        references=["Inditech Systems"],
    )
    add(
        engine,
        "location",
        "Pune",
        predicate="location",
        subject="Inditech Electrosystems",
    )
    add(
        engine,
        "alias",
        "Inditech Electrosystems",
        predicate="same_as",
        subject="Inditech Systems",
        action="alias",
        at=200,
    )
    packet = engine.recall_path(
        "Where is North's employer located?",
        "North",
        ["employer", "location"],
        query_time=250,
    )
    assert (
        packet["answer_status"] == "supported"
        and packet["evidence"][0]["value"] == "Pune"
    )
    assert len(packet["steps"]) == 2
    assert (
        engine.recall(
            "location", "Inditech Systems", predicate="location", query_time=250
        )["evidence"][0]["value"]
        == "Pune"
    )
    with pytest.raises(EngineStorageError):
        add(
            engine,
            "cycle",
            "Inditech Systems",
            predicate="same_as",
            subject="Inditech Electrosystems",
            action="alias",
            at=300,
        )
    assert engine.get("cycle") is None


@pytest.mark.parametrize("mode", ["vector", "hybrid", "graph", "hybrid_no_graph"])
def test_search_reconciles_old_vector_hits_with_current_claims(engine, mode):
    add(engine, "old", 1000, kind="rule")
    add(
        engine,
        "new",
        600,
        kind="rule",
        at=200,
        action="supersede",
        reason="Accepted update",
    )
    hits = engine.search("North budget 1000", k=5, query_time=250, retrieval_mode=mode)
    assert hits and all("1000" not in h.content for h in hits)
    assert any(h.memory_id == "new" and "600" in h.content for h in hits)
    assert all(h.metadata.get("memory_evidence") for h in hits)
    scoped = engine.search(
        "North budget", k=5, query_time=250, retrieval_mode=mode, document_ids=["old"]
    )
    assert scoped == []
    historical = engine.search(
        "North earlier budget",
        k=5,
        query_time=250,
        retrieval_mode=mode,
        temporal_mode="historical",
    )
    assert any(h.memory_id == "old" for h in historical)
    assert not any(h.memory_id == "new" for h in historical)


def test_correction_history_is_not_falsely_reported_as_past_truth(engine):
    add(engine, "wrong", 3, predicate="study_year")
    add(
        engine,
        "right",
        2,
        predicate="study_year",
        at=200,
        action="correct",
        reason="Previous year was mistaken",
    )
    graph = engine.graph_store
    assert (
        graph.execute(
            "MATCH(a:MemoryClaim)-[:CONTRADICTS]->(b:MemoryClaim) RETURN count(*)"
        ).rows[0][0]
        == 1
    )
    assert (
        graph.execute(
            "MATCH(a:MemoryClaim)-[:SUPERSEDES]->(b:MemoryClaim) RETURN count(*)"
        ).rows[0][0]
        == 1
    )
    old = engine.recall(
        "year",
        "North",
        predicate="study_year",
        query_time=250,
        temporal_mode="historical",
    )
    assert old["answer_status"] == "historical_assertion"
    assert old["evidence"][0]["status"] == "corrected"


def test_only_affected_work_becomes_stale_and_handoff_carries_versions(engine):
    now = int(time.time())
    add(engine, "budget", 1000, at=now - 10, kind="rule")
    add(engine, "name", "North", predicate="preferred_name", at=now - 10)
    engine.record_work(
        "plan", [cid(engine, "budget")], description="Plan based on the old budget"
    )
    engine.record_work("booking", [cid(engine, "budget")], depends_on=["plan"])
    engine.record_work("greeting", [cid(engine, "name")])
    add(
        engine,
        "updated",
        600,
        at=now - 1,
        kind="rule",
        action="supersede",
        reason="User changed budget",
    )
    packet = engine.handoff(["plan", "booking", "greeting"])
    assert not packet["can_continue"]
    assert [w["work"]["status"] for w in packet["work"]] == ["stale", "stale", "ready"]
    assert packet["work"][0]["current_evidence"][0]["value"] == 600
    assert packet["work"][0]["used_versions"][0]["value"] == 1000


def test_invalid_authority_and_failed_graph_write_leave_stores_unchanged(
    engine, monkeypatch
):
    with pytest.raises(ValueError):
        add(engine, "forged", 600, origin="agent", confirmed=True)
    assert engine.vector_store.count() == 0
    add(engine, "old", 1000, kind="rule")
    original = engine.inspect_claim(cid(engine, "old"), 250)

    def fail(*args, **kwargs):
        raise RuntimeError("Injected post-claim failure")

    monkeypatch.setattr(engine.lifecycle, "invalidate_work", fail)
    with pytest.raises(EngineStorageError):
        add(
            engine,
            "new",
            600,
            kind="rule",
            at=200,
            action="correct",
            reason="User correction",
        )
    assert engine.get("new") is None
    assert engine.inspect_claim(cid(engine, "old"), 250) == original


def test_typed_sources_cannot_be_overwritten_merged_or_silently_deleted(engine):
    add(engine, "one", 600)
    add(engine, "two", 600)
    with pytest.raises(ValueError):
        engine.update("one", content="changed")
    with pytest.raises(ValueError):
        engine.add("changed", memory_id="one")
    with pytest.raises(ValueError):
        engine.delete("one")
    result = engine.deduplicate_memories(dry_run=False)
    assert result["merged"] == 0
    assert engine.get("one") and engine.get("two")
    assert engine.delete("one", user_confirmed=True)
    assert engine.lifecycle.claim(cid(engine, "two")) is not None


def test_original_source_and_score_explanation_survive_reopening(engine, tmp_path):
    add(engine, "saved", 600, kind="rule")
    claim = cid(engine, "saved")
    name = engine.graph_store.graph_name
    engine.close()
    reopened = MemoryEngine(
        config={"extraction_policy": "none"},
        qdrant_path=str(tmp_path / "vectors"),
        graph_name=name,
    )
    try:
        assert reopened.get("saved").content == "North budget: 600"
        assert reopened.inspect_claim(claim, 200)["fuzzy_score"] == 1
    finally:
        reopened.close()


def test_source_only_ingestion_records_episode_without_inventing_facts(engine):
    engine.add(
        "An agent proposed a possible trip.",
        memory_id="episode",
        source_info={"origin": "agent", "actor_id": "planner", "recorded_at": 100},
    )
    view = engine.inspect_claim(cid(engine, "episode"), 200)
    assert (
        view["kind"] == "episode"
        and view["value"] == "An agent proposed a possible trip."
    )
    assert engine.get("episode").metadata["memory_type"] == "episodic"


def test_known_time_does_not_use_a_correction_that_was_not_yet_known(engine):
    add(engine, "old", 1000, kind="rule", at=100)
    add(
        engine,
        "new",
        600,
        kind="rule",
        at=200,
        action="supersede",
        reason="Accepted later change",
    )
    then = engine.recall("budget", "North", query_time=250, known_at=150)
    assert then["answer_status"] == "supported" and then["evidence"][0]["value"] == 1000
    now = engine.recall("budget", "North", query_time=250, known_at=250)
    assert now["evidence"][0]["value"] == 600
    assert (
        engine.inspect_claim(cid(engine, "old"), 250, known_at=150)["fuzzy_score"] == 1
    )


def test_agent_tool_cannot_forge_confirmation_protection_or_user_deletion(engine):
    tool = MemoryToolAdapter(engine, agent_id="planner")
    fake = tool.call_tool(
        "add_memory",
        dict(
            content="false",
            claims=[dict(subject="North", predicate="budget", value=600, kind="rule")],
            source_info=dict(origin="user", actor_id="north", user_confirmed=True),
        ),
    )
    assert not fake["success"] and engine.vector_store.count() == 0
    proposed = tool.call_tool(
        "add_memory",
        dict(
            content="Agent proposes budget 600",
            claims=[dict(subject="North", predicate="budget", value=600)],
            source_info=dict(origin="tool", actor_id="fake", quality=1.0),
        ),
    )
    assert proposed["success"]
    view = engine.inspect_claim(cid(engine, proposed["result"]))
    assert not view["accepted"] and not view["protected"]
    assert (
        view["sources"][0]["origin"] == "agent"
        and view["sources"][0]["actor_id"] == "planner"
    )
    assert not tool.call_tool(
        "delete_memory", dict(memory_id=proposed["result"], user_confirmed=True)
    )["success"]
    assert not tool.call_tool(
        "add_memory", dict(content="bad", claims=[], source_info={"quality": "bad"})
    )["success"]


def test_completed_work_is_retained_when_later_memory_change_requires_review(engine):
    at = int(time.time()) - 10
    add(engine, "budget", 1000, kind="rule", at=at)
    planner = MemoryToolAdapter(engine, agent_id="planner")
    reviewer = MemoryToolAdapter(engine, agent_id="reviewer")
    assert planner.call_tool(
        "record_work", dict(work_id="booked", claim_ids=[cid(engine, "budget")])
    )["success"]
    assert not reviewer.call_tool("complete_work", dict(work_id="booked"))["success"]
    assert planner.call_tool("complete_work", dict(work_id="booked"))["success"]
    add(
        engine,
        "new",
        600,
        kind="rule",
        at=at + 5,
        action="supersede",
        reason="New budget after completion",
    )
    packet = reviewer.call_tool("handoff_memory", dict(work_ids=["booked"]))["result"]
    assert not packet["can_continue"]
    work = packet["work"][0]["work"]
    assert (
        work["status"] == "completed"
        and work["validation_state"] == "stale"
        and work["completed_at"]
    )
    assert not planner.call_tool("complete_work", dict(work_id="booked"))["success"]


def test_conflicting_claim_marks_only_related_work_for_review(engine):
    at = int(time.time()) - 5
    add(engine, "old", 1000, kind="rule", at=at)
    engine.record_work("plan", [cid(engine, "old")])
    add(
        engine,
        "agent_claim",
        700,
        kind="rule",
        at=at + 1,
        origin="agent",
        confirmed=False,
        actor="critic",
    )
    assert engine.handoff(["plan"])["work"][0]["work"]["status"] == "stale"


def test_batch_typed_ingestion_and_immutable_event_replay(engine):
    items = [
        dict(
            content="Typed fact",
            memory_id="batch",
            claims=[dict(subject="North", predicate="language", value="Python")],
            source_info=dict(
                origin="user", actor_id="north", user_confirmed=True, recorded_at=100
            ),
        )
    ]
    assert engine.add_batch(items) == ["batch"]
    assert engine.add_batch(items) == ["batch"]
    assert engine.vector_store.count() == 1


def test_accepted_alias_is_not_available_before_its_evidence_was_known(engine):
    add(
        engine,
        "location",
        "Pune",
        subject="Inditech Electrosystems",
        predicate="location",
        at=100,
    )
    add(
        engine,
        "alias",
        "Inditech Electrosystems",
        subject="Inditech Systems",
        predicate="same_as",
        action="alias",
        at=200,
    )
    assert (
        engine.recall(
            "location",
            "Inditech Systems",
            predicate="location",
            query_time=250,
            known_at=150,
        )["answer_status"]
        == "missing"
    )
    packet = engine.recall(
        "location",
        "Inditech Systems",
        predicate="location",
        query_time=250,
        known_at=250,
    )
    assert packet["evidence"][0]["identity_evidence"][0]["evidence_claim_id"] == cid(
        engine, "alias"
    )


def test_agent_repetition_does_not_refresh_or_strengthen_a_user_fact(engine):
    add(engine, "original", 600, at=100)
    before = engine.inspect_claim(cid(engine, "original"), 100 + 90 * 86400)[
        "fuzzy_score"
    ]
    add(
        engine,
        "echo",
        600,
        at=100 + 89 * 86400,
        origin="agent",
        confirmed=False,
        actor="echo_agent",
        action="confirm",
    )
    after = engine.inspect_claim(cid(engine, "original"), 100 + 90 * 86400)
    assert after["fuzzy_score"] == before
    assert after["fuzzy_explanation"]["inputs"]["support"] == pytest.approx(1 / 3)


def test_agents_cannot_relabel_a_budget_as_the_phone_number(engine):
    with pytest.raises(ValueError):
        add(
            engine,
            "confused",
            600,
            origin="agent",
            confirmed=False,
            aliases=["phone number"],
        )
    assert engine.vector_store.count() == 0


def test_equal_numeric_values_do_not_create_false_contradictions(engine):
    add(engine, "integer", 600)
    add(engine, "float", 600.0, at=200, action="confirm")
    packet = engine.recall("budget", "North", query_time=250)
    assert packet["answer_status"] == "supported" and len(packet["evidence"]) == 1


def test_past_belief_is_not_reported_as_truth_after_a_known_correction(engine):
    add(engine, "mistake", 3, predicate="study_year", at=100)
    add(
        engine,
        "correction",
        2,
        predicate="study_year",
        at=200,
        action="correct",
        reason="Wrong year in the earlier statement",
    )
    past = engine.recall(
        "year", "North", predicate="study_year", query_time=150, known_at=250
    )
    assert past["answer_status"] == "historical_assertion"
    assert not past["evidence"][0]["accepted_for_current_use"]
    unaware = engine.inspect_claim(cid(engine, "mistake"), 150, known_at=150)
    assert not unaware["correction_known"] and unaware["ended_at"] is None


def test_identical_messages_in_different_events_are_distinct_episodes(engine):
    source = dict(origin="agent", actor_id="planner", recorded_at=100)
    for mid in ["first", "second"]:
        engine.add(
            "Hello again",
            memory_id=mid,
            source_info=source,
            metadata={"session_id": "S1"},
        )
    hits = engine.search(
        "planner Hello again", retrieval_mode="vector", k=5, query_time=200
    )
    assert {h.memory_id for h in hits} == {"first", "second"}
    for mid in ["first", "second"]:
        assert engine.inspect_claim(cid(engine, mid), 200)["scope"] == {
            "session_id": "S1"
        }


def test_repeated_identity_evidence_preserves_earlier_knowledge_and_deletion(engine):
    add(
        engine,
        "location",
        "Pune",
        subject="Inditech Electrosystems",
        predicate="location",
    )
    for mid, at in [("first_alias", 110), ("second_alias", 210)]:
        add(
            engine,
            mid,
            "Inditech Electrosystems",
            subject="Inditech Systems",
            predicate="same_as",
            action="alias",
            at=at,
        )
    past = engine.recall(
        "location",
        "Inditech Systems",
        predicate="location",
        query_time=150,
        known_at=150,
    )
    assert past["answer_status"] == "supported"
    assert past["evidence"][0]["identity_evidence"][0]["evidence_claim_id"] == cid(
        engine, "first_alias"
    )
    engine.delete("second_alias", user_confirmed=True)
    current = engine.recall("location", "Inditech Systems", predicate="location")
    assert current["answer_status"] == "supported"
    engine.delete("first_alias", user_confirmed=True)
    assert (
        engine.recall("location", "Inditech Systems", predicate="location")[
            "answer_status"
        ]
        == "missing"
    )
