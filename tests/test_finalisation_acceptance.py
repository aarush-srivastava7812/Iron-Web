"""Current-state checks across website HTTP and its actual dashboard inspection."""
from tests.test_application_integration import connected_app, plan, requirements, trip, user  # noqa: F401
from tests.test_memory_dashboard import publish


def test_budget_change_invalidates_old_context_and_rebuilds_current_plan(connected_app, monkeypatch):  # noqa: F811
    from agents.config import settings
    monkeypatch.setattr(settings, "agent_mode", "offline")
    client, runtime = connected_app
    owner = user(client, "budget_acceptance")
    path = trip(client, owner)
    requirements(client, owner, path)
    assert plan(client, owner, path)["orchestration"]["status"] == "ok"
    traveler = next(iter(runtime.users.values()))
    request = dict(subject="Traveller", scope={"trip_id":path.rsplit("/", 1)[1]}, task_type="itinerary")
    packet = traveler.service.context(traveler.principals["travel_orchestrator"], **request)
    assert client.put(path + "/requirements", headers=owner, json={"budget":80000}).status_code == 200
    assert not traveler.service.validate_context(traveler.principals["travel_orchestrator"], packet["context_token"])["valid"]
    assert client.get(path + "/plan", headers=owner).json()["stale"]
    grant = publish(monkeypatch, client, owner, path)
    inspected = client.get("/api/dashboard/snapshot", headers=grant).json()
    assert inspected["tiers"]["captured_contexts"] == []
    assert any(c["lifecycle_status"] == "superseded" for c in inspected["shared_memory"]["claims"])
    revised = plan(client, owner, path)["orchestration"]
    assert revised["status"] == "ok" and revised["trip_brief"]["budget_total_inr"] == 80000
    assert not client.get(path + "/plan", headers=owner).json()["stale"]


def test_conflict_forget_replay_and_isolation_in_website_and_dashboard(connected_app, monkeypatch):  # noqa: F811
    client, runtime = connected_app
    owner = user(client, "conflict_acceptance")
    other = user(client, "conflict_stranger")
    path = trip(client, owner)
    requirements(client, owner, path)
    assert client.patch("/api/profile", headers=owner, json={"dietary_restrictions":["no nuts"]}).status_code == 200
    current = client.get(path + "/requirements", headers=owner).json()
    assert current["status"] == "needs_information" and current["required_issues"]["dietary"] == "scope_conflict"
    grant = publish(monkeypatch, client, owner, path)
    snapshot = client.get("/api/dashboard/snapshot", headers=grant).json()
    values = [c["properties"].get("value_json", "") for c in snapshot["shared_memory"]["claims"]]
    assert any("no nuts" in v for v in values) and any("vegetarian" in v for v in values)
    for suffix in ["/requirements", "/dashboard", "/memory-events", "/plan"]:
        assert client.get(path + suffix, headers=other).status_code == 404
    assert client.get("/api/dashboard/snapshot", headers=other).status_code == 401
    traveler = runtime.for_user(next(iter(runtime.users)))
    # Use the existing immutable source-event API to retain the exact original
    # envelope for replay; the HTTP website exposes forgetting, not event-ID injection.
    actor = traveler.principals["app_user"]
    payload = dict(event_id="finalisation-forget", text="Remember quiet gardens", confirmed=True,
                   subject="Traveller", scope={"trip_id":path.rsplit("/", 1)[1]}, session_id=path.rsplit("/", 1)[1],
                   claims=[dict(subject="Traveller", predicate="interests", value=["quiet gardens"],
                                kind="preference", scope={"trip_id":path.rsplit("/", 1)[1]})])
    traveler.service.submit(actor, payload)
    while traveler.service.process_one():
        pass
    receipt = traveler.service.receipt(actor, payload["event_id"])
    assert receipt["status"] == "ready"
    assert client.delete(path + "/memory-events/" + payload["event_id"], headers=owner).status_code == 204
    assert traveler.service.submit(actor, payload)["status"] == "redacted"
    assert traveler.service.engine(traveler.user_id).get(receipt["memory_id"]) is None
    inspected = client.get("/api/dashboard/snapshot", headers=grant).json()
    assert inspected["tiers"]["captured_contexts"] == []
    assert not any("quiet gardens" in str(c) for c in inspected["shared_memory"]["claims"])
    assert not any("quiet gardens" in str(c) for c in inspected["vectors"]["points"])
