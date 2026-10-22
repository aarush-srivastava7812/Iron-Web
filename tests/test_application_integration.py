"""Authenticated HTTP → real workflow → isolated FalkorDB/Qdrant integration.

The ordinary suite uses the repository's declared offline embedding fixture;
it does not replace graph/vector storage or the context compiler with mocks.
"""

from pathlib import Path
import sys
import uuid

import pytest

BACKEND = (
    Path(__file__).resolve().parents[1]
    / "stitch_ai_travel_booking_platform"
    / "backend"
)
sys.path.insert(0, str(BACKEND))


@pytest.fixture
def connected_app(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.db import Base, get_db
    from app.agent_runtime import AgentRuntime, get_agent_runtime
    from agents.memory_gateway.three_tier import application_context_runtime
    import seed

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "app.sqlite"),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(seed, "SessionLocal", sessions)
    monkeypatch.setattr(seed, "create_schema", lambda: None)
    seed.run()
    runtime = AgentRuntime(
        tmp_path / "memory",
        context_runtime=application_context_runtime(),
        namespace="test_app_" + uuid.uuid4().hex[:8],
    )

    def db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    client = TestClient(app)
    yield client, runtime
    app.dependency_overrides.clear()
    runtime.close()
    engine.dispose()


def user(client, name="traveler"):
    response = client.post(
        "/api/auth/register",
        json={
            "email": name + "@example.com",
            "username": name,
            "password": "integration-password",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return {"Authorization": "Bearer " + data["access_token"]}


def trip(client, headers):
    response = client.post("/api/assistant/conversations", json={}, headers=headers)
    assert response.status_code == 201
    return "/api/assistant/conversations/" + response.json()["id"]


def requirements(client, headers, path, **changes):
    body = dict(
        destination="Goa",
        start_date="2026-12-01",
        end_date="2026-12-05",
        budget=100000,
        currency="INR",
        traveller_count=2,
        pace="relaxed",
        dietary="vegetarian",
    )
    body.update(changes)
    response = client.put(path + "/requirements", headers=headers, json=body)
    assert response.status_code == 200, [
        e["receipt"]["error"]
        for e in client.get(path + "/memory-events", headers=headers).json()["events"]
    ]
    return response.json()


def plan(client, headers, path, content="Plan my trip"):
    response = client.post(
        path + "/messages", headers=headers, json={"content": content, "page": "plan"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_connected_plan_uses_current_memory_and_catalog(connected_app):
    client, _ = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path)
    response = plan(client, headers, path)
    assert response["connection_status"] == "agents_connected"
    result = response["orchestration"]
    assert result["status"] == "ok", result
    assert result["trip_brief"]["budget_total_inr"] == 100000
    assert result["budget"]["per_person"] is False
    assert (
        result["budget"]["total_inr"] >= result["itinerary"]["total_est_cost_inr"] * 2
    )
    assert result["itinerary"]["days"][1]["calendar_date"] == "2026-12-02"
    assert {r["agent_id"] for r in result["agent_results"]} >= {
        "stay_agent",
        "food_guide_agent",
        "itinerary_planner",
        "budget_booking_agent",
    }
    assert all(r["claim_ids"] for r in result["memory"])
    food = next(
        r for r in result["agent_results"] if r["agent_id"] == "food_guide_agent"
    )
    assert food["food_options"] and all(
        r["diet"] == "veg" for r in food["food_options"]
    )
    warm = plan(client, headers, path)["orchestration"]
    assert warm["status"] == "ok" and any(m["cache_hit"] for m in warm["memory"])
    changed = plan(client, headers, path, "Lower my budget to INR 80000")[
        "orchestration"
    ]
    assert changed["trip_brief"]["budget_total_inr"] == 80000
    events = client.get(path + "/memory-events", headers=headers).json()["events"]
    assert len(events) == 2  # agent repetitions are not promoted into facts


def test_authenticated_users_and_trips_are_isolated(connected_app):
    client, _ = connected_app
    owner, stranger = user(client), user(client, "stranger")
    first, second = trip(client, owner), trip(client, owner)
    requirements(client, owner, first)
    assert client.get(first + "/requirements", headers=stranger).status_code == 404
    assert (
        client.put(
            first + "/requirements", headers=stranger, json={"budget": 2}
        ).status_code
        == 404
    )
    assert (
        client.post(
            first + "/messages", headers=stranger, json={"content": "Plan my trip"}
        ).status_code
        == 404
    )
    assert client.get(first + "/memory-events", headers=stranger).status_code == 404
    assert (
        plan(client, owner, second)["orchestration"]["status"] == "needs_clarification"
    )
    assert (
        client.get(second + "/requirements", headers=owner).json()["required_issues"][
            "budget"
        ]
        == "missing"
    )
    assert (
        client.post(
            first + "/messages",
            headers=owner,
            json={"content": "Plan my trip", "user_id": "stranger"},
        ).status_code
        == 422
    )


def test_removal_does_not_restore_old_budget_and_trip_delete_forgets_sources(
    connected_app,
):
    client, runtime = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path)
    assert (
        client.put(
            path + "/requirements", headers=headers, json={"budget": 60000}
        ).status_code
        == 200
    )
    assert (
        client.delete(path + "/requirements/budget", headers=headers).status_code == 204
    )
    result = plan(client, headers, path)["orchestration"]
    assert result["status"] == "needs_clarification" and result.get("itinerary") is None
    assert (
        client.get(path + "/requirements", headers=headers).json()["required_issues"][
            "budget"
        ]
        != "supported"
    )
    traveler = next(iter(runtime.users.values()))
    ids = [
        e["receipt"]["id"] for e in traveler.events(path.rsplit("/", 1)[1])["events"]
    ]
    assert client.delete(path, headers=headers).status_code == 204
    assert all(
        traveler.service.receipt(traveler.principals["app_user"], eid)["status"]
        == "redacted"
        for eid in ids
    )


def test_mid_generation_change_discards_old_draft(connected_app, monkeypatch):
    from agents.memory_gateway.three_tier import ThreeTierGateway
    from app.schemas import TripRequirementsIn

    client, runtime = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path)
    original = ThreeTierGateway.validate_current
    changed = []

    def validate(gateway, **options):
        if not changed:
            changed.append(True)
            traveler = runtime.for_user(gateway.user_id)
            traveler.save_requirements(
                gateway.trip_id, TripRequirementsIn(budget=80000)
            )
        return original(gateway, **options)

    monkeypatch.setattr(ThreeTierGateway, "validate_current", validate)
    result = plan(client, headers, path)["orchestration"]
    assert changed and result["status"] == "ok", result
    assert result["trip_brief"]["budget_total_inr"] == 80000


def test_unsupported_rules_and_pending_updates_block_planning(connected_app):
    client, runtime = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path)
    walking = plan(client, headers, path, "Walking limit is 100 metres")[
        "orchestration"
    ]
    assert (
        walking["status"] == "needs_clarification"
        and "cannot verify" in walking["response"]
    )
    traveler = next(iter(runtime.users.values()))
    traveler.service.submit(
        traveler.principals["app_user"],
        dict(
            event_id="pending",
            text="Budget change",
            subject="Traveller",
            scope={"trip_id": path.rsplit("/", 1)[1]},
            confirmed=True,
            claims=[
                dict(
                    subject="Traveller",
                    predicate="budget",
                    value=20000,
                    kind="rule",
                    scope={"trip_id": path.rsplit("/", 1)[1]},
                )
            ],
        ),
    )
    assert plan(client, headers, path)["connection_status"] == "memory_pending"


