import json

from agents.agentic import ToolAgent
from agents.schemas import AgentResult, TripBrief


def call(name, **arguments):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}


class ScriptedClient:
    def __init__(self, *turns):
        self.turns = iter(turns)
        self.requests = []

    def tool_turn(self, messages, tools, **sampling):
        self.requests.append((list(messages), tools, sampling))
        return next(self.turns)


def test_agent_must_execute_tool_and_observe_before_finishing():
    client = ScriptedClient(call("finish", summary="Pretend finished"), call("inspect_brief"),
                            call("finish", summary="Inspected confirmed brief"))
    executions = []
    def inspect():
        executions.append(True)
        return AgentResult(agent_id="trip_consultant", status="ok", summary="Actual inspection")
    result = ToolAgent("trip_consultant", client=client).run(inspect, brief=TripBrief(destination="Goa"))
    assert executions == [True]
    assert result.execution.completed
    assert result.summary == "Actual inspection"
    assert any("successful role tool" in o for o in result.execution.observations)
    assert all(0 < r[2]["temperature"] < 1 for r in client.requests)


def test_invalid_model_candidate_is_rejected_then_agent_can_repair():
    from agents.stay_agent import StayAgent
    from agents.travel_tools.base import MockTravelBackend, using_backend
    client = ScriptedClient(call("compare_stays", limit=3), call("finish", summary="Invalid selection", selected_indices=[99]),
                            call("finish", summary="Selected observed lodging", selected_indices=[1, 0]))
    with using_backend(MockTravelBackend()):
        options = StayAgent().search(TripBrief(destination="Goa"), destination_id=1)
        result = ToolAgent("stay_agent", client=client).run(
            lambda **_: options.model_copy(deep=True), brief=TripBrief(destination="Goa"))
    assert result.status == "ok"
    assert result.stay_options[0].stay_id == options.stay_options[1].stay_id
    assert len(result.stay_options) == 2
    assert any("observed candidates" in o for o in result.execution.observations)


def test_provider_failure_never_masquerades_as_offline_agent_success():
    client = ScriptedClient()
    result = ToolAgent("food_guide_agent", client=client).run(lambda **_: None)
    assert result.status == "failed"
    assert not result.execution.completed
    assert result.execution.mode == "nvidia"
    assert result.food_options == []


def test_planner_requires_validation_before_finish():
    from agents.itinerary_planner import ItineraryPlanner
    client = ScriptedClient(call("build_schedule"), call("finish", summary="Unreviewed"),
                            call("review_schedule"), call("finish", summary="Reviewed itinerary"))
    brief = TripBrief(destination="Goa", duration_days=2)
    result = ToolAgent("itinerary_planner", client=client).run(
        lambda **kw: ItineraryPlanner().draft(brief, **kw), brief=brief,
        planner_inputs={"attractions": [], "food_options": [], "stay_options": []})
    assert result.status == "ok"
    assert "review_schedule" in result.execution.tool_calls
    assert any("review_schedule" in o for o in result.execution.observations)


def test_provider_actions_use_nonzero_sampling_without_a_seed_and_real_work_log(monkeypatch):
    import httpx
    from agents.config import settings
    from agents.resource_manager.model_registry import NimClient
    captured = []
    def provider(request):
        payload = json.loads(request.content)
        captured.append(payload)
        return httpx.Response(200, json={"choices":[{"message":{"content":json.dumps(
            {"tool":"inspect_brief","arguments":{}})}}]})
    monkeypatch.setattr(settings, "nvidia_api_key", "test-only")
    monkeypatch.setattr(settings, "nim_agent_protocol", "json")
    client = NimClient()
    client._client = httpx.Client(base_url="https://provider.invalid/v1", transport=httpx.MockTransport(provider))
    try:
        for temperature in [0.35, 0.85]:
            message = client.tool_turn([{"role":"system","content":"Inspect confirmed data."},
                                        {"role":"user","content":"Confirmed Goa trip"}], [], temperature=temperature)
            assert message["tool_calls"][0]["function"]["name"] == "inspect_brief"
        assert [p["temperature"] for p in captured] == [0.35, 0.85]
        assert all("seed" not in p and "top_p" not in p for p in captured)
        assert all("working_history" in p["messages"][1]["content"] for p in captured)
    finally:
        client.close()


def test_small_catalog_does_not_repeat_and_recharge_the_same_experience():
    from agents.itinerary_planner import ItineraryPlanner
    from agents.tour_guide_agent import TourGuideAgent
    from agents.travel_tools.base import MockTravelBackend, using_backend
    brief = TripBrief(destination="Goa", duration_days=4)
    with using_backend(MockTravelBackend()):
        experiences = TourGuideAgent().recommend(brief, destination_id=1).attractions
    result = ItineraryPlanner().draft(brief, attractions=experiences)
    paid = [s for d in result.itinerary.days for s in d.stops if s.kind == "attraction"]
    assert len(paid) == len({s.title for s in paid}) == 1
    assert result.itinerary.total_est_cost_inr == experiences[0].price_per_person_inr
    assert any(s.kind == "buffer" for d in result.itinerary.days for s in d.stops)
