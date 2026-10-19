"""Provider contracts plus authenticated real graph/vector workflow coverage."""
# ruff: noqa: F811 -- Imported pytest fixture is resolved by parameter name.
import json
from datetime import date

import httpx
import pytest

from agents.config import settings
from agents.schemas import TripBrief
from agents.tinyfish import (
    RESEARCH_ROLES, ResearchOutput, TinyFishClient, TinyFishError,
    TinyFishResearchAgent, public_url,
)
from tests.test_application_integration import connected_app, plan, requirements, trip, user  # noqa: F401


def item(name="Web hotel", **changes):
    return dict(name=name, source_url="https://example.com/" + name.replace(" ", "-"),
                location="Goa", description="Public destination finding", price_inr=2000,
                price_basis="per_room_night", currency="INR", dietary="vegetarian",
                price_note="Indicative rate; confirm dates and opening hours", **changes)


def output(*items):
    return {"destination": "Goa", "items": list(items) or [item()]}


def brief(**changes):
    return TripBrief(destination="Goa", start_date=date(2026, 12, 1), end_date=date(2026, 12, 3),
                     duration_days=3, party_size=2, budget_total_inr=50000, **changes)


class ResearchClient:
    def __init__(self, body):
        self.body, self.requests = body, []

    def research(self, url, goal):
        self.requests.append((url, goal))
        return "test-run", ResearchOutput.model_validate(self.body)


def test_async_client_checks_run_and_goal_success(monkeypatch):
    monkeypatch.setattr(settings, "tinyfish_api_key", "test-only")
    requests = []
    responses = iter([{"run_id": "run-123"}, {"status": "RUNNING"},
                      {"status": "COMPLETED", "result": output()}])

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=next(responses))

    with httpx.Client(base_url="https://provider.invalid", transport=httpx.MockTransport(handler)) as http:
        run_id, result = TinyFishClient(client=http, sleep=lambda _: None).research("https://example.com", "Public research")
    assert run_id == "run-123" and result.items[0].price_inr == 2000
    assert [r.method for r in requests] == ["POST", "GET", "GET"]
    payload = json.loads(requests[0].content)
    assert "output_schema" in payload
    assert "additionalProperties" not in json.dumps(payload["output_schema"])


@pytest.mark.parametrize("payload", [
    {"status": "FAILED", "error": {"message": "private upstream details"}},
    {"status": "COMPLETED", "result": {"error": "Could not research"}},
    {"status": "COMPLETED", "result": {"destination": "Goa", "items": []}},
    {"status": "COMPLETED", "result": None},
    {"status": "UNRECOGNIZED"},
])
def test_completed_is_not_automatically_usable(monkeypatch, payload):
    monkeypatch.setattr(settings, "tinyfish_api_key", "test-only")
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=({"run_id": "abc"} if request.url.path.endswith("run-async") else
                                        {} if request.url.path.endswith("cancel") else payload))

    with httpx.Client(base_url="https://provider.invalid", transport=httpx.MockTransport(handler)) as http:
        with pytest.raises((TinyFishError, ValueError)):
            TinyFishClient(client=http).research("https://example.com", "Research")
    assert seen[-1].endswith("/abc/cancel")


def test_timeout_cancels_without_creating_duplicate_runs(monkeypatch):
    monkeypatch.setattr(settings, "tinyfish_api_key", "test-only")
    now, methods = [0.0], []

    def handler(request):
        methods.append(request.url.path)
        return httpx.Response(200, json={"run_id": "abc"} if request.url.path.endswith("run-async") else {"status": "RUNNING"})

    def advance(seconds):
        now[0] += seconds

    with httpx.Client(base_url="https://provider.invalid", transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(TinyFishError, match="timed out"):
            TinyFishClient(client=http, timeout=2, clock=lambda: now[0], sleep=advance).research("https://example.com", "Research")
    assert methods.count("/v1/automation/run-async") == 1
    assert methods[-1] == "/v1/runs/abc/cancel"


def test_transient_poll_failure_recovers_without_duplicate_research(monkeypatch):
    monkeypatch.setattr(settings, "tinyfish_api_key", "test-only")
    seen, polls = [], [0]

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json={"run_id": "abc"})
        polls[0] += 1
        if polls[0] == 1:
            raise httpx.ReadTimeout("Temporary status request timeout", request=request)
        if polls[0] == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"status": "COMPLETED", "result": output()})

    with httpx.Client(base_url="https://provider.invalid", transport=httpx.MockTransport(handler)) as http:
        run, _ = TinyFishClient(client=http, sleep=lambda _: None).research("https://example.com", "Public research")
    assert run == "abc"
    assert [method for method, _ in seen].count("POST") == 1


