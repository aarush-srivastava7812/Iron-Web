"""Real store inspection, tenancy boundaries, and independent dashboard relay."""

import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tests.test_application_integration import connected_app, plan, requirements, trip, user  # noqa: F401

pytest_plugins = ["tests.test_application_integration"]


def test_captured_event_context_is_sanitized_and_forgotten_history_is_purged():
    from memory.observability import ObservationLog
    log = ObservationLog()
    log.emit("trip", "context_assembled", agent_id="planner", packet={
        "agent_text": "instructions", "traveller_text": "private trip fact",
        "context_token": "never-public", "tokens": {"prompt": 12},
    })
    snapshot = log.snapshot("trip")
    assert snapshot["events"][0]["context"]["tokens"]["prompt"] == 12
    assert "never-public" not in json.dumps(snapshot)
    log.invalidate("trip", purge_history=True)
    snapshot = log.snapshot("trip")
    assert snapshot["contexts"] == []
    assert "context" not in snapshot["events"][0]
    assert "private trip fact" not in json.dumps(snapshot)


def test_public_provider_token_counts_are_not_treated_as_secrets():
    from memory.observability import public_value
    assert public_value({"input_tokens": 42, "output_tokens": 12,
                         "api_key": "private", "context_token": "proof"}) == {
        "input_tokens": 42, "output_tokens": 12,
    }


def publish(monkeypatch, client, headers, path, *, narrow=True):
    from app.security import decode_token

    user_id = decode_token(headers["Authorization"][7:])
    monkeypatch.setenv("DASHBOARD_PUBLISH_TOKEN", "dashboard-read-grant-" + "q" * 32)
    monkeypatch.setenv("DASHBOARD_USER_ID", user_id)
    if narrow:
        monkeypatch.setenv("DASHBOARD_TRIP_ID", path.rsplit("/", 1)[1])
    else:
        monkeypatch.delenv("DASHBOARD_TRIP_ID", raising=False)
    return {"Authorization": "Bearer dashboard-read-grant-" + "q" * 32}


def test_dashboard_inspects_actual_memory_without_warming_context(
    connected_app, monkeypatch
):
    client, runtime = connected_app
    headers = user(client, "dashboard_owner")
    path = trip(client, headers)
    requirements(client, headers, path)
    grant = publish(monkeypatch, client, headers, path)
    traveler = next(iter(runtime.users.values()))
    context = runtime.context_runtime
    generation = traveler.service.journal.generation(traveler.user_id)
    before = (len(context.cache.items), context.cache.bytes)
    response = client.get("/api/dashboard/snapshot", headers=grant)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["schema"] == "iron_web_dashboard_v1"
    assert data["agents"]["registered"] == 9 and data["agents"]["observed"] == 0
    assert data["tiers"]["captured_contexts"] == []
    assert len(data["tiers"]["layers"]) == 3
    assert data["tiers"]["policy"]["half_tokens"] == 2048
    assert data["tiers"]["policy"]["card_tokens"] == 1024
    assert data["databases"]["falkordb"]["status"] == "online"
    assert data["vectors"]["points"] and data["shared_memory"]["claims"]
    assert data["storage"]["memories"] > 0
    assert generation == traveler.service.journal.generation(traveler.user_id)
    assert before == (len(context.cache.items), context.cache.bytes)
    assert plan(client, headers, path)["orchestration"]["status"] == "ok"
    data = client.get("/api/dashboard/snapshot", headers=grant).json()
    assert data["agents"]["observed"] >= 4
    assert data["agents"]["reading_memory"] == 0
    assert data["tiers"]["captured_contexts"]
    assert any(e["kind"] == "context_validated" for e in data["observations"]["events"])
    assert "context_token" not in json.dumps(data)
    assert "lease_token" not in json.dumps(data)
    assert data["credentials"]["active_credential"] is None


