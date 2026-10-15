"""Validator arithmetic and schedule checks."""
from __future__ import annotations

from agents.schemas import (
    BudgetEstimate,
    BudgetLine,
    DraftItinerary,
    ItineraryDay,
    ItineraryStop,
    TripBrief,
)
from agents.validation.budget_validator import validate_budget
from agents.validation.itinerary_validator import validate_itinerary
from agents.validation.result_validator import validate_results


def _stop(day, start, end, title, kind="attraction", cost=100, location="A"):
    from agents.schemas import Evidence
    import time

    return ItineraryStop(day=day, start_time=start, end_time=end, title=title, kind=kind,
                         location=location, est_cost_inr=cost,
                         evidence=Evidence(source="test", kind="mock", retrieved_at=int(time.time())))


def test_budget_total_mismatch_is_error():
    budget = BudgetEstimate(lines=[BudgetLine(category="stay", amount_inr=1000, basis="estimate"),
                                   BudgetLine(category="food", amount_inr=500, basis="estimate")],
                            total_inr=2000)
    result = validate_budget(budget)
    assert not result.ok
    assert any(i.code == "budget_total_mismatch" for i in result.errors)


def test_budget_over_budget_warning_and_delta():
    brief = TripBrief(party_size=2, budget_total_inr=20_000)
    budget = BudgetEstimate(per_person=False,
                            lines=[BudgetLine(category="stay", amount_inr=15_000, basis="estimate"),
                                   BudgetLine(category="food", amount_inr=12_000, basis="estimate")],
                            total_inr=27_000)
    result = validate_budget(budget, brief)
    warnings = [i.code for i in result.warnings]
    assert "over_budget" in warnings
    assert budget.budget_delta_inr == 7_000


def test_itinerary_overlap_detected():
    itinerary = DraftItinerary(
        title="test",
        days=[ItineraryDay(day=1, stops=[
            _stop(1, "09:00", "12:00", "Museum A"),
            _stop(1, "10:00", "11:00", "Cafe B", kind="food"),
        ])],
        total_est_cost_inr=200,
    )
    result = validate_itinerary(itinerary)
    assert any(i.code == "stop_overlap" for i in result.errors)


def test_itinerary_tight_transfer_warning():
    itinerary = DraftItinerary(
        title="test",
        days=[ItineraryDay(day=1, stops=[
            _stop(1, "09:00", "12:00", "Old Fort", location="North"),
            _stop(1, "12:10", "13:00", "Harbour Cafe", kind="food", location="South"),
        ])],
        total_est_cost_inr=200,
    )
    result = validate_itinerary(itinerary)
    assert any(i.code == "tight_transfer" for i in result.warnings)


def test_itinerary_trip_length_mismatch():
    brief = TripBrief(duration_days=2)
    itinerary = DraftItinerary(
        title="test",
        days=[ItineraryDay(day=n, stops=[]) for n in (1, 2, 3, 4)],
        total_est_cost_inr=0,
    )
    result = validate_itinerary(itinerary, brief)
    assert any(i.code == "trip_length_mismatch" for i in result.errors)


def test_result_validator_flags_mock_and_stale_sources():
    import time

    from agents.schemas import AgentResult, Evidence

    fresh = AgentResult(agent_id="explore_agent", status="ok",
                        evidence=[Evidence(source="x", kind="mock", retrieved_at=int(time.time()))])
    stale = AgentResult(agent_id="stay_agent", status="ok",
                        evidence=[Evidence(source="y", kind="live",
                                           retrieved_at=int(time.time()) - 10 * 60 * 60)])
    result = validate_results([fresh, stale])
    codes = [i.code for i in result.issues]
    assert "mock_source" in codes and "stale_source" in codes
