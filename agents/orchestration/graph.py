"""Parent LangGraph workflow: parse → retrieve → understand → plan → execute
(required specialists in parallel) → validate (bounded revise) → synthesize →
propose + persist memory writes → END.

Iron Web remains the durable memory layer; the checkpointer only keeps
execution state. Agents that are not needed for the current request are
skipped, never run "just in case".
"""
from __future__ import annotations

import logging
import time
import uuid

from langgraph.graph import END, StateGraph

from agents.config import settings
from agents.explore_agent import ExploreAgent
from agents.food_guide_agent import FoodGuideAgent
from agents.itinerary_planner import ItineraryPlanner
from agents.memory_gateway.gateway import MemoryGateway
from agents.schemas import (
    AgentResult,
    MemoryWriteProposal,
    OrchestrationRequest,
    TripBrief,
)
from agents.stay_agent import StayAgent
from agents.trip_consultant import TripConsultant
from agents.travel_tools import destinations as destination_tool

from .checkpointing import get_saver
from .routing import plan_tasks
from .state import AgentState
from agents.budget_booking_agent import BudgetBookingAgent
from agents.tour_guide_agent import TourGuideAgent
from agents.travel_support_agent import TravelSupportAgent
from agents.validation.budget_validator import validate_budget
from agents.validation.itinerary_validator import validate_itinerary
from agents.validation.result_validator import validate_results

logger = logging.getLogger(__name__)


