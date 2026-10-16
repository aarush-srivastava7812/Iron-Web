"""Orchestration routing: only required agents run for a request."""
from __future__ import annotations

from agents.orchestration.routing import parse_intent, plan_tasks
from agents.schemas import OrchestrationRequest


def _req(page: str, request: str) -> OrchestrationRequest:
    return OrchestrationRequest(request=request, user_id="u1", session_id="s1", page=page)  # type: ignore[arg-type]


def test_page_base_tasks_match_architecture_mapping():
    assert set(plan_tasks(_req("stays", "hotels in Goa"))) == {"trip_consultant", "stay_agent"}
    assert set(plan_tasks(_req("tour_guide", "what to see"))) == {"trip_consultant", "tour_guide_agent"}
    # The architecture allows Explore on the food page for discovery of local
    # areas; stays/itinerary must never run there.
    food_tasks = plan_tasks(_req("food_guide", "where to eat"))
    assert {"trip_consultant", "food_guide_agent"} <= set(food_tasks)
    assert "stay_agent" not in food_tasks and "itinerary_planner" not in food_tasks
    assert "explore_agent" in plan_tasks(_req("explore", "inspire me"))
    support = plan_tasks(_req("support", "what should I pack"))
    assert "travel_support_agent" in support
    assert "food_guide_agent" not in support


def test_plan_page_runs_full_pipeline_with_dependencies():
    tasks = plan_tasks(_req("plan", "plan a 3 day trip to Manali for 2 with a budget of 60k"))
    for expected in ("trip_consultant", "explore_agent", "stay_agent", "tour_guide_agent",
                     "food_guide_agent", "itinerary_planner", "budget_booking_agent"):
        assert expected in tasks


def test_intent_adds_only_relevant_specialists():
    tasks = plan_tasks(_req("home", "find me food places in Kochi"))
    assert "food_guide_agent" in tasks
    assert "stay_agent" not in tasks
    assert "itinerary_planner" not in tasks


def test_itinerary_adds_research_dependencies():
    tasks = plan_tasks(_req("home", "make me a day by day itinerary"))
    assert "itinerary_planner" in tasks
    assert {"explore_agent", "stay_agent", "tour_guide_agent", "food_guide_agent"} <= set(tasks)


def test_intent_flags():
    intent = parse_intent("book a hotel and check the budget, maybe change my plans")
    assert intent["booking"] and intent["stays"] and intent["budget"] and intent["support"]
    assert not intent["food"]
