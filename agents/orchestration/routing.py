"""Intent parsing and agent routing.

The page mapping comes from the architecture: each page has a fixed agent set,
and request keywords can add specialists. Only the needed agents run.
"""
from __future__ import annotations

import re

from agents.schemas import OrchestrationRequest

_PAGE_BASE_TASKS: dict[str, list[str]] = {
    "stays": ["trip_consultant", "stay_agent"],
    "tour_guide": ["trip_consultant", "tour_guide_agent"],
    "food_guide": ["trip_consultant", "food_guide_agent"],
    "explore": ["trip_consultant", "explore_agent"],
    "plan": ["trip_consultant", "explore_agent", "stay_agent", "tour_guide_agent",
             "food_guide_agent", "itinerary_planner", "budget_booking_agent"],
    "support": ["trip_consultant", "travel_support_agent"],
    "home": ["trip_consultant", "explore_agent"],
}

_BUDGET_WORDS = re.compile(r"\b(budget|cost|price|how much|afford|cheap|expensive)\b", re.IGNORECASE)
_BOOKING_WORDS = re.compile(r"\b(book|reserve|confirm|buy)\b", re.IGNORECASE)
_STAY_WORDS = re.compile(r"\b(hotel|stay|hostel|homestay|resort|room)\b", re.IGNORECASE)
_FOOD_WORDS = re.compile(r"\b(eat|food|restaurant|cafe|cuisine|lunch|dinner|breakfast)\b", re.IGNORECASE)
_SIGHTS_WORDS = re.compile(r"\b(see|visit|attraction|sightseeing|guide|tour|museum|temple)\b", re.IGNORECASE)
_DISCOVER_WORDS = re.compile(r"\b(suggest|ideas|where|recommend|explore|inspire)\b", re.IGNORECASE)
_ITINERARY_WORDS = re.compile(r"\b(itinerary|schedule|day by day|day-by-day|day wise)\b", re.IGNORECASE)
_SUPPORT_WORDS = re.compile(r"\b(pack|weather|cancel|change|delay|what to bring)\b", re.IGNORECASE)


def parse_intent(request: str) -> dict[str, bool]:
    text = request or ""
    return {
        "budget": bool(_BUDGET_WORDS.search(text)),
        "booking": bool(_BOOKING_WORDS.search(text)),
        "stays": bool(_STAY_WORDS.search(text)),
        "food": bool(_FOOD_WORDS.search(text)),
        "sights": bool(_SIGHTS_WORDS.search(text)),
        "discover": bool(_DISCOVER_WORDS.search(text)),
        "itinerary": bool(_ITINERARY_WORDS.search(text)),
        "support": bool(_SUPPORT_WORDS.search(text)),
    }


def plan_tasks(request: OrchestrationRequest) -> list[str]:
    """Agents to run for this request: page base set + intent-driven additions."""
    tasks = list(_PAGE_BASE_TASKS.get(request.page, _PAGE_BASE_TASKS["home"]))
    intent = parse_intent(request.request)

    def add(agent: str) -> None:
        if agent not in tasks:
            tasks.append(agent)

    if intent["stays"]:
        add("stay_agent")
    if intent["food"]:
        add("food_guide_agent")
    if intent["sights"]:
        add("tour_guide_agent")
    if intent["discover"]:
        add("explore_agent")
    if intent["budget"] or intent["itinerary"]:
        add("budget_booking_agent")
        if intent["itinerary"]:
            add("itinerary_planner")
    if intent["support"]:
        add("travel_support_agent")
    if request.confirmed_booking:
        add("budget_booking_agent")

    # Itinerary planning requires research results first; keep the dependency
    # ordering explicit for the graph.
    if "itinerary_planner" in tasks:
        for required in ("explore_agent", "stay_agent", "tour_guide_agent", "food_guide_agent"):
            add(required)
    return tasks