def test_provider_auth_error_does_not_expose_response_or_key(monkeypatch):
    monkeypatch.setattr(settings, "tinyfish_api_key", "secret-test-key")
    with httpx.Client(base_url="https://provider.invalid", transport=httpx.MockTransport(
            lambda _: httpx.Response(401, text="secret-test-key upstream details"))) as http:
        with pytest.raises(TinyFishError, match="HTTP 401") as error:
            TinyFishClient(client=http).research("https://example.com", "Public research")
    assert "secret-test-key" not in str(error.value)


def test_missing_key_is_an_explicit_failure_without_catalog_fallback(monkeypatch):
    monkeypatch.setattr(settings, "tinyfish_api_key", "")
    result = TinyFishResearchAgent("stay_agent").run(brief())
    assert result.status == "failed" and not result.stay_options
    assert "TINYFISH_API_KEY" in result.summary
    assert result.execution.mode == "tinyfish" and not result.execution.completed


def test_cached_public_research_retains_source_time_and_needs_no_new_run(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "tinyfish_api_key", "test-only")
    monkeypatch.setattr(settings, "tinyfish_cache_path", str(tmp_path))
    first = TinyFishClient()
    first.remember("https://example.com", "Public city research", "abc", output())
    stamp = first.retrieved_at
    with httpx.Client(base_url="https://provider.invalid", transport=httpx.MockTransport(
            lambda _: pytest.fail("Cache hit must not create another run"))) as http:
        client = TinyFishClient(client=http)
        run, result = client.research("https://example.com", "Public city research")
    assert run == "abc" and result.items
    assert client.cache_hit and client.retrieved_at == stamp


def test_city_qualifiers_and_extra_items_preserve_bounded_valid_research():
    from agents.tinyfish import validated_output
    data = [item("Hotel " + str(i)) for i in range(8)]
    for row in data:
        row["location"] = "Goa, India"
    normalized = validated_output(output(*data))
    assert len(normalized.items) == 5
    client = ResearchClient(output(*data))
    client.body["destination"] = "Goa, a coastal destination in India"
    result = TinyFishResearchAgent("stay_agent", client=client).run(brief())
    assert result.status == "ok"


@pytest.mark.parametrize("url", ["http://example.com", "https://localhost/a", "https://127.0.0.1/a",
                                 "https://10.0.0.1/a", "javascript:alert(1)", "https://user:secret@example.com"])
def test_nonpublic_sources_rejected(url):
    with pytest.raises(ValueError):
        public_url(url)


@pytest.mark.parametrize("agent_id,basis", [("explore_agent", "unknown"), ("stay_agent", "per_room_night"),
                                          ("food_guide_agent", "per_guest_meal"), ("tour_guide_agent", "per_guest_visit")])
def test_results_have_sources_and_never_fabricate_catalog_ids(agent_id, basis):
    data = item()
    data["price_basis"] = basis
    client = ResearchClient(output(data))
    result = TinyFishResearchAgent(agent_id, client=client).run(brief(dietary_requirements=["vegetarian"]))
    assert result.status == "ok", result
    assert result.execution.completed and result.execution.mode == "tinyfish"
    option = getattr(result, RESEARCH_ROLES[agent_id][2])[0]
    assert option.evidence.ref.startswith("https://")
    for key in ("stay_id", "place_id", "guide_id", "destination_id"):
        assert getattr(option, key, None) is None
    goal = client.requests[0][1]
    assert "2026-12-01" not in goal and "50000" not in goal and "party_size" not in goal
    assert "dietary_requirements" not in goal


@pytest.mark.parametrize("changes", [
    {"price_inr": None}, {"price_inr": -1}, {"price_inr": True},
    {"price_basis": "unknown"}, {"currency": "unknown"}, {"dietary": "unknown"},
    {"location": "Jaipur"}, {"source_url": "javascript:alert(1)"},
])
def test_invalid_food_evidence_never_enters_a_plan(changes):
    data = item()
    data["price_basis"] = "per_guest_meal"
    data.update(changes)
    result = TinyFishResearchAgent("food_guide_agent", client=ResearchClient(output(data))).run(
        brief(dietary_requirements=["vegetarian"]))
    assert result.status == "failed" and not result.food_options