def test_store_failure_saves_question_and_keeps_catalog_available(
    connected_app, monkeypatch
):
    client, runtime = connected_app
    headers = user(client)
    path = trip(client, headers)

    def unavailable(_):
        raise RuntimeError("test storage outage")

    monkeypatch.setattr(runtime, "for_user", unavailable)
    result = plan(client, headers, path)
    assert result["connection_status"] == "unavailable"
    assert result["orchestration"]["status"] == "unavailable"
    assert client.get("/api/stays").status_code == 200
    messages = client.get(path, headers=headers).json()["messages"]
    assert messages[0]["content"] == "Plan my trip"


def test_saved_profile_is_shared_across_trips_and_restart_preserves_trip(connected_app):
    client, runtime = connected_app
    headers = user(client)
    path = trip(client, headers)
    assert (
        client.patch(
            "/api/profile",
            headers=headers,
            json={"dietary_restrictions": ["vegetarian"], "travel_style": "relaxed"},
        ).status_code
        == 200
    )
    requirements(client, headers, path)
    assert plan(client, headers, path)["orchestration"]["status"] == "ok"
    second = trip(client, headers)
    packet = client.get(second + "/requirements", headers=headers).json()
    diet = next(f for f in packet["fields"] if f["predicate"] == "dietary")
    assert diet["status"] == "supported" and diet["location"] == "profile"
    runtime.close()
    assert (
        client.get(path + "/requirements", headers=headers).json()["status"] == "ready"
    )


def test_requirement_validation_and_insufficient_budget(connected_app):
    client, _ = connected_app
    headers = user(client)
    path = trip(client, headers)
    assert (
        client.put(
            path + "/requirements", headers=headers, json={"budget": True}
        ).status_code
        == 422
    )
    assert (
        client.put(
            path + "/requirements",
            headers=headers,
            json={"start_date": "2026-12-05", "end_date": "2026-12-01"},
        ).status_code
        == 422
    )
    requirements(client, headers, path, budget=1)
    result = plan(client, headers, path)["orchestration"]
    assert result["status"] == "needs_clarification" and result.get("itinerary") is None


def test_unknown_destination_does_not_recommend_another_city(connected_app):
    client, _ = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path, destination="No Such Destination")
    result = plan(client, headers, path)["orchestration"]
    assert result["status"] == "needs_clarification"
    assert (
        "no exact catalog match" in result["response"]
        and result.get("itinerary") is None
    )


def test_repeated_stale_contexts_stop_after_two_rebuilds(connected_app, monkeypatch):
    from agents.memory_gateway.three_tier import ThreeTierGateway

    client, _ = connected_app
    headers = user(client)
    path = trip(client, headers)
    requirements(client, headers, path)
    attempts = []

    def stale(_, **options):
        attempts.append(True)
        return False

    monkeypatch.setattr(ThreeTierGateway, "validate_current", stale)
    result = plan(client, headers, path)["orchestration"]
    assert len(attempts) == 3
    assert result["status"] == "context_changed" and result.get("itinerary") is None