def test_dashboard_grant_tenancy_and_vector_values(connected_app, monkeypatch):
    client, _ = connected_app
    headers = user(client, "dashboard_first")
    path = trip(client, headers)
    requirements(client, headers, path)
    second_trip = trip(client, headers)
    requirements(client, headers, second_trip, destination="Munnar")
    other = user(client, "dashboard_second")
    grant = publish(monkeypatch, client, headers, path)
    assert client.get("/api/dashboard/snapshot").status_code == 401
    assert client.get("/api/dashboard/snapshot", headers=headers).status_code == 401
    assert client.get(path + "/dashboard", headers=other).status_code == 404
    assert client.get(path + "/dashboard", headers=headers).status_code == 200
    response = client.get(
        "/api/dashboard/vectors?limit=1&include_values=true", headers=grant
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert (
        len(data["points"]) == 1
        and len(data["points"][0]["vector"]) == data["dimensions"]
    )
    assert "Munnar" not in json.dumps(data)
    assert (
        client.get(
            "/api/dashboard/vectors?after=not-a-cursor", headers=grant
        ).status_code
        == 422
    )
    assert (
        client.get("/api/dashboard/graph?offset=-1", headers=grant).status_code == 422
    )
    first = client.get("/api/dashboard/shared-memory?limit=1", headers=grant).json()
    assert first["next_offset"] == 1
    second = client.get(
        "/api/dashboard/shared-memory?limit=1&offset=1", headers=grant
    ).json()
    assert first["claims"][0]["id"] != second["claims"][0]["id"]
    monkeypatch.setenv("DASHBOARD_TRIP_ID", second_trip.rsplit("/", 1)[1])
    assert "Munnar" in client.get("/api/dashboard/snapshot", headers=grant).text
    monkeypatch.setenv("DASHBOARD_USER_ID", "nonexistent")
    assert client.get("/api/dashboard/snapshot", headers=grant).status_code == 404


def test_dashboard_full_shared_store_and_invalidation(connected_app, monkeypatch):
    client, _ = connected_app
    headers = user(client, "dashboard_shared")
    path = trip(client, headers)
    requirements(client, headers, path)
    plan(client, headers, path)
    grant = publish(monkeypatch, client, headers, path, narrow=False)
    data = client.get("/api/dashboard/snapshot", headers=grant).json()
    assert data["trip_id"] is None and data["scope"] == "traveler_shared_memory"
    assert {label for n in data["graph"]["nodes"] for label in n["labels"]} >= {
        "MemoryClaim",
        "MemorySource",
        "MemoryField",
        "Entity",
    }
    assert data["graph"]["edges"]
    requirements(client, headers, path, budget=80000)
    data = client.get("/api/dashboard/snapshot", headers=grant).json()
    assert data["tiers"]["captured_contexts"] == []
    claims = data["shared_memory"]["claims"]
    assert any(c["lifecycle_status"] == "superseded" for c in claims)
    assert client.delete(path, headers=headers).status_code == 204
    data = client.get("/api/dashboard/snapshot", headers=grant).json()
    assert data["shared_memory"]["claims"] == [] and data["vectors"]["points"] == []
    assert data["tiers"]["captured_contexts"] == []


def test_credentials_and_observations_never_expose_secrets(monkeypatch):
    from agents.config import settings
    from memory.dashboard import credential_status
    from memory.observability import ObservationLog, public_value

    secret = "nvapi-" + "secret-value-" * 4
    monkeypatch.setattr(settings, "nvidia_api_key", secret)
    monkeypatch.setenv("NVIDIA_API_KEY", secret)
    status = public_value(credential_status())
    assert secret not in json.dumps(status)
    assert status["configured"][0]["masked"].endswith(secret[-4:])
    assert status["configured"][0]["active"] is False
    log = ObservationLog(limit=2)
    for number in range(4):
        log.emit(
            "trip",
            "context_assembled",
            agent_id="agent",
            packet=dict(
                context_token="private-proof",
                agent_text=secret,
                tokens={"agent": 12},
                residency={"handle": "private-handle"},
            ),
        )
    observed = log.snapshot("trip")
    assert len(observed["events"]) == 2
    assert secret not in json.dumps(observed) and "private-proof" not in json.dumps(
        observed
    )
    assert "private-handle" not in json.dumps(observed)
    log.invalidate("trip")
    assert log.snapshot("trip")["contexts"] == []


def test_dashboard_relay_caching_failure_and_no_write_surface(monkeypatch):
    import dashboard.backend.main as module

    calls = []
    data = dict(
        schema="iron_web_dashboard_v1",
        status="online",
        agents={"observed": 2},
        observations=dict(boot="boot1", sequence=9, events=[dict(id=9)]),
        receipts=[],
    )

    def transport(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer " + "a" * 32
        if len(calls) > 1:
            return httpx.Response(503, json={"error": "private upstream detail"})
        return httpx.Response(200, json=data)

    async def check():
        relay = module.MemoryRelay()
        relay.source = "http://memory-owner:8000"
        relay.token = "a" * 32
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            relay.client = client
            assert await relay.read() == data
            assert await relay.read() == data and len(calls) == 1
            relay.cache.clear()
            with pytest.raises(HTTPException) as failure:
                await relay.read()
            assert failure.value.status_code == 503 and relay.cache == {}
            assert "private upstream detail" not in failure.value.detail

    asyncio.run(check())
    with TestClient(module.app, base_url="http://localhost", client=("127.0.0.1", 12345)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/app.js").status_code == 200
        assert client.post("/api/dashboard/snapshot", json={}).status_code == 405
        assert client.get("/api/dashboard/vectors?limit=101").status_code == 422
        assert client.get("/api/dashboard/vectors?after=invalid").status_code == 422
        assert client.get("/health").status_code == 200


def test_dashboard_stream_reports_unavailable_and_event_cursor_reset(monkeypatch):
    import dashboard.backend.main as module

    async def unavailable(*args, **kwargs):
        raise HTTPException(503, "Memory owner unavailable")

    monkeypatch.setattr(module.relay, "read", unavailable)

    from starlette.requests import Request as HTTPRequest

    class Request(HTTPRequest):
        async def is_disconnected(self):
            return False

    async def check():
        stream = module.snapshot_events(Request({"type": "http", "scheme": "http", "path": "/api/dashboard/stream",
            "headers": [(b"host", b"localhost")], "client": ("127.0.0.1", 12345)}))
        chunk = await anext(stream)
        assert chunk.startswith("event: feed_error\n")
        assert "Memory owner unavailable" in chunk
        await stream.aclose()

    asyncio.run(check())

    async def live(*args, **kwargs):
        return dict(
            observations=dict(
                boot="newboot", sequence=2, events=[dict(id=1), dict(id=2)]
            ),
            receipts=[],
        )

    monkeypatch.setattr(module.relay, "read", live)
    with TestClient(module.app, base_url="http://localhost", client=("127.0.0.1", 12345)) as client:
        data = client.get("/api/dashboard/events?after=900&boot=oldboot").json()
        assert data["reset"] and len(data["events"]) == 2
        assert client.get("/api/dashboard/events?after=1&boot=newboot").json()[
            "events"
        ] == [dict(id=2)]


def test_independent_backend_reads_real_website_memory(connected_app, monkeypatch):
    import dashboard.backend.main as module
    from app.main import app as website_app

    client, _ = connected_app
    headers = user(client, "dashboard_relay")
    path = trip(client, headers)
    requirements(client, headers, path)
    grant = publish(monkeypatch, client, headers, path)
    relay = module.MemoryRelay()
    relay.source = "http://website"
    relay.token = grant["Authorization"][7:]
    monkeypatch.setattr(module, "relay", relay)

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=website_app)
        ) as source:
            relay.client = source
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=module.app),
                base_url="http://localhost",
            ) as dashboard:
                for resource in [
                    "snapshot",
                    "overview",
                    "agents",
                    "tiers",
                    "credentials",
                    "events",
                    "graph",
                    "shared-memory",
                    "vectors?include_values=true&limit=1",
                ]:
                    response = await dashboard.get("/api/dashboard/" + resource)
                    assert response.status_code == 200, (resource, response.text)
                data = (await dashboard.get("/api/dashboard/snapshot")).json()
                assert data["storage"]["memories"] > 0
                assert "NVIDIA_API_KEY" in str(data["credentials"])
                assert grant["Authorization"][7:] not in json.dumps(data)

    asyncio.run(check())
