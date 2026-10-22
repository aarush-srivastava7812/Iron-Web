"""Public travel output must be useful without disclosing diagnostic payloads."""
from datetime import date

from agents.presentation import present_agent, travel_response
from agents.schemas import (
    AgentExecution, AgentResult, Attraction, BudgetEstimate, BudgetLine,
    DraftItinerary, Evidence, ItineraryDay, ItineraryStop, StayOption,
    SupportGuidance, TripBrief, ValidationIssue,
)


def evidence(ref="https://example.com/stay"):
    return Evidence(source="tinyfish.web", kind="live", retrieved_at=1, ref=ref)


def test_recommendations_use_real_details_and_keep_diagnostics_private():
    result = AgentResult(
        agent_id="stay_agent", status="ok", summary="SECRET_INTERNAL_SUMMARY",
        stay_options=[StayOption(name="Garden House", location="Jaipur",
            price_per_night_inr=2500, amenities=["Courtyard"],
            pros=["Close to the old town"], evidence=evidence())],
        evidence=[evidence()], execution=AgentExecution(mode="tinyfish",
            persona="SECRET_PERSONA", goal="SECRET_GOAL", completed=True,
            decision="SECRET_DECISION", observations=["SECRET_OBSERVATION"],
            tool_calls=["SECRET_TOOL"]))
    response = travel_response(dict(agent_results=[result], trip_brief=TripBrief(
        destination="Jaipur", party_size=2, pace="relaxed", budget_total_inr=30000)))
    assert "Garden House" in response and "Close to the old town" in response
    assert "₹2,500 per room / night" in response and "spending limit ₹30,000" in response
    assert "SECRET" not in response and "stay_agent" not in response
    view = result.presentation.model_dump_json()
    assert "SECRET" not in view
    assert "https://example.com/stay" in view


def test_missing_research_and_failures_do_not_masquerade_as_completed_findings():
    discovery = present_agent(AgentResult(agent_id="stay_agent", status="ok", evidence=[evidence()]))
    assert discovery.status == "needs_review" and not discovery.findings
    assert "not enough checked detail" in discovery.overview
    failed = present_agent(AgentResult(agent_id="stay_agent", status="failed",
        errors=["TINYFISH_API_KEY: private"], summary="Traceback: private"))
    assert failed.status == "unavailable" and "private" not in failed.model_dump_json()


def test_incomplete_costs_never_imply_free_prices_or_budget_fit():
    stay = present_agent(AgentResult(agent_id="stay_agent", status="ok",
        stay_options=[StayOption(name="Unpriced stay", evidence=evidence())]))
    assert stay.findings[0].price == "Nightly rate to confirm"
    for total in (0, 1200):
        budget = BudgetEstimate(costs_complete=False, total_inr=total,
            unknown_categories=["stays", "transport"],
            lines=[BudgetLine(category="food", amount_inr=total, basis="estimate")])
        view = present_agent(AgentResult(agent_id="budget_booking_agent", status="ok", budget=budget))
        assert "full trip total is still unknown" in view.overview or "awaiting supplier quotes" in view.overview
        assert "Still to price: stays, transport." in view.notes
        assert "remaining" not in view.model_dump_json()


def test_schedule_and_important_constraints_survive_the_richer_response():
    itinerary = DraftItinerary(title="A relaxed trip", days=[ItineraryDay(day=1,
        calendar_date=date(2026, 12, 1), stops=[ItineraryStop(day=1, start_time="10:00",
            end_time="11:00", title="Museum visit", kind="attraction")])],
        unresolved_conflicts=["Step-free access needs confirmation"])
    result = AgentResult(agent_id="itinerary_planner", status="ok", itinerary=itinerary)
    reply = travel_response(dict(agent_results=[result], itinerary=itinerary,
        validation_issues=[ValidationIssue(severity="warning", code="route", message="Confirm transfer times")]))
    assert "Day 1: 10:00: Museum visit" in reply
    assert "Step-free access needs confirmation" in reply and "Confirm transfer times" in reply
    assert result.presentation.findings[0].detail == "10:00–11:00: Museum visit"


def test_unsafe_sources_and_reasoning_in_display_fields_are_excluded():
    for url in ("javascript:alert(1)", "https://user:password@example.com", "https://127.0.0.1/private"):
        view = present_agent(AgentResult(agent_id="tour_guide_agent", status="ok",
            attractions=[Attraction(name="Museum", why_fit="<think>private deliberation</think>", evidence=evidence(url))],
            evidence=[evidence(url)]))
        assert not view.sources and view.findings[0].source_url is None
        assert not view.findings[0].detail
    support = present_agent(AgentResult(agent_id="travel_support_agent", status="ok",
        guidance=SupportGuidance(topic="Packing", guidance="Bring comfortable shoes", risks=["Check the forecast"])))
    assert support.findings[0].detail == "Bring comfortable shoes" and support.notes == ["Check the forecast"]


def test_saved_plan_findings_follow_the_edited_budget_not_old_presentations(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "stitch_ai_travel_booking_platform/backend"))
    from app.plan_drafts import view
    old = AgentResult(agent_id="budget_booking_agent", status="ok", budget=BudgetEstimate(total_inr=1000))
    old.presentation = present_agent(old)
    payload = dict(agent_results=[old.model_dump(mode="json")],
                   budget=BudgetEstimate(total_inr=2400).model_dump(mode="json"))
    row = SimpleNamespace(version=2, stale=False, payload=payload)
    displayed = view(row, [row])["plan"]["agent_results"][0]["presentation"]["overview"]
    assert "₹2,400" in displayed and "₹1,000" not in displayed
    assert "₹1,000" in payload["agent_results"][0]["presentation"]["overview"]


def test_failed_research_chat_does_not_echo_stored_provider_errors(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "stitch_ai_travel_booking_platform/backend"))
    from app.local_chat import status_reply
    reply = status_reply(dict(research=dict(status="failed", error="SECRET_PROVIDER_ERROR",
        failed_specialists=[dict(name="Hotels", reason="SECRET_PROVIDER_ERROR")])))
    assert "SECRET" not in reply and "trip details are intact" in reply
