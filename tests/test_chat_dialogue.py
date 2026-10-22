"""Multi-turn dialogue, private state, protected edits and honest job recovery."""
# ruff: noqa: F811
import time
from threading import Event, Thread

from sqlalchemy import select

from tests.test_application_integration import connected_app, trip, user  # noqa: F401
from tests.test_tinyfish_chat import configure, send


def ready(client, headers, path):
    return send(client, headers, path, "Jaipur, 1 December 2026 for three days, two adults, INR 90000 total")["workspace"]


def test_contextual_answers_corrections_and_reload_preserve_scope(connected_app, monkeypatch):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "dialogue_context")
    path = trip(client, headers)
    for text, awaiting in [("Plan a trip to Agra", "start_date"), ("1 December 2026", "duration_days"),
                           ("three", "traveller_count"), ("two", "budget"), ("15k per person", None)]:
        answer = send(client, headers, path, text)
        assert answer["status"] == "ok", answer
        assert answer["awaiting"] == awaiting
        assert answer["reply"].count("?") <= 1
        if text == "Plan a trip to Agra":
            assert "Interests:" not in answer["reply"]
        if awaiting:
            reloaded = client.get(path+"/workspace", headers=headers).json()
            assert reloaded["dialogue"]["awaiting"] == awaiting
    work = answer["workspace"]
    assert work["draft"]["budget"] == 30000 and work["draft"]["traveller_count"] == 2
    assert "× 2" in answer["reply"] and "confirm" in answer["reply"].lower()
    assert not work["confirmed"] and not work["plan_ready"]
    corrected = send(client, headers, path, "Actually Jaipur instead of Agra")
    assert corrected["workspace"]["draft"]["destination"] == "Jaipur"
    assert corrected["workspace"]["draft"]["budget"] == 30000
    extended = send(client, headers, path, "Extend by two days")
    assert extended["workspace"]["draft"]["end_date"] == "2026-12-05"
    moved = send(client, headers, path, "Move my trip to 8 December 2026")
    assert moved["workspace"]["draft"]["end_date"] == "2026-12-12"
    returned = send(client, headers, path, "Return on 10 December 2026")
    assert returned["workspace"]["draft"]["duration_days"] == 3
    other_path = trip(client, headers)
    unscoped = send(client, headers, other_path, "two")
    assert not unscoped["workspace"]["draft"].get("traveller_count")
    other = user(client, "dialogue_other")
    assert client.get(path+"/workspace", headers=other).status_code == 404


def test_pending_budget_ambiguity_and_readonly_queries(connected_app, monkeypatch):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "dialogue_repairs")
    path = trip(client, headers)
    initial = send(client, headers, path, "Agra")["workspace"]
    ambiguous = send(client, headers, path, "Maybe Jaipur instead of Agra")
    assert ambiguous["status"] == "needs_clarification"
    assert ambiguous["workspace"]["revision"] == initial["revision"]
    assert ambiguous["suggestions"] == ["Set destination to Jaipur"]
    pending = send(client, headers, path, "INR 12000 per person")
    assert pending["awaiting"] == "traveller_count" and not pending["workspace"]["draft"].get("budget")
    totaled = send(client, headers, path, "two adults and one child")
    assert totaled["workspace"]["draft"]["budget"] == 36000
    resized = send(client, headers, path, "four adults")
    assert resized["workspace"]["draft"]["budget"] == 48000
    send(client, headers, path, "Set budget to INR 36000 total")
    totaled = send(client, headers, path, "three adults")
    assert totaled["workspace"]["draft"]["budget"] == 36000
    before = totaled["workspace"]
    for text in ("Show my trip summary", "Show my budget", "Show hotels in Jaipur", "Do not change my budget to INR 5000"):
        answer = send(client, headers, path, text)
        assert answer["workspace"]["revision"] == before["revision"], answer
        assert answer["workspace"]["draft"] == before["draft"]
    assert "spending limit" in send(client, headers, path, "What is my budget?")["reply"]
    about = send(client, headers, path, "Tell me about Agra")
    assert "Taj Mahal" in about["reply"] and "https://agra.nic.in/tourist-places/" in about["reply"]
    assert about["workspace"]["draft"] == before["draft"]
    compared = send(client, headers, path, "Compare Agra and Jaipur")
    assert "Agra —" in compared["reply"] and "Jaipur —" in compared["reply"]
    assert compared["workspace"]["revision"] == before["revision"]
    send(client, headers, path, "asdf")
    recovered = send(client, headers, path, "still asdf")
    assert "enter the fields directly" in recovered["reply"]


