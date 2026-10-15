"""Actual graph/vector proofs for authenticated receipts, coordination and replay."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import time
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

import pytest

from memory.models import EngineStorageError
from memory.shared.service import SharedMemoryService, PendingMemory
from memory.shared.interpreter import TravelInterpreter
from shared_server import handler_for


def settings():
    keys, records = {}, []
    for tenant, actor, role in [
        ("A", "user", "user"),
        ("A", "planner", "agent"),
        ("A", "reviewer", "agent"),
        ("B", "user", "user"),
    ]:
        token = "test_private_credential_" + tenant + actor
        keys[tenant, actor] = token
        records.append(
            dict(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                tenant=tenant,
                actor=actor,
                role=role,
            )
        )
    return keys, records


@pytest.fixture
def shared(tmp_path):
    keys, records = settings()
    service = SharedMemoryService(
        tmp_path / "service",
        records,
        namespace="test_shared_" + uuid.uuid4().hex[:8],
        interpreter=TravelInterpreter(),
        autostart=False,
    )
    yield service, keys
    service.close()


def principal(shared, tenant="A", actor="user"):
    service, keys = shared
    return service.authenticate(keys[tenant, actor])


def send(shared, eid="old", value=1000, **extra):
    service, _ = shared
    body = dict(
        event_id=eid,
        text=f"Budget {value}",
        subject="Traveller",
        confirmed=True,
        claims=[
            dict(
                subject="Traveller",
                predicate="budget",
                value=value,
                kind="rule",
                **extra,
            )
        ],
    )
    return service.submit(principal(shared), body)


def drain(shared):
    service, _ = shared
    while service.process_one():
        pass


def test_receipt_is_durable_before_semantic_work_and_retry_is_idempotent(shared):
    service, keys = shared
    saved = send(shared)
    assert saved["status"] == "queued" and not service.engines
    with pytest.raises(PendingMemory):
        service.recall(principal(shared), query="budget", subject="Traveller")
    namespace, root, records = service.namespace, service.root, settings()[1]
    service.close()
    reopened = SharedMemoryService(root, records, namespace=namespace, autostart=False)
    # Replace fixture's object in place so teardown closes the current owner.
    service.__dict__ = reopened.__dict__
    drain(shared)
    assert service.receipt(principal(shared), "old")["status"] == "ready"
    assert send(shared)["status"] == "ready"
    assert service.engine("A").vector_store.count() == 1
    with pytest.raises(ValueError):
        send(shared, value=600)


def test_pending_change_blocks_completion_and_invalidates_only_related_work(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    evidence = service.recall(principal(shared), query="budget", subject="Traveller")
    service.record_work(
        principal(shared), "plan", [evidence["evidence"][0]["claim_id"]]
    )
    owned = service.claim_work(principal(shared, actor="planner"), "plan")["work"]
    send(shared, "changed", 600, action="supersede", reason="User changed budget")
    with pytest.raises(PendingMemory):
        service.complete_work(
            principal(shared, actor="planner"), "plan", owned["lease_token"]
        )
    drain(shared)
    handoff = service.handoff(principal(shared, actor="reviewer"), ["plan"])
    assert not handoff["can_continue"]
    assert handoff["work"][0]["current_evidence"][0]["value"] == 600
    assert "lease_token" not in handoff["work"][0]["work"]


def test_private_user_spaces_and_source_authority(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    assert (
        service.recall(principal(shared, "B"), query="budget", subject="Traveller")[
            "answer_status"
        ]
        == "missing"
    )
    body = dict(event_id="forged", text="Change", subject="Traveller", confirmed=True)
    with pytest.raises(PermissionError):
        service.submit(principal(shared, actor="planner"), body)
    with pytest.raises(PermissionError):
        service.authenticate("incorrect_secret_which_is_long_enough")
    assert service.engine("A").graph_name != service.engine("B").graph_name


def test_raw_inputs_are_interpreted_conservatively_and_failures_stay_visible(shared):
    service, _ = shared
    service.submit(
        principal(shared),
        dict(
            event_id="raw",
            text="My maximum travel budget is 750.",
            subject="Traveller",
            confirmed=True,
            scope={"trip_id": "X"},
        ),
    )
    drain(shared)
    assert (
        service.recall(
            principal(shared),
            query="budget",
            subject="Traveller",
            scope={"trip_id": "X"},
        )["evidence"][0]["value"]
        == 750
    )
    service.submit(
        principal(shared),
        dict(
            event_id="unrecognized",
            text="Perhaps everything should be different, who knows.",
            subject="Traveller",
            confirmed=True,
        ),
    )
    drain(shared)
    assert (
        service.receipt(principal(shared), "unrecognized")["status"] == "needs_review"
    )
    assert (
        service.receipt(principal(shared), "unrecognized")["semantic_claim_count"] == 0
    )
    with pytest.raises(PendingMemory):
        service.recall(principal(shared), query="budget", subject="Traveller")
    service.withdraw(principal(shared), "unrecognized")
    assert (
        service.recall(principal(shared), query="phone", subject="Traveller")[
            "answer_status"
        ]
        == "missing"
    )
    service.submit(
        principal(shared, actor="planner"),
        dict(
            event_id="agent-change",
            text="Change my budget to 300.",
            subject="Traveller",
        ),
    )
    drain(shared)
    assert service.receipt(principal(shared), "agent-change")["status"] == "failed"
    with pytest.raises(PendingMemory):
        service.recall(principal(shared), query="budget", subject="Traveller")
    service.withdraw(principal(shared), "agent-change")
    assert not service.journal.pending("A")


def test_notification_acknowledgments_are_per_agent_and_persistent(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    assert len(service.journal.notices("A", "planner")) == 1
    service.journal.acknowledge("A", "planner", "old")
    service.journal.acknowledge("A", "planner", "old")
    assert not service.journal.notices("A", "planner")
    assert len(service.journal.notices("A", "reviewer")) == 1
    assert not service.journal.notices("B", "planner")


def test_concurrent_agents_have_one_owner_and_stale_completion_is_fenced(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    cid = service.recall(principal(shared), query="budget", subject="Traveller")[
        "evidence"
    ][0]["claim_id"]
    service.record_work(principal(shared), "plan", [cid])

    def attempt(actor):
        try:
            return actor, service.claim_work(principal(shared, actor=actor), "plan")
        except EngineStorageError:
            return actor, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, ["planner", "reviewer"] * 4))
    owners = {actor for actor, result in results if result}
    assert len(owners) == 1
    old_owner = next(iter(owners))
    other = "reviewer" if old_owner == "planner" else "planner"
    first = next(result["work"] for _, result in results if result)
    engine = service.engine("A")
    engine.graph_store.execute("MATCH(w:MemoryWork {id:'plan'}) SET w.lease_until=0")
    new = service.claim_work(principal(shared, actor=other), "plan")["work"]
    assert new["owner_version"] == first["owner_version"] + 1
    with pytest.raises(EngineStorageError):
        service.complete_work(
            principal(shared, actor=old_owner), "plan", first["lease_token"]
        )
    completed = service.complete_work(
        principal(shared, actor=other), "plan", new["lease_token"]
    )
    assert completed["status"] == "completed"
    assert (
        service.complete_work(
            principal(shared, actor=other), "plan", new["lease_token"]
        )["completed_at"]
        == completed["completed_at"]
    )
    assert (
        service.claim_work(principal(shared, actor=old_owner), "plan")["status"]
        == "already_completed"
    )


def test_http_authentication_tenant_binding_and_pending_response(shared):
    service, keys = shared
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(service))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"

    def call(path, data, token):
        return urlopen(
            Request(
                url + path,
                data=json.dumps(data).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token,
                },
            ),
            timeout=10,
        )

    try:
        with pytest.raises(HTTPError) as error:
            call(
                "/v1/recall",
                dict(query="budget", subject="Traveller"),
                "invalid_credentials_long_enough",
            )
        assert error.value.code == 401
        receipt = json.load(
            call(
                "/v1/events",
                dict(
                    event_id="http",
                    text="My budget is 400.",
                    subject="Traveller",
                    confirmed=True,
                ),
                keys["A", "user"],
            )
        )
        assert receipt["status"] == "queued"
        with pytest.raises(HTTPError) as error:
            call(
                "/v1/recall",
                dict(query="budget", subject="Traveller"),
                keys["A", "planner"],
            )
        assert error.value.code == 409
        drain(shared)
        assert (
            json.load(
                call(
                    "/v1/recall",
                    dict(query="budget", subject="Traveller"),
                    keys["A", "planner"],
                )
            )["evidence"][0]["value"]
            == 400
        )
        assert (
            json.load(
                call(
                    "/v1/recall",
                    dict(query="budget", subject="Traveller"),
                    keys["B", "user"],
                )
            )["answer_status"]
            == "missing"
        )
        with pytest.raises(HTTPError) as error:
            call(
                "/v1/events",
                dict(event_id="escape", text="x", subject="Traveller", tenant="B"),
                keys["A", "planner"],
            )
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cold_backup_and_fresh_restore_preserve_memory_and_completed_work(
    shared, tmp_path
):
    from memory.shared.snapshot import cold_backup, restore_fresh

    service, _ = shared
    send(shared)
    drain(shared)
    cid = service.recall(principal(shared), query="budget", subject="Traveller")[
        "evidence"
    ][0]["claim_id"]
    service.record_work(principal(shared), "completed", [cid])
    lease = service.claim_work(principal(shared, actor="planner"), "completed")["work"][
        "lease_token"
    ]
    service.complete_work(principal(shared, actor="planner"), "completed", lease)
    service.record_work(principal(shared), "unfinished", [cid])
    service.claim_work(principal(shared, actor="planner"), "unfinished")
    namespace, root, records = service.namespace, service.root, settings()[1]
    service.close()
    backup = tmp_path / "snapshot"
    assert cold_backup(root, records, namespace, backup)["tenants"] == 2
    target = tmp_path / "restored"
    assert not restore_fresh(backup, target)["active_execution_leases_restored"]
    restored = SharedMemoryService(
        target, records, namespace=namespace, autostart=False
    )
    try:
        actor = restored.authenticate(settings()[0]["A", "reviewer"])
        assert (
            restored.recall(actor, query="budget", subject="Traveller")["evidence"][0][
                "value"
            ]
            == 1000
        )
        assert (
            restored.handoff(actor, ["completed"])["work"][0]["work"]["status"]
            == "completed"
        )
        assert (
            restored.claim_work(actor, "unfinished")["work"]["agent_id"] == "reviewer"
        )
        assert restored.engine("A").graph_name != service.engine("A").graph_name
    finally:
        restored.close()
    with pytest.raises(ValueError):
        restore_fresh(backup, target)


def test_two_workers_keep_one_tenant_ordered_while_another_can_progress(shared):
    from threading import Event

    service, _ = shared
    entered, release, second_started = Event(), Event(), Event()
    interpreter = TravelInterpreter()

    def interpret(text, context):
        if text == "My budget is 1000.":
            entered.set()
            assert release.wait(10)
        if text == "Change my budget to 600.":
            second_started.set()
        return interpreter(text, context)

    service.interpreter = interpret
    for tenant, eid, text in [
        ("A", "first", "My budget is 1000."),
        ("A", "second", "Change my budget to 600."),
        ("B", "other", "My budget is 300."),
    ]:
        service.submit(
            principal(shared, tenant),
            dict(event_id=eid, text=text, subject="Traveller", confirmed=True),
        )
    for index in range(2):
        worker = Thread(target=service._loop, daemon=True)
        service.workers.append(worker)
        worker.start()
    try:
        assert entered.wait(5)
        deadline = time.monotonic() + 5
        while (
            service.receipt(principal(shared, "B"), "other")["status"] != "ready"
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert service.receipt(principal(shared, "B"), "other")["status"] == "ready"
        assert not second_started.is_set()
        release.set()
        deadline = time.monotonic() + 5
        while (
            service.receipt(principal(shared), "second")["status"] != "ready"
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert (
            service.recall(principal(shared), query="budget", subject="Traveller")[
                "evidence"
            ][0]["value"]
            == 600
        )
    finally:
        release.set()


def test_local_interpretation_does_not_drop_a_destination_condition():
    assert (
        TravelInterpreter()(
            "I want to visit Jaipur if I can afford it.",
            dict(subject="Traveller", scope={}),
        )
        == []
    )


@pytest.mark.parametrize("boundary", ["receipt", "vector", "graph", "vector_loss"])
def test_killed_process_replays_receipt_and_repairs_partial_write(
    shared, tmp_path, boundary
):
    service, keys = shared
    send(shared)
    root, namespace, records = service.root, service.namespace, settings()[1]
    service.close()
    config = tmp_path / "crash.json"
    config.write_text(
        json.dumps(dict(root=str(root), namespace=namespace, records=records)),
        encoding="utf-8",
    )
    script = Path(__file__).parent / "fixtures/shared_crash.py"
    result = subprocess.run(
        [sys.executable, str(script), str(config), boundary],
        cwd=Path(__file__).resolve().parents[1],
        timeout=30,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 72, result.stdout + result.stderr
    reopened = SharedMemoryService(root, records, namespace=namespace, autostart=False)
    service.__dict__ = reopened.__dict__
    drain(shared)
    assert service.receipt(principal(shared), "old")["status"] == "ready"
    engine = service.engine("A")
    assert engine.vector_store.count() == 1
    assert (
        service.recall(principal(shared), query="budget", subject="Traveller")[
            "evidence"
        ][0]["value"]
        == 1000
    )
    assert engine.graph_store.execute("MATCH(c:MemoryClaim) RETURN count(*)").rows == [
        [1]
    ]
    # Clean only extra snapshots created by this killed test process.
    for kind in ("staging", "rollback"):
        for key in engine.graph_store.redis.scan_iter(
            match="{" + engine.graph_name + "}:" + kind + ":*"
        ):
            engine.graph_store.redis.delete(key)


def test_user_deletion_scrubs_history_and_retries_do_not_resurrect_evidence(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    user = principal(shared)
    mid = service.receipt(user, "old")["memory_id"]
    assert service.history(user)["events"][0]["text"] == "Budget 1000"
    with pytest.raises(PermissionError):
        service.forget(principal(shared, actor="planner"), "old")
    assert service.forget(user, "old")["status"] == "queued"
    drain(shared)
    assert service.receipt(user, "old")["status"] == "redacted"
    assert service.history(user)["events"][0]["text"] is None
    assert service.engine("A").get(mid) is None
    assert send(shared)["status"] == "redacted"
    assert service.engine("A").vector_store.count() == 0


def test_task_waits_for_its_prerequisite_before_an_agent_can_acquire_it(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    user = principal(shared)
    agent = principal(shared, actor="planner")
    cid = service.recall(user, query="budget", subject="Traveller")["evidence"][0][
        "claim_id"
    ]
    service.record_work(user, "parent", [cid])
    service.record_work(user, "child", [cid], depends_on=["parent"])
    packet = service.handoff(agent, ["child"])
    assert not packet["can_continue"] and packet["work"][0][
        "awaiting_prerequisites"
    ] == ["parent"]
    with pytest.raises(EngineStorageError):
        service.claim_work(agent, "child")
    owned = service.claim_work(agent, "parent")["work"]
    service.complete_work(agent, "parent", owned["lease_token"])
    assert service.claim_work(agent, "child")["status"] == "owned"


def test_unknown_confirmed_change_blocks_use_of_old_approved_budget(shared):
    service, _ = shared
    send(shared)
    drain(shared)
    user = principal(shared)
    cid = service.recall(user, query="budget", subject="Traveller")["evidence"][0][
        "claim_id"
    ]
    service.record_work(user, "plan", [cid])
    service.submit(
        user,
        dict(
            event_id="unclear-change",
            text="Limit my travel spending to 410.",
            subject="Traveller",
            confirmed=True,
        ),
    )
    drain(shared)
    assert service.receipt(user, "unclear-change")["status"] == "needs_review"
    with pytest.raises(PendingMemory):
        service.claim_work(principal(shared, actor="planner"), "plan")
    assert (
        service.history(user)["events"][-1]["text"]
        == "Limit my travel spending to 410."
    )
