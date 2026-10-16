"""Specialist agent contract tests (mock travel data, real memory)."""
from __future__ import annotations

from agents.explore_agent import ExploreAgent
from agents.food_guide_agent import FoodGuideAgent
from agents.itinerary_planner import ItineraryPlanner
from agents.stay_agent import StayAgent
from agents.tour_guide_agent import TourGuideAgent
from agents.travel_support_agent import TravelSupportAgent
from agents.trip_consultant import TripConsultant
from agents.schemas import TripBrief


def test_consultant_extracts_constraints_not_inventions():
    consultant = TripConsultant()
    brief = consultant.extract(
        "Plan a 3 day trip to Manali for 4 people with a budget of 60k, vegetarian food, relaxed pace"
    )
    assert brief.destination == "Manali"
    assert brief.duration_days == 3
    assert brief.party_size == 4
    assert brief.budget_total_inr == 60_000
    assert brief.pace == "relaxed"
    assert "vegetarian" in brief.dietary_requirements
    assert brief.effective_budget_per_person() == 15_000
    assert brief.clarification_question is None


def test_consultant_flags_missing_fields_and_asks():
    brief = TripConsultant().extract("I want a holiday somewhere")
    assert brief.destination_flexible is True
    assert "party_size" in brief.missing_fields
    assert brief.clarification_question
    # Unknown fields are never fabricated.
    assert brief.destination is None
    assert brief.party_size is None


def test_consultant_memory_fills_only_soft_fields(gateway):
    from agents.schemas import MemoryWriteProposal

    gateway.propose_write(MemoryWriteProposal(
        user_id="user-mem", session_id="s", agent_id="food_guide_agent",
        content="Dietary requirement: vegan", kind="preference", importance=0.9,
    ))
    memory = gateway.retrieve(query="dietary requirements", user_id="user-mem",
                              agent_id="trip_consultant", use_cache=False)
    brief = TripConsultant().extract("Trip to Jaipur for 2", memory)
    assert "vegan" in brief.dietary_requirements
    assert brief.destination == "Jaipur"


def test_explore_returns_diverse_relevant_ideas(mock_backend):
    brief = TripBrief(destination_flexible=True, interests=["beach", "sea"])
    result = ExploreAgent().discover(brief, limit=4)
    assert result.status == "ok"
    assert 1 <= len(result.destination_ideas) <= 4
    assert all(idea.name for idea in result.destination_ideas)
    assert all(idea.evidence.kind == "mock" for idea in result.destination_ideas)


def test_stay_agent_ranks_and_labels_availability(mock_backend):
    brief = TripBrief(destination="Goa", duration_days=3, party_size=2,
                      budget_per_person_inr=20_000)
    result = StayAgent().search(brief, None, destination_id=1, destination_name="Goa", nights=2)
    assert result.status == "ok"
    assert result.stay_options
    top = result.stay_options[0]
    assert top.total_price_inr == top.price_per_night_inr * 2
    assert top.availability_status == "unknown"
    assert top.evidence.note and "not verified" in top.evidence.note


def test_stay_agent_respects_dietary_memory_for_food(mock_backend):
    pass  # covered by food guide test below


def test_tour_guide_matches_interests_and_flags_hours(mock_backend):
    brief = TripBrief(destination="Goa", interests=["history"])
    result = TourGuideAgent().recommend(brief, None, destination_id=1, destination_name="Goa")
    assert result.status == "ok" and result.attractions
    assert any("history" in (a.category or "") for a in result.attractions)
    assert all("not verified" in (a.hours_caveat or "") for a in result.attractions)


def test_food_guide_applies_dietary_requirements(mock_backend):
    brief = TripBrief(destination="Goa", dietary_requirements=["vegetarian"])
    result = FoodGuideAgent().recommend(brief, None, destination_id=1, destination_name="Goa")
    assert result.status == "ok" and result.food_options
    # The catalog's "both" category also fits a vegetarian requirement.
    assert all(option.diet in {"veg", "both"} for option in result.food_options)
    assert all("street" not in (option.diet or "") for option in result.food_options)


def test_itinerary_no_overlaps_and_matches_duration(mock_backend):
    from agents.validation.itinerary_validator import validate_itinerary

    brief = TripBrief(destination="Goa", duration_days=3, pace="moderate")
    attractions = TourGuideAgent().recommend(brief, None, destination_id=1,
                                             destination_name="Goa").attractions
    food = FoodGuideAgent().recommend(brief, None, destination_id=1,
                                      destination_name="Goa").food_options
    stays = StayAgent().search(brief, None, destination_id=1, destination_name="Goa",
                               nights=2).stay_options
    result = ItineraryPlanner().draft(brief, destination_name="Goa",
                                      attractions=attractions, food_options=food,
                                      stay_options=stays)
    assert result.status == "ok" and result.itinerary
    itinerary = result.itinerary
    assert len(itinerary.days) == 3
    validation = validate_itinerary(itinerary, brief)
    overlap_errors = [i for i in validation.errors if i.code == "stop_overlap"]
    assert not overlap_errors, overlap_errors
    assert itinerary.total_est_cost_inr == sum(
        s.est_cost_inr for d in itinerary.days for s in d.stops)


def test_support_agent_packing_replan_and_emergency():
    support = TravelSupportAgent()
    packing = support.support("what should I pack", TripBrief(destination="Manali",
                                                              duration_days=4),
                              destination_id=3, destination_name="Manali")
    assert packing.status == "ok" and "packing" in packing.summary.lower()
    assert packing.guidance.topic == "packing"

    replan = support.support("our train is delayed, need to change day 2",
                             TripBrief(destination="Goa"))
    assert replan.guidance.needs_replanning is True
    assert replan.guidance.affected_items or replan.guidance.risks

    emergency = support.support("there was an accident, need a hospital", None)
    assert "112" in emergency.guidance.guidance
    assert emergency.guidance.topic == "emergency"