def test_mandatory_conditions_require_explicit_removal_confirmation(connected_app, monkeypatch):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "dialogue_protection")
    path = trip(client, headers)
    before = send(client, headers, path, "I have a peanut allergy and need wheelchair access")["workspace"]["draft"]
    assert before["hard_requirements"]
    assert send(client, headers, path, "yes")["workspace"]["draft"] == before
    asked = send(client, headers, path, "Remove my mandatory conditions")
    assert asked["awaiting"] == "clear_hard" and asked["workspace"]["draft"] == before
    kept = send(client, headers, path, "No, keep them")
    assert kept["workspace"]["draft"] == before
    send(client, headers, path, "Remove my mandatory conditions")
    updated = send(client, headers, path, "I must avoid stairs")["workspace"]["draft"]
    # The intervening turn dismisses the old confirmation; a plain yes cannot
    # clear a newly added condition.
    assert send(client, headers, path, "yes")["workspace"]["draft"] == updated
    asked = send(client, headers, path, "Remove my mandatory conditions")["workspace"]
    changed = dict(asked["draft"], hard_requirements=[*asked["draft"]["hard_requirements"], "Wheelchair accessible room"])
    edited = client.put(path+"/workspace", headers=headers, json={"expected_revision": asked["revision"], "draft": changed})
    assert edited.status_code == 200
    stale = send(client, headers, path, "yes")
    assert "changed after" in stale["reply"] and stale["workspace"]["draft"] == changed
    send(client, headers, path, "Remove my mandatory conditions")
    cleared = send(client, headers, path, "Yes, remove them")
    assert not cleared["workspace"]["draft"]["hard_requirements"]


def test_chat_status_does_not_wait_for_research_lock_or_repeat_paid_work(connected_app, monkeypatch):
    from app.db import get_db
    from app.main import app
    from app.planning_jobs import PlanningJob
    configure(monkeypatch)
    client, runtime = connected_app
    headers = user(client, "dialogue_jobs")
    path = trip(client, headers)
    work = ready(client, headers, path)
    identity = client.get("/api/auth/me", headers=headers).json()
    sessions = app.dependency_overrides[get_db]
    with next(sessions()) as db:
        db.add(PlanningJob(id="dialogue-running", user_id=identity["id"], conversation_id=work["conversation_id"],
                           status="running", kind="confirm", payload={}))
        db.commit()
    entered, released = Event(), Event()

    def research_holds_memory_lock():
        with runtime.for_user(identity["id"]).lock:
            entered.set()
            released.wait(10)

    thread = Thread(target=research_holds_memory_lock)
    thread.start()
    try:
        assert entered.wait(2)
        started = time.monotonic()
        answer = send(client, headers, path, "What is the progress?")
        assert time.monotonic()-started < 2
        assert answer["status"] == "research_running" and "still researching" in answer["reply"]
        assert answer["workspace"]["draft"] == work["draft"]
        refused = send(client, headers, path, "Set budget to INR 5000")
        assert refused["workspace"]["draft"] == work["draft"]
    finally:
        released.set()
        thread.join(5)
    with next(sessions()) as db:
        job = db.get(PlanningJob, "dialogue-running")
        job.status = "completed"
        job.result = {"orchestration": {"status": "failed", "agent_results": [
            {"agent_id": "food_guide_agent", "status": "failed", "errors": ["TinyFish research timed out"]}]}}
        db.commit()
    failure = send(client, headers, path, "Why did research fail?")
    assert "Restaurant research" in failure["reply"] and "timed out" in failure["reply"]
    assert "intact" in failure["reply"] and "provider credit" in failure["reply"]
    send(client, headers, path, "Retry research")
    with next(sessions()) as db:
        assert len(db.scalars(select(PlanningJob)).all()) == 1


def test_optional_preference_clear_reaches_memory_only_after_confirmation(connected_app, monkeypatch):
    configure(monkeypatch)
    client, _ = connected_app
    headers = user(client, "dialogue_forget")
    path = trip(client, headers)
    ready(client, headers, path)
    work = send(client, headers, path, "Vegetarian")["workspace"]

    def confirm(work):
        response = client.post(path+"/confirm", headers=headers, json={"expected_revision": work["revision"], "mode": "manual"})
        assert response.status_code == 200, response.text
        assert response.json()["orchestration"]["status"] == "ok", response.text

    confirm(work)
    changed = send(client, headers, path, "No dietary restrictions")["workspace"]
    assert not changed["draft"].get("dietary") and not changed["plan_ready"]
    prior = client.get(path+"/requirements", headers=headers).json()
    assert any(f["predicate"] == "dietary" and f["status"] == "supported" for f in prior["fields"])
    confirm(changed)
    after = client.get(path+"/requirements", headers=headers).json()
    assert not any(f["predicate"] == "dietary" and f["status"] == "supported" for f in after["fields"])