class TravelWorkflow:
    """Owns the shared gateway/agents and compiles the parent graph once."""

    def __init__(self, gateway: MemoryGateway | None = None, *, checkpoint: bool = True) -> None:
        self.checkpoint = checkpoint
        self.gateway = gateway or MemoryGateway()
        self.consultant = TripConsultant()
        self.explore = ExploreAgent()
        self.stay = StayAgent()
        self.tour_guide = TourGuideAgent()
        self.food_guide = FoodGuideAgent()
        self.planner = ItineraryPlanner()
        self.budget = BudgetBookingAgent()
        self.support = TravelSupportAgent()
        self.graph = self._build_graph()

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------
    def _parse_request(self, state: AgentState) -> AgentState:
        request: OrchestrationRequest | None = state.get("_request")  # type: ignore[assignment]
        if request is None:
            request = OrchestrationRequest(
                request=state.get("request", ""),
                user_id=state.get("user_id", "anonymous"),
                session_id=state.get("session_id", "default"),
                page=state.get("page", "home"),  # type: ignore[arg-type]
                confirmed_booking=bool(state.get("confirmed_booking")),
                answers=state.get("answers", {}),
            )
        return {
            "request_id": state.get("request_id") or uuid.uuid4().hex[:12],
            "request": request.request,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "page": request.page,
            "confirmed_booking": request.confirmed_booking,
            "answers": request.answers,
            "tasks": plan_tasks(request),
            "revision_count": state.get("revision_count", 0),
            "errors": state.get("errors", []),
            "agent_results": state.get("agent_results", []),
            "status": "running",
        }

    def _retrieve_context(self, state: AgentState) -> AgentState:
        context = self.gateway.retrieve(
            query=f"{state['request']} travel preferences",
            user_id=state["user_id"],
            session_id=state["session_id"],
            agent_id="travel_orchestrator",
        )
        return {"memory_context": context}

    def _understand_requirements(self, state: AgentState) -> AgentState:
        memory = self.gateway.retrieve(
            query=self.consultant.memory_queries(TripBrief())[0],
            user_id=state["user_id"],
            session_id=state["session_id"],
            agent_id="trip_consultant",
        )
        if hasattr(self.gateway, "trip_brief"):
            brief = self.gateway.trip_brief(memory)
            result = AgentResult(agent_id="trip_consultant", status="ok",
                                 summary=self.consultant._summary(brief), trip_brief=brief)
        else:
            result = self.consultant.run(state["request"], memory)
        brief = result.trip_brief or TripBrief()
        # Answers from a previous clarification round fill missing fields.
        answers = state.get("answers") or {}
        if answers:
            if hasattr(self.gateway, "validate_current"):
                from agents.memory_gateway.three_tier import MemoryNeedsInformation
                raise MemoryNeedsInformation({"answers": "save confirmed Trip details before planning"})
            brief = self._apply_answers(brief, answers, state["user_id"], state["session_id"])
        return {
            "agent_results": [result],
            "trip_brief": brief,
            "nights": max((brief.duration_days or 3) - 1, 1),
            "clarification_question": brief.clarification_question,
        }

    def _clarify_or_continue(self, state: AgentState) -> str:
        """Clarify only when missing details materially affect the result."""
        brief: TripBrief | None = state.get("trip_brief")
        if not brief or not brief.clarification_question or state.get("answers"):
            return "continue"
        if not brief.destination and not brief.destination_flexible:
            return "clarify"
        has_signals = bool(
            brief.destination or brief.interests or brief.has_dates()
            or brief.duration_days or brief.party_size
            or brief.effective_budget_per_person()
        )
        if not has_signals:
            return "clarify"  # nothing actionable to work with yet
        critical = {"destination", "dates_or_duration"} & set(brief.missing_fields)
        tasks = state.get("tasks", [])
        needs_full_brief = (
            state.get("page") == "plan"
            or "itinerary_planner" in tasks
            or (state.get("confirmed_booking") and "budget_booking_agent" in tasks)
        )
        if critical and needs_full_brief:
            return "clarify"
        # Page-specific questions (a food tip, a stay list) proceed with the
        # known context; specialists handle partial briefs.
        return "continue"

    @staticmethod
    def _apply_answers(brief: TripBrief, answers: dict, user_id: str, session_id: str) -> TripBrief:
        data = brief.model_dump()
        mapping = {
            "destination": "destination", "party_size": "party_size",
            "duration_days": "duration_days", "budget_total_inr": "budget_total_inr",
            "budget_per_person_inr": "budget_per_person_inr", "pace": "pace",
        }
        for key, field in mapping.items():
            if key in answers and answers[key] not in (None, ""):
                data[field] = answers[key]
        if "destination_flexible" in answers:
            data["destination_flexible"] = bool(answers["destination_flexible"])
        updated = TripBrief(**data)
        # Re-run the missing-field finalize through the consultant's helper.
        from agents.trip_consultant import TripConsultant  # local import avoids cycles

        TripConsultant()._finalize(updated)  # noqa: SLF001 — same-package contract helper
        return updated

    def _resolve_destination(self, state: AgentState) -> AgentState:
        # We chose to continue past clarification; drop the stale question so
        # synthesis reports a real result.
        base: AgentState = {"clarification_question": None}
        brief: TripBrief | None = state.get("trip_brief")
        if not brief or not brief.destination:
            return base
        response = destination_tool.search_destinations(query=brief.destination, limit=1)
        if hasattr(self.gateway, "validate_current"):
            from agents.memory_gateway.three_tier import MemoryNeedsInformation
            exact = [row for row in response.data if brief.destination.strip().casefold()
                     in {str(row.get("name", "")).casefold(), str(row.get("slug", "")).casefold()}]
            if not response.ok or not exact:
                raise MemoryNeedsInformation({"destination": "no exact catalog match"})
            response.data = exact
        if response.ok and response.data:
            row = response.data[0]
            base.update({"destination_id": row.get("id"), "destination_name": row.get("name")})
        return base

    # -- specialist nodes (skipped unless planned) ------------------------
    def _run_explore(self, state: AgentState) -> AgentState:
        if "explore_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.explore.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="explore_agent",
        )
        return {"agent_results": [self.explore.discover(state.get("trip_brief"), memory)]}

    def _run_stay(self, state: AgentState) -> AgentState:
        if "stay_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.stay.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="stay_agent",
        )
        return {"agent_results": [self.stay.search(
            state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
            nights=state.get("nights", 2),
        )]}

    def _run_tour_guide(self, state: AgentState) -> AgentState:
        if "tour_guide_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.tour_guide.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="tour_guide_agent",
        )
        return {"agent_results": [self.tour_guide.recommend(
            state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
        )]}

    def _run_food_guide(self, state: AgentState) -> AgentState:
        if "food_guide_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.food_guide.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="food_guide_agent",
        )
        return {"agent_results": [self.food_guide.recommend(
            state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
        )]}

    def _run_support(self, state: AgentState) -> AgentState:
        if "travel_support_agent" not in state.get("tasks", []):
            return {}
        memory = None
        if hasattr(self.gateway, "validate_current"):
            memory = self.gateway.retrieve(query="Current preparation requirements", user_id=state["user_id"],
                                           session_id=state["session_id"], agent_id="travel_support_agent")
        return {"agent_results": [self.support.support(
            state["request"], state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
            itinerary=state.get("itinerary"),
        )]}

    def _collect_results(self, state: AgentState) -> AgentState:
        """Merge point for parallel branches; resolve destination from explore
        results if the brief named no known destination."""
        updates: AgentState = {}
        if state.get("destination_id") is None:
            for result in state.get("agent_results", []):
                if result.destination_ideas:
                    top = result.destination_ideas[0]
                    updates["destination_id"] = top.destination_id
                    updates["destination_name"] = top.name
                    break
        return updates

    def _run_itinerary(self, state: AgentState) -> AgentState:
        if "itinerary_planner" not in state.get("tasks", []):
            return {}
        if hasattr(self.gateway, "validate_current"):
            self.gateway.retrieve(query="Current itinerary and pace", user_id=state["user_id"],
                                  session_id=state["session_id"], agent_id="itinerary_planner")
        results = state.get("agent_results", [])
        pick = lambda agent_id, field: (next(  # noqa: E731
            (getattr(r, field) for r in results if r.agent_id == agent_id and getattr(r, field, None)),
            None))
        itinerary_result = self.planner.draft(
            state.get("trip_brief"),
            destination_name=state.get("destination_name"),
            attractions=pick("tour_guide_agent", "attractions") or [],
            food_options=pick("food_guide_agent", "food_options") or [],
            stay_options=pick("stay_agent", "stay_options") or [],
            transport_options=pick("budget_booking_agent", "transport_options") or [],
        )
        return {"agent_results": [itinerary_result], "itinerary": itinerary_result.itinerary}

    def _run_budget(self, state: AgentState) -> AgentState:
        if "budget_booking_agent" not in state.get("tasks", []):
            return {}
        if hasattr(self.gateway, "validate_current"):
            self.gateway.retrieve(query="Current budget and party size", user_id=state["user_id"],
                                  session_id=state["session_id"], agent_id="budget_booking_agent")
        results = state.get("agent_results", [])

        def pick(agent_id: str, field: str):
            return next(
                (getattr(r, field) for r in results if r.agent_id == agent_id and getattr(r, field, None)),
                None,
            )

        brief = state.get("trip_brief")
        party = (brief.party_size if brief and brief.party_size else 1)
        if state.get("confirmed_booking"):
            items = self._cart_from_itinerary(state)
            result = self.budget.attempt_booking(
                user_id=state["user_id"], cart_items=items, confirmed=True,
            )
        else:
            result = self.budget.estimate(
                brief,
                stay_options=pick("stay_agent", "stay_options") or [],
                transport_options=pick("budget_booking_agent", "transport_options") or [],
                food_options=pick("food_guide_agent", "food_options") or [],
                attractions=pick("tour_guide_agent", "attractions") or [],
                itinerary=state.get("itinerary"),
                nights=state.get("nights", 2),
                party_size=party,
                per_person=False,
            )
        return {"agent_results": [result], "budget": result.budget}

    @staticmethod
    def _cart_from_itinerary(state: AgentState) -> list[dict]:
        items: list[dict] = []
        itinerary = state.get("itinerary")
        if itinerary:
            for day in itinerary.days:
                for stop in day.stops:
                    if stop.kind in {"stay", "food", "transport"}:
                        items.append({"item_type": stop.kind, "name": stop.title,
                                      "start_date": day.calendar_date.isoformat() if day.calendar_date else None,
                                      "quantity": 1})
        return items

    def _validate_results(self, state: AgentState) -> AgentState:
        results = state.get("agent_results", [])
        issues = []
        result_validation = validate_results(results)
        issues.extend(result_validation.issues)
        itinerary = state.get("itinerary")
        if itinerary:
            itinerary_validation = validate_itinerary(itinerary, state.get("trip_brief"))
            issues.extend(itinerary_validation.issues)
        budget = state.get("budget")
        if budget:
            budget_validation = validate_budget(budget, state.get("trip_brief"))
            issues.extend(budget_validation.issues)
        return {"validation_issues": issues}

    def _revise_or_continue(self, state: AgentState) -> str:
        issues = state.get("validation_issues", [])
        errors = [i for i in issues if i.severity == "error"]
        if errors and state.get("revision_count", 0) < settings.max_revision_loops:
            return "revise"
        return "synthesize"

    def _revise(self, state: AgentState) -> AgentState:
        """Bounded revision: drop failing itinerary pieces and re-draft once."""
        count = state.get("revision_count", 0) + 1
        updates: AgentState = {"revision_count": count}
        errors = [i.message for i in state.get("validation_issues", []) if i.severity == "error"]
        if errors:
            updates["errors"] = list(state.get("errors", [])) + errors
        # Re-draft with fewer moving parts so the loop terminates.
        if state.get("itinerary") is not None:
            state = dict(state)
            state["tasks"] = [t for t in state.get("tasks", [])]
            results = [r for r in state.get("agent_results", []) if r.agent_id != "itinerary_planner"]
            state["agent_results"] = results
            outcome = self._run_itinerary(state)
            outcome["revision_count"] = count
            outcome["errors"] = updates.get("errors", [])
            return outcome
        return updates

    def _synthesize(self, state: AgentState) -> AgentState:
        results = state.get("agent_results", [])
        parts: list[str] = []
        if state.get("clarification_question"):
            return {"response": state["clarification_question"], "status": "needs_clarification"}
        for result in results:
            if result.summary and result.status != "failed":
                parts.append(f"{result.agent_id.replace('_', ' ').title()}: {result.summary}")
                options = result.stay_options or result.food_options or result.attractions or result.destination_ideas
                if options:
                    parts.append("Suggestions: " + "; ".join(option.name for option in options[:4]))
                if result.guidance:
                    parts.append(result.guidance.guidance)
        itinerary = state.get("itinerary")
        if itinerary:
            day_lines = []
            for day in itinerary.days:
                stops = " → ".join(stop.title for stop in day.stops) or "free day"
                day_lines.append(f"Day {day.day}: {stops}")
            parts.append("Schedule:\n" + "\n".join(day_lines))
        budget = state.get("budget")
        if budget:
            parts.append(f"Estimated cost: ₹{budget.total_inr:,} "
                         + ("per person" if budget.per_person else "total")
                         + " (estimates, not confirmed prices)")
            parts.extend(budget.warnings[:2])
        warnings = [i.message for i in state.get("validation_issues", []) if i.severity == "warning"]
        if warnings:
            parts.append("Caveats: " + "; ".join(sorted(set(warnings))[:3]))
        if any(r.status == "failed" for r in results):
            failed = [r.agent_id for r in results if r.status == "failed"]
            parts.append(f"Some parts could not be completed: {', '.join(failed)}.")
        response = "\n".join(parts) or "I could not put together a plan for that request yet."
        return {"response": response, "status": "ok"}

    def _clarify(self, state: AgentState) -> AgentState:
        question = state.get("clarification_question") or "Could you share a few more trip details?"
        return {"response": question, "status": "needs_clarification"}

    def _propose_writes(self, state: AgentState) -> AgentState:
        """Selective memory writes: durable preferences + the key decision."""
        proposals: list[MemoryWriteProposal] = []
        brief = state.get("trip_brief")
        if brief:
            proposals.extend(self.consultant.preference_writes(
                brief, state["user_id"], state["session_id"]))
        if state.get("destination_name"):
            proposals.append(MemoryWriteProposal(
                user_id=state["user_id"], session_id=state["session_id"],
                agent_id="travel_orchestrator",
                content=f"Planned a trip to {state['destination_name']}"
                        + (f" for {brief.duration_days} days" if brief and brief.duration_days else ""),
                kind="decision", importance=0.7, confidence=0.85,
            ))
        return {"write_proposals": proposals}

    def _persist_writes(self, state: AgentState) -> AgentState:
        proposals = state.get("write_proposals", [])
        if not proposals:
            return {}
        results = self.gateway.propose_writes(proposals)
        stored = sum(1 for r in results if r.status == "stored")
        logger.info("memory writes: %d/%d stored for user %s",
                    stored, len(results), state["user_id"])
        return {}

    # ------------------------------------------------------------------
    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("parse_request", self._parse_request)
        builder.add_node("retrieve_context", self._retrieve_context)
        builder.add_node("understand_requirements", self._understand_requirements)
        builder.add_node("resolve_destination", self._resolve_destination)
        builder.add_node("run_explore", self._run_explore)
        builder.add_node("run_stay", self._run_stay)
        builder.add_node("run_tour_guide", self._run_tour_guide)
        builder.add_node("run_food_guide", self._run_food_guide)
        builder.add_node("run_support", self._run_support)
        builder.add_node("collect_results", self._collect_results)
        builder.add_node("run_itinerary", self._run_itinerary)
        builder.add_node("run_budget", self._run_budget)
        builder.add_node("validate_results", self._validate_results)
        builder.add_node("revise", self._revise)
        builder.add_node("synthesize", self._synthesize)
        builder.add_node("propose_writes", self._propose_writes)
        builder.add_node("persist_writes", self._persist_writes)

        builder.set_entry_point("parse_request")
        builder.add_node("clarify", self._clarify)
        builder.add_edge("parse_request", "retrieve_context")
        builder.add_edge("retrieve_context", "understand_requirements")
        builder.add_conditional_edges(
            "understand_requirements", self._clarify_or_continue,
            {"clarify": "clarify", "continue": "resolve_destination"},
        )
        builder.add_edge("clarify", END)
        builder.add_edge("resolve_destination", "run_explore")
        # Independent research runs as parallel branches into the collector.
        builder.add_edge("resolve_destination", "run_stay")
        builder.add_edge("resolve_destination", "run_tour_guide")
        builder.add_edge("resolve_destination", "run_food_guide")
        builder.add_edge("resolve_destination", "run_support")
        builder.add_edge("run_explore", "collect_results")
        builder.add_edge("run_stay", "collect_results")
        builder.add_edge("run_tour_guide", "collect_results")
        builder.add_edge("run_food_guide", "collect_results")
        builder.add_edge("run_support", "collect_results")
        builder.add_edge("collect_results", "run_itinerary")
        builder.add_edge("run_itinerary", "run_budget")
        builder.add_edge("run_budget", "validate_results")
        builder.add_conditional_edges(
            "validate_results", self._revise_or_continue,
            {"revise": "revise", "synthesize": "synthesize"},
        )
        builder.add_edge("revise", "validate_results")
        builder.add_edge("synthesize", "propose_writes")
        builder.add_edge("propose_writes", "persist_writes")
        builder.add_edge("persist_writes", END)
        return builder.compile(checkpointer=get_saver() if self.checkpoint else None)

    # ------------------------------------------------------------------
    def run(self, request: OrchestrationRequest) -> dict:
        started = time.perf_counter()
        config = {"configurable": {"thread_id": request.user_id + ":" + request.session_id}}
        final = self.graph.invoke(
            {"_request": request, "request": request.request,  # type: ignore[dict-item]
             "user_id": request.user_id, "session_id": request.session_id,
             "page": request.page, "confirmed_booking": request.confirmed_booking,
             "answers": request.answers},
            config=config,
        )
        final["_elapsed_ms"] = int((time.perf_counter() - started) * 1000)  # type: ignore[assignment]
        return final