def test_authenticated_memory_workflow_saves_web_plan_and_edits_external_stay(connected_app, monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tinyfish")
    captured = []

    def research(self, url, goal):
        captured.append((url, goal))
        if goal.startswith("Research hotels"):
            items = [item(), item("Second web hotel")]
            items[1]["price_inr"] = 3000
            items[1]["source_url"] = items[0]["source_url"]
        elif goal.startswith("Research restaurants"):
            data = item("Web vegetarian restaurant")
            data.update(price_basis="per_guest_meal", price_inr=300)
            items = [data]
        elif goal.startswith("Research attractions"):
            data = item("Web attraction")
            data.update(price_basis="per_guest_visit", price_inr=100)
            items = [data]
        else:
            items = [item("Goa")]
        return "test-run", ResearchOutput.model_validate(output(*items))

    monkeypatch.setattr(TinyFishClient, "research", research)
    client, _ = connected_app
    headers = user(client, "tinyfish_traveler")
    path = trip(client, headers)
    assert client.get(path + "/workspace", headers=headers).status_code == 200
    requirements(client, headers, path, end_date="2026-12-03")
    result = plan(client, headers, path)["orchestration"]
    assert result["status"] == "ok", [(r["agent_id"], r["status"], r["summary"], r["errors"]) for r in result["agent_results"]]
    assert result["trip_brief"]["budget_total_inr"] == 100000
    assert all(m["claim_ids"] for m in result["memory"])
    assert {r["execution"]["mode"] for r in result["agent_results"]} == {"tinyfish", "local"}
    assert len(captured) == 4
    assert all("2026-12-01" not in goal and "100000" not in goal and "tinyfish_traveler" not in goal for _, goal in captured)
    saved = client.get(path + "/plan", headers=headers).json()
    assert saved["plan"]["selected_stay_id"] is None
    assert saved["plan"]["selected_stay_ref"] == 'web:["https://example.com/Web-hotel","Web hotel"]'
    changed = client.post(path + "/plan/edits", headers=headers,
                          json={"expected_version": saved["version"], "action": "stay", "candidate": 1})
    assert changed.status_code == 200, changed.text
    updated = changed.json()["plan"]
    assert updated["selected_stay_ref"] == 'web:["https://example.com/Web-hotel","Second web hotel"]'
    assert updated["budget"]["total_inr"] - saved["plan"]["budget"]["total_inr"] == 2200
    book = client.get(path + "/travel-book", headers=headers)
    assert book.status_code == 200, book.text
    assert book.json()["stay"]["name"] == "Second web hotel"
    assert book.json()["stay"]["source_url"] == "https://example.com/Web-hotel"
    assert "indicative" in book.json()["notice"]
    assert len(client.get(path + "/memory-events", headers=headers).json()["events"]) == 1
    other = user(client, "tinyfish_other")
    assert client.get(path + "/plan", headers=other).status_code == 404
    stale = client.put(path + "/requirements", headers=headers, json={"budget": 90000})
    assert stale.status_code == 200
    assert client.get(path + "/plan", headers=headers).json()["stale"]


def test_expired_memory_with_failed_research_does_not_repeat_paid_work(connected_app, monkeypatch):
    monkeypatch.setattr(settings, "agent_mode", "tinyfish")
    client, runtime = connected_app
    headers = user(client, "expired_tinyfish")
    path = trip(client, headers)
    requirements(client, headers, path)
    traveler = runtime.for_user(client.get("/api/auth/me", headers=headers).json()["id"])
    access = traveler.service.context_access
    clock = [access.clock()]
    monkeypatch.setattr(access, "clock", lambda: clock[0])
    calls = []

    def stopped(self, url, goal):
        calls.append(url)
        if len(calls) == 1:
            clock[0] += 301
        raise TinyFishError("Research timed out")

    monkeypatch.setattr(TinyFishClient, "research", stopped)
    result = plan(client, headers, path)["orchestration"]
    assert result["status"] == "failed" and result["itinerary"] is None
    assert len(calls) == 4
    assert client.get(path + "/plan", headers=headers).json() is None
def test_provider_submission_is_bounded_before_execution_timeout(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    import time
    from agents.config import settings
    from agents.tinyfish import TinyFishClient

    monkeypatch.setattr(settings, "tinyfish_api_key", "test-key")
    monkeypatch.setattr(settings, "tinyfish_cache_path", "")
    gate = Lock()
    current, peak = 0, 0

    def execute(self, url, goal):
        nonlocal current, peak
        with gate:
            current += 1
            peak = max(peak, current)
        time.sleep(0.05)
        with gate:
            current -= 1
        return goal

    monkeypatch.setattr(TinyFishClient, "_execute", execute)
    with ThreadPoolExecutor(max_workers=4) as executor:
        result = list(executor.map(lambda i: TinyFishClient().research("https://example.com", str(i)), range(4)))
    assert result == ["0", "1", "2", "3"] and peak == 2 and current == 0
