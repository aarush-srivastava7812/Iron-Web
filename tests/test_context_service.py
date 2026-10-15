"""Real graph/vector integration for stale cache hits and authenticated snapshots."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import time
import uuid

import pytest

from memory.shared.service import SharedMemoryService, PendingMemory
from memory.models import EngineStorageError
from tests.test_shared_memory_service import settings
from tests.test_context_assembly import runtime


@pytest.fixture
def contexts(tmp_path):
    keys, records = settings()
    keys["B", "planner"] = "test_private_credential_Bplanner"
    records.append(
        dict(
            tenant="B",
            actor="planner",
            role="agent",
            token_hash=hashlib.sha256(keys["B", "planner"].encode()).hexdigest(),
        )
    )
    service = SharedMemoryService(
        tmp_path / "service",
        records,
        namespace="test_ctx_" + uuid.uuid4().hex[:8],
        context_runtime=runtime(),
        autostart=False,
    )
    yield service, keys
    service.close()


def actor(contexts, name="planner", tenant="A"):
    return contexts[0].authenticate(contexts[1][tenant, name])


def event(contexts, eid="original", value=100000, trip="summer", **changes):
    service, _ = contexts
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id=eid,
            subject="Traveller",
            text=f"Budget {value}",
            confirmed=True,
            scope={"trip_id": trip},
            claims=[
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=value,
                    kind="rule",
                    scope={"trip_id": trip},
                    **changes,
                )
            ],
        ),
    )
    while service.process_one():
        pass


def context(contexts, **extra):
    return contexts[0].context(
        actor(contexts),
        subject="Traveller",
        scope={"trip_id": "summer"},
        task_type="itinerary",
        **extra,
    )


def test_warm_hit_pending_change_and_accepted_replacement(contexts):
    service, _ = contexts
    event(contexts)
    old = context(contexts)
    warm = context(contexts)
    assert not old["cache_hit"] and warm["cache_hit"]
    assert "100000" in warm["traveller_text"]
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="new",
            subject="Traveller",
            text="Lower budget",
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=60000,
                    kind="rule",
                    scope={"trip_id": "summer"},
                    action="supersede",
                    reason="User lowered budget",
                )
            ],
        ),
    )
    with pytest.raises(PendingMemory):
        context(contexts)
    with pytest.raises(PendingMemory):
        service.validate_context(actor(contexts), old["context_token"])
    while service.process_one():
        pass
    new = context(contexts)
    assert "60000" in new["traveller_text"] and "100000" not in new["prompt"]
    assert not service.validate_context(actor(contexts), old["context_token"])["valid"]
    assert service.validate_context(actor(contexts), new["context_token"])["valid"]


def test_unrelated_trip_keeps_context_warm_but_global_changes_still_block(contexts):
    seed_ready(contexts)
    service, _ = contexts
    saved = context(contexts)
    assert context(contexts)["cache_hit"]
    service.record_work(actor(contexts), "summer-plan", saved["claim_ids"])
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="other-trip",
            subject="Traveller",
            text="My budget is 20000",
            scope={"trip_id": "other"},
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=20000,
                    kind="rule",
                    scope={"trip_id": "other"},
                )
            ],
        ),
    )
    assert context(contexts)["cache_hit"]
    assert service.handoff(actor(contexts), ["summer-plan"])["can_continue"]
    lease = service.claim_work(actor(contexts), "summer-plan")["work"]["lease_token"]
    assert (
        service.complete_work(actor(contexts), "summer-plan", lease)["status"]
        == "completed"
    )
    assert service.validate_context(actor(contexts), saved["context_token"])["valid"]
    while service.process_one():
        pass
    assert context(contexts)["cache_hit"]
    assert service.validate_context(actor(contexts), saved["context_token"])["valid"]
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="global",
            subject="Traveller",
            text="Change my preferences",
            confirmed=True,
        ),
    )
    with pytest.raises(PendingMemory):
        context(contexts)


def test_misleading_event_envelope_cannot_hide_relevant_pending_claims(contexts):
    seed_ready(contexts)
    service, _ = contexts
    saved = context(contexts)
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="mixed-scope",
            subject="Traveller",
            text="Change this trip",
            scope={"trip_id": "other"},
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=20000,
                    kind="rule",
                    scope={"trip_id": "summer"},
                )
            ],
        ),
    )
    with pytest.raises(PendingMemory):
        context(contexts)
    with pytest.raises(PendingMemory):
        service.validate_context(actor(contexts), saved["context_token"])


def test_scope_gates_preserve_work_input_validation(contexts):
    service, _ = contexts
    with pytest.raises(ValueError):
        service.handoff(actor(contexts), None)
    with pytest.raises(EngineStorageError, match="exact claim"):
        service.record_work(actor(contexts), "invalid", [{}])


def test_external_graph_change_also_revokes_context(contexts):
    seed_ready(contexts)
    service, _ = contexts
    saved = context(contexts)
    service.engine("A").add(
        "Updated directly",
        claims=[
            dict(
                subject="Traveller",
                predicate="budget",
                value=50000,
                kind="rule",
                scope={"trip_id": "summer"},
                action="supersede",
                reason="Direct local change",
            )
        ],
        source_info=dict(origin="user", actor_id="local-user", user_confirmed=True),
    )
    assert not service.validate_context(actor(contexts), saved["context_token"])[
        "valid"
    ]
    assert "50000" in context(contexts)["prompt"]


def test_tokens_are_actor_bound_and_tamper_proof(contexts):
    saved = context(contexts)
    service, _ = contexts
    with pytest.raises(PermissionError):
        service.validate_context(actor(contexts, "reviewer"), saved["context_token"])
    with pytest.raises(PermissionError):
        service.validate_context(actor(contexts), saved["context_token"] + "x")
    with pytest.raises(PermissionError):
        service.context(
            actor(contexts, "user"),
            subject="T",
            scope={"trip_id": "summer"},
            task_type="itinerary",
        )


def test_other_trips_users_and_redaction_cannot_reuse_cached_values(contexts):
    service, _ = contexts
    event(contexts)
    original = context(contexts)
    other = service.context(
        actor(contexts),
        subject="Traveller",
        scope={"trip_id": "other"},
        task_type="itinerary",
    )
    assert "100000" not in other["prompt"]
    user_b = service.context(
        actor(contexts, "planner", "B"),
        subject="Traveller",
        scope={"trip_id": "summer"},
        task_type="itinerary",
    )
    assert "100000" not in user_b["prompt"]
    with pytest.raises(PermissionError):
        service.validate_context(
            actor(contexts, "planner", "B"), original["context_token"]
        )
    service.forget(actor(contexts, "user"), "original")
    with pytest.raises(PendingMemory):
        context(contexts)
    while service.process_one():
        pass
    after = context(contexts)
    assert "100000" not in after["prompt"]
    assert not service.validate_context(actor(contexts), original["context_token"])[
        "valid"
    ]


def test_future_claim_boundary_invalidates_without_a_new_write(contexts):
    service, _ = contexts
    now = int(time.time())
    service.context_access.clock = lambda: now
    event(contexts, valid_from=now + 10)
    early = context(contexts)
    assert "100000" not in early["prompt"]
    service.context_access.clock = lambda: now + 11
    later = context(contexts)
    assert "100000" in later["traveller_text"] and not later["cache_hit"]
    assert not service.validate_context(actor(contexts), early["context_token"])[
        "valid"
    ]


def test_concurrent_requests_return_independent_payloads(contexts):
    event(contexts)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: context(contexts), range(4)))
    responses[0]["traveller_text"] = "mutated"
    assert "100000" in context(contexts)["traveller_text"]


def seed_ready(contexts):
    event(contexts)
    service, _ = contexts
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="trip",
            subject="Traveller",
            text="Trip details",
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate=p,
                    value=v,
                    scope={"trip_id": "summer"},
                )
                for p, v in {
                    "destination": "Goa",
                    "dates": "2026-12-01 to 2026-12-05",
                    "currency": "INR",
                }.items()
            ],
        ),
    )
    while service.process_one():
        pass


def test_all_saved_trip_requirements_reach_every_brief_and_work(contexts):
    seed_ready(contexts)
    service, _ = contexts
    rules = {
        "max_walk_metres": 500,
        "avoid_boats": True,
        "max_activities_per_day": 1,
        "accessibility": "step-free",
        "custom_transfer_requirement": "Only a vehicle with a ramp",
    }
    facts = {
        "departure_city": "Delhi",
        "traveller_count": 2,
        "flight_time_preference": "morning",
    }
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="restrictions",
            subject="Traveller",
            text="Confirmed trip requirements",
            scope={"trip_id": "summer"},
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate=p,
                    value=v,
                    kind="rule" if p in rules else "fact",
                    scope={"trip_id": "summer"},
                )
                for p, v in {**rules, **facts}.items()
            ],
        ),
    )
    while service.process_one():
        pass
    for task in ("flight", "hotel", "itinerary"):
        packet = service.context(
            actor(contexts),
            subject="Traveller",
            scope={"trip_id": "summer"},
            task_type=task,
        )
        assert packet["status"] == "ready"
        for predicate in {**rules, **facts}:
            assert predicate + ":" in packet["prompt"]
        assert "max_walk_metres:" in packet["traveller_text"]
    service.record_work(actor(contexts), "brief-only", packet["claim_ids"])
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="walking-change",
            subject="Traveller",
            text="Maximum walking is now 50 metres",
            scope={"trip_id": "summer"},
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate="max_walk_metres",
                    value=50,
                    kind="rule",
                    scope={"trip_id": "summer"},
                    action="supersede",
                    reason="User tightened walking limit",
                )
            ],
        ),
    )
    while service.process_one():
        pass
    assert not service.handoff(actor(contexts), ["brief-only"])["can_continue"]
    assert "[50]" in context(contexts)["traveller_text"]


def test_protected_profile_and_session_rules_cannot_be_hidden_by_trip_preferences(
    contexts,
):
    seed_ready(contexts)
    service, _ = contexts
    claims = [
        dict(
            subject="Traveller",
            predicate="dietary",
            value=value,
            kind=kind,
            scope=scope,
        )
        for value, kind, scope in [
            ("vegetarian", "rule", {}),
            ("seafood", "preference", {"trip_id": "summer"}),
            ("no nuts", "rule", {"trip_id": "summer", "session_id": "call"}),
        ]
    ]
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="food-rules",
            text="Explicit food constraints",
            subject="Traveller",
            confirmed=True,
            claims=claims,
        ),
    )
    while service.process_one():
        pass
    packet = context(contexts, session_id="call")
    assert "vegetarian" in packet["prompt"] and "no nuts" in packet["prompt"]
    assert packet["status"] == "needs_information"
    assert packet["required_issues"]["dietary"] == "scope_conflict"


def test_http_client_discards_response_generated_during_a_change(contexts):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from memory.shared.client import SharedMemoryClient
    from shared_server import handler_for

    seed_ready(contexts)
    service, keys = contexts
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(service))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = SharedMemoryClient(
            "http://127.0.0.1:" + str(server.server_port), keys["A", "planner"]
        )
        calls = []

        def generate(packet):
            calls.append(packet["traveller_text"])
            if len(calls) == 1:
                event(
                    contexts,
                    "lowered",
                    60000,
                    action="supersede",
                    reason="Lower approved budget",
                )
            return packet["traveller_text"]

        result = client.generate_current(
            dict(
                subject="Traveller", scope={"trip_id": "summer"}, task_type="itinerary"
            ),
            generate,
        )
        assert result["status"] == "ready" and len(calls) == 2
        assert "60000" in result["response"] and "100000" not in result["response"]
        assert client.validate_context(result["context"]["context_token"])["valid"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_generation_retry_is_bounded_and_missing_fields_skip_generation(contexts):
    from memory.shared.client import SharedMemoryClient

    client = SharedMemoryClient("http://127.0.0.1", "unused")
    service, _ = contexts
    client.context = lambda **body: context(contexts)
    client.validate_context = lambda token: dict(valid=False)
    calls = []
    assert (
        client.generate_current({}, lambda packet: calls.append(packet))["status"]
        == "needs_information"
    )
    assert not calls
    seed_ready(contexts)
    result = client.generate_current({}, lambda packet: calls.append(packet))
    assert result["status"] == "context_changed" and len(calls) == 3


def test_failed_or_unclear_event_cannot_bypass_a_warm_context(contexts):
    seed_ready(contexts)
    saved = context(contexts)
    service, _ = contexts
    service.submit(
        actor(contexts, "user"),
        dict(
            event_id="unclear",
            subject="Traveller",
            text="Make everything different",
            confirmed=True,
        ),
    )
    while service.process_one():
        pass
    assert (
        service.receipt(actor(contexts, "user"), "unclear")["status"] == "needs_review"
    )
    with pytest.raises(PendingMemory):
        context(contexts)
    service.withdraw(actor(contexts, "user"), "unclear")
    assert not service.validate_context(actor(contexts), saved["context_token"])[
        "valid"
    ]
    assert context(contexts)["status"] == "ready"


def test_context_dependencies_reach_handoff_without_sharing_ownership(contexts):
    seed_ready(contexts)
    service, _ = contexts
    prepared = context(contexts)
    service.record_work(actor(contexts), "context-plan", prepared["claim_ids"])
    lease = service.claim_work(actor(contexts), "context-plan")["work"]["lease_token"]
    event(contexts, "lower-budget", 60000, action="supersede", reason="New user cap")
    packet = service.handoff(actor(contexts, "reviewer"), ["context-plan"])
    assert not packet["can_continue"] and packet["work"][0]["needs_review"]
    assert lease not in str(context(contexts)) and lease not in str(packet)


def test_restart_rebuilds_views_and_rejects_old_context_proofs(contexts):
    seed_ready(contexts)
    service, _ = contexts
    saved = context(contexts)
    root, namespace = service.root, service.namespace
    records = [
        dict(token_hash=digest, tenant=p.tenant, actor=p.actor, role=p.role)
        for digest, p in service.credentials
    ]
    service.close()
    reopened = SharedMemoryService(
        root, records, namespace=namespace, context_runtime=runtime(), autostart=False
    )
    service.__dict__ = reopened.__dict__
    with pytest.raises(PermissionError):
        service.validate_context(actor(contexts), saved["context_token"])
    rebuilt = context(contexts)
    assert not rebuilt["cache_hit"] and "100000" in rebuilt["traveller_text"]


def test_agent_proposal_does_not_become_a_current_context_requirement(contexts):
    service, _ = contexts
    service.submit(
        actor(contexts),
        dict(
            event_id="proposal",
            subject="Traveller",
            text="Agent suggests a budget",
            claims=[
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=99999,
                    kind="rule",
                    scope={"trip_id": "summer"},
                )
            ],
        ),
    )
    while service.process_one():
        pass
    prepared = context(contexts)
    assert prepared["status"] == "needs_information"
    assert prepared["required_issues"]["budget"] == "unconfirmed"
    assert "99999" not in prepared["prompt"]


def test_time_boundary_crossed_during_assembly_does_not_return_old_context(contexts):
    service, _ = contexts
    now = int(time.time())
    event(contexts, valid_until=now + 1)
    clock = iter([now, now + 2])
    service.context_access.clock = lambda: next(clock)
    with pytest.raises(RuntimeError, match="changed"):
        context(contexts)


@pytest.mark.gpu
def test_cuda_service_change_and_deletion_revoke_resident_cards(contexts):
    from memory.cache.cards import CardRouter

    service, _ = contexts
    service.context_access.runtime.ranker = CardRouter(use_gpu=True)
    seed_ready(contexts)
    prepared = context(contexts)
    assert prepared["residency"]["device"] == "cuda", prepared["residency"]
    index = service.context_access.runtime.ranker.index
    old_handle, old_owner = index.handle, index.owner
    service.forget(actor(contexts, "user"), "original")
    assert index.device_matrix is None and index.handle is None
    with pytest.raises(PendingMemory):
        context(contexts)
    while service.process_one():
        pass
    after = context(contexts)
    assert "100000" not in after["prompt"]
    with pytest.raises(PermissionError):
        import numpy as np

        index.rank(old_owner, old_handle, np.zeros(384, dtype=np.float32), 1)
