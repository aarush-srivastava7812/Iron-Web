"""LangGraph workflow: conditional execution, parallel merge, e2e planning."""
from __future__ import annotations

import uuid

from agents.orchestration.graph import TravelWorkflow
from agents.schemas import OrchestrationRequest
from agents.travel_tools.base import set_backend


def _run(page: str, request: str, **kwargs) -> dict:
    workflow = TravelWorkflow()
    from agents.travel_tools.base import MockTravelBackend
    set_backend(MockTravelBackend())
    # Unique session per call so the checkpointer never replays another test's state.
    kwargs.setdefault("session_id", f"session-{uuid.uuid4().hex[:8]}")
    return workflow.run(OrchestrationRequest(
        request=request, user_id=kwargs.pop("user_id", "user-e2e"),
        session_id=kwargs.pop("session_id", "session-e2e"),
        page=page,  # type: ignore[arg-type]
        **kwargs,
    ))


def test_clarification_for_vague_request():
    final = _run("home", "I want a holiday somewhere")
    assert final["status"] == "needs_clarification"
    assert final["response"] == final["clarification_question"]


def test_stays_page_runs_only_needed_agents():
    final = _run("stays", "Find a hotel in Goa for 2 people, 3 days, budget 40k")
    ran = {r.agent_id for r in final["agent_results"] if r.status != "skipped"}
    assert "stay_agent" in ran
    assert "food_guide_agent" not in ran
    assert "itinerary_planner" not in ran


def test_food_page_runs_food_agent_only():
    final = _run("food_guide", "vegetarian food places in Kochi")
    ran = {r.agent_id for r in final["agent_results"]}
    assert "food_guide_agent" in ran
    assert "stay_agent" not in ran
    assert "itinerary_planner" not in ran
    assert final["status"] == "ok"


def test_plan_page_end_to_end_produces_itinerary_and_budget():
    final = _run("plan", "Plan a 3 day trip to Goa for 2 people with a budget of 50k, relaxed pace")
    assert final["status"] == "ok", final.get("errors")
    ran = {r.agent_id for r in final["agent_results"]}
    assert {"trip_consultant", "explore_agent", "stay_agent", "tour_guide_agent",
            "food_guide_agent", "itinerary_planner", "budget_booking_agent"} <= ran
    itinerary = final.get("itinerary")
    assert itinerary is not None and len(itinerary.days) == 3
    budget = final.get("budget")
    assert budget is not None and budget.total_inr > 0
    assert budget.status == "estimate"
    assert final["response"], "a synthesized response is expected"


def test_plan_workflow_persists_decision_memory():
    final = _run("plan", "Plan a 2 day trip to Munnar for 2 with budget 30k",
                 user_id="user-persist", session_id="session-persist")
    assert final["status"] == "ok"
    proposals = final.get("write_proposals", [])
    assert any(p.kind == "decision" for p in proposals)
    # The memory should now be retrievable for that user.
    context = final["memory_context"]
    assert context is not None and context.user_id == "user-persist"


def test_confirmed_booking_reports_pending_not_confirmed():
    final = _run("plan", "Confirm the Goa trip booking for 2026-12-01 to 2026-12-03",
                 confirmed_booking=True)
    booking_results = [r for r in final["agent_results"] if r.agent_id == "budget_booking_agent"]
    assert booking_results, "booking flow should run"
    # Mock provider returns a simulated *pending* request, never a confirmation.
    assert booking_results[0].budget is None or booking_results[0].budget.status != "confirmed"


def test_parallel_results_merge_without_duplicates():
    final = _run("plan", "Plan a 2 day trip to Varanasi for 2 with budget 20k")
    agent_ids = [r.agent_id for r in final["agent_results"]]
    assert len(agent_ids) == len(set(agent_ids)), "reducer must merge by agent id"
