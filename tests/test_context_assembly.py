"""Task fields, fallback and changing moods checked before service wiring."""

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from memory.context.runtime import ContextRuntime
from memory.context.contracts import (
    AgentProfile,
    CardTemplate,
    ContextPolicy,
    ContextRequest,
)
from memory.context.tokens import TokenBudget, ContextCapacity


def runtime(**policy):
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    return ContextRuntime(
        profiles=[
            AgentProfile(
                actor_id="planner", version="1", instructions="Plan practical trips."
            )
        ],
        tokens=TokenBudget(tokenizer, "test-fixture"),
        policy=ContextPolicy(**policy),
    )


def request(**extra):
    return ContextRequest(
        subject="Traveller", scope={"trip_id": "A"}, task_type="itinerary", **extra
    )


def answer(predicate, value, scope, *, status="supported", at=100):
    return dict(
        answer_status=status,
        evidence=[
            dict(
                claim_id="id-" + predicate,
                predicate=predicate,
                value=value,
                accepted_for_current_use=True,
                scope=scope,
                valid_until=2**63 - 1,
                sources=[dict(event_id="source-" + predicate, recorded_at=at)],
            )
        ],
    )


def reader(predicate, scope):
    values = {
        "destination": "Goa",
        "dates": "2026-12-01 to 2026-12-05",
        "budget": 60000,
        "currency": "INR",
    }
    return (
        answer(predicate, values[predicate], scope)
        if predicate in values
        else dict(answer_status="missing", evidence=[])
    )


def test_required_fields_are_current_and_unknown_task_or_actor_is_rejected():
    prepared = runtime().compile("planner", request(), reader, now=101)
    assert prepared["status"] == "ready" and "60000" in prepared["traveller_text"]
    assert set(prepared["claim_ids"]) == {
        "id-destination",
        "id-dates",
        "id-budget",
        "id-currency",
    }
    with pytest.raises(PermissionError):
        runtime().compile("other", request(), reader, now=101)
    with pytest.raises(ValueError):
        runtime().compile(
            "planner",
            ContextRequest(subject="T", scope={"trip_id": "A"}, task_type="unknown"),
            reader,
            now=101,
        )


def test_required_missing_and_disputed_fields_never_fall_back():
    called = []

    def read(predicate, scope):
        called.append((predicate, scope))
        if predicate == "budget":
            return dict(answer_status="disputed", evidence=[])
        return reader(predicate, scope)

    prepared = runtime().compile("planner", request(), read, now=101)
    assert prepared["status"] == "needs_information"
    assert prepared["required_issues"] == {"budget": "disputed"}
    assert not any(p == "budget" and not scope for p, scope in called)


def test_optional_profile_preference_does_not_hide_trip_dispute():
    def read(predicate, scope):
        if predicate == "pace":
            return answer(
                predicate,
                "restful" if scope else "busy",
                scope,
                status="disputed" if scope else "supported",
            )
        if predicate == "dietary" and not scope:
            return answer(predicate, "vegetarian", scope)
        return reader(predicate, scope)

    prepared = runtime().compile("planner", request(), read, now=101)
    assert "vegetarian" in prepared["traveller_text"]
    assert (
        "pace: disputed" in prepared["traveller_text"]
        and "busy" not in prepared["traveller_text"]
    )


def test_mood_expires_from_source_time_without_reads_renewing_it():
    def read(predicate, scope):
        return (
            answer("mood", "relaxed", scope, at=100)
            if predicate == "mood"
            else reader(predicate, scope)
        )

    active = runtime().compile("planner", request(session_id="session"), read, now=110)
    expired = runtime().compile(
        "planner", request(session_id="session"), read, now=1900
    )
    assert any(c["mood"] == "relaxed" for c in active["cards"])
    assert not any(c["mood"] for c in expired["cards"])
    assert active["expires"] <= 1900


def test_session_inherits_trip_mood_only_when_session_has_no_mood():
    def read(predicate, scope):
        if predicate == "mood" and "session_id" not in scope:
            return answer("mood", "relaxed", scope, at=100)
        return reader(predicate, scope)

    inherited = runtime().compile("planner", request(session_id="call"), read, now=110)
    assert any(c["mood"] == "relaxed" for c in inherited["cards"])
    mood = next(f for f in inherited["fields"] if f["predicate"] == "mood")
    assert mood["location"] == "trip" and mood["scopes"] == [{"trip_id": "A"}]
    expired = runtime().compile("planner", request(session_id="call"), read, now=1900)
    assert not any(c["mood"] for c in expired["cards"])

    for status in ("disputed", "unconfirmed"):

        def unresolved(predicate, scope):
            if predicate == "mood" and "session_id" in scope:
                return dict(answer_status=status, evidence=[])
            return read(predicate, scope)

        blocked = runtime().compile(
            "planner", request(session_id="call"), unresolved, now=110
        )
        assert not any(c["mood"] for c in blocked["cards"])

    def session_first(predicate, scope):
        if predicate == "mood" and "session_id" in scope:
            return answer("mood", "active", scope, at=105)
        return read(predicate, scope)

    explicit = runtime().compile(
        "planner", request(session_id="call"), session_first, now=110
    )
    assert not any(c["mood"] for c in explicit["cards"])


def test_mandatory_half_overflow_is_visible():
    with pytest.raises(ContextCapacity):
        runtime(half_tokens=2).compile("planner", request(), reader, now=101)


def test_optional_hot_overflow_is_moved_to_additional_evidence():
    def read(predicate, scope):
        return (
            answer("pace", "slow " * 100, scope)
            if predicate == "pace"
            else reader(predicate, scope)
        )

    context_runtime = runtime(half_tokens=120)
    compiled = context_runtime.compile("planner", request(), read, now=101)
    result = context_runtime.assemble(compiled, request(), owner="A")
    assert "id-pace" not in compiled["claim_ids"]
    assert "id-pace" in result["claim_ids"] and "slow" in result["evidence_text"]


def test_overlapping_cards_do_not_repeat_facts_in_the_prompt():
    base = runtime()
    configured = ContextRuntime(
        profiles=list(base.profiles.values()),
        tokens=base.tokens,
        templates=[
            CardTemplate(
                card_id=i,
                title=i,
                task_types=("itinerary",),
                fields=("pace", "interests"),
            )
            for i in ["one", "two"]
        ],
    )

    def read(predicate, scope):
        if predicate in {"pace", "interests"}:
            return answer(
                predicate,
                "a calm pace" if predicate == "pace" else "one specific museum",
                scope,
            )
        return reader(predicate, scope)

    prepared = configured.compile("planner", request(), read, now=101)
    result = configured.assemble(prepared, request(), owner="A")
    assert result["prompt"].count("a calm pace") == 1
    assert result["prompt"].count("one specific museum") == 1


def test_removing_an_optional_card_preserves_its_source_facts():
    base = runtime(context_limit=300, output_tokens=32)
    configured = ContextRuntime(
        profiles=list(base.profiles.values()),
        tokens=base.tokens,
        policy=base.policy,
        templates=[
            CardTemplate(
                card_id="large",
                title="Large card",
                task_types=("itinerary",),
                fields=("interests",),
                guidance="optional guidance " * 160,
            )
        ],
    )

    def read(predicate, scope):
        return (
            answer(predicate, "one specific museum", scope)
            if predicate == "interests"
            else reader(predicate, scope)
        )

    compiled = configured.compile("planner", request(), read, now=101)
    result = configured.assemble(compiled, request(), owner="A")
    assert result["cards"] == []
    assert "one specific museum" in result["prompt"]
    assert "id-interests" in result["claim_ids"]
