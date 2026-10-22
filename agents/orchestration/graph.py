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
from agents.agentic import AgenticWorkflowMixin, enabled as agentic_enabled, provider
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


class TravelWorkflow(AgenticWorkflowMixin):
    """Owns the shared gateway/agents and compiles the parent graph once."""

    def __init__(self, gateway: MemoryGateway | None = None, *, checkpoint: bool = True,
                 agentic: bool | None = None) -> None:
        self.checkpoint = checkpoint
        self.agentic = agentic_enabled() if agentic is None else agentic
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
        result = self._agent_operation("trip_consultant", lambda: result,
                                       dict(state, trip_brief=brief), memory=memory)
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
        if any(r.status == "failed" for r in state.get("agent_results", [])):
            return "failed"
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
        dest_candidate = (brief.destination if brief and brief.destination else None) or state.get("destination_name") or state.get("place")
        if not dest_candidate:
            return base
        response = destination_tool.search_destinations(query=dest_candidate, limit=1)
        if hasattr(self.gateway, "validate_current"):
            from agents.memory_gateway.three_tier import MemoryNeedsInformation
            exact = [row for row in response.data if brief.destination.strip().casefold()
                     in {str(row.get("name", "")).casefold(), str(row.get("slug", "")).casefold()}]
            if not response.ok or not exact:
                from agents.agentic import provider
                if self.agentic and provider() == "tinyfish":
                    return dict(base, destination_name=brief.destination, destination_id=None)
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
        return {"agent_results": [self._agent_operation("explore_agent",
            lambda **args: self.explore.discover(state.get("trip_brief"), memory, **args), state, memory=memory)]}

    def _run_stay(self, state: AgentState) -> AgentState:
        if "stay_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.stay.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="stay_agent",
        )
        return {"agent_results": [self._agent_operation("stay_agent", lambda **args: self.stay.search(
            state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
            nights=state.get("nights", 2),
            **args,
        ), state, memory=memory)]}

    def _run_tour_guide(self, state: AgentState) -> AgentState:
        if "tour_guide_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.tour_guide.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="tour_guide_agent",
        )
        return {"agent_results": [self._agent_operation("tour_guide_agent", lambda **args: self.tour_guide.recommend(
            state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
            **args,
        ), state, memory=memory)]}

    def _run_food_guide(self, state: AgentState) -> AgentState:
        if "food_guide_agent" not in state.get("tasks", []):
            return {}
        memory = self.gateway.retrieve(
            query=self.food_guide.memory_queries(state.get("trip_brief"))[0],
            user_id=state["user_id"], session_id=state["session_id"],
            agent_id="food_guide_agent",
        )
        return {"agent_results": [self._agent_operation("food_guide_agent", lambda **args: self.food_guide.recommend(
            state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
            **args,
        ), state, memory=memory)]}

    def _run_support(self, state: AgentState) -> AgentState:
        if "travel_support_agent" not in state.get("tasks", []):
            return {}
        memory = None
        if hasattr(self.gateway, "validate_current"):
            memory = self.gateway.retrieve(query="Current preparation requirements", user_id=state["user_id"],
                                           session_id=state["session_id"], agent_id="travel_support_agent")
        return {"agent_results": [self._agent_operation("travel_support_agent", lambda: self.support.support(
            state["request"], state.get("trip_brief"), memory,
            destination_id=state.get("destination_id"),
            destination_name=state.get("destination_name"),
            itinerary=state.get("itinerary"),
        ), state, memory=memory)]}

    def _collect_results(self, state: AgentState) -> AgentState:
        """Merge point for parallel branches; resolve destination from explore
        results if the brief named no known destination."""
        updates: AgentState = {}
        if state.get("destination_id") is None and not state.get("destination_name"):
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
        memory = None
        if hasattr(self.gateway, "validate_current"):
            memory = self.gateway.retrieve(query="Current itinerary and pace", user_id=state["user_id"],
                                  session_id=state["session_id"], agent_id="itinerary_planner")
        results = state.get("agent_results", [])
        pick = lambda agent_id, field: (next(  # noqa: E731
            (getattr(r, field) for r in results if r.agent_id == agent_id and getattr(r, field, None)),
            None))
        inputs = dict(
            attractions=pick("tour_guide_agent", "attractions") or [],
            food_options=pick("food_guide_agent", "food_options") or [],
            stay_options=pick("stay_agent", "stay_options") or [],
        )
        itinerary_result = self._agent_operation("itinerary_planner", lambda **args: self.planner.draft(
            state.get("trip_brief"),
            destination_name=state.get("destination_name"),
            transport_options=pick("budget_booking_agent", "transport_options") or [],
            **args,
        ), state, memory=memory, planner_inputs=inputs)
        return {"agent_results": [itinerary_result], "itinerary": itinerary_result.itinerary}

    def _run_budget(self, state: AgentState) -> AgentState:
        if "budget_booking_agent" not in state.get("tasks", []):
            return {}
        memory = None
        if hasattr(self.gateway, "validate_current"):
            memory = self.gateway.retrieve(query="Current budget and party size", user_id=state["user_id"],
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
            result = self._agent_operation("budget_booking_agent", lambda: self.budget.estimate(
                brief,
                stay_options=pick("itinerary_planner", "stay_options") or pick("stay_agent", "stay_options") or [],
                transport_options=pick("budget_booking_agent", "transport_options") or [],
                food_options=pick("food_guide_agent", "food_options") or [],
                attractions=pick("tour_guide_agent", "attractions") or [],
                itinerary=state.get("itinerary"),
                nights=state.get("nights", 2),
                party_size=party,
                per_person=False,
                unpriced_research=self.agentic and provider() == "tinyfish",
            ), state, memory=memory)
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
            if "budget_booking_agent" in state["tasks"] and outcome.get("itinerary"):
                revised = dict(state, **outcome)
                revised["agent_results"] = results + outcome.get("agent_results", [])
                budget_outcome = self._run_budget(revised)
                outcome["agent_results"] = outcome.get("agent_results", []) + budget_outcome.get("agent_results", [])
                outcome["budget"] = budget_outcome.get("budget")
            outcome["revision_count"] = count
            outcome["errors"] = updates.get("errors", [])
            return outcome
        return updates

    def _synthesize(self, state: AgentState) -> AgentState:
        from agents.presentation import travel_response

        results = state.get("agent_results", [])
        if state.get("clarification_question"):
            return {"response": state["clarification_question"], "status": "needs_clarification"}
        response = travel_response(state)
        failed = any(r.status == "failed" for r in results)
        return {"response": response, "status": "failed" if failed else "ok"}

    def _clarify(self, state: AgentState) -> AgentState:
        question = state.get("clarification_question") or "Could you share a few more trip details?"
        return {"response": question, "status": "needs_clarification"}

    def _propose_writes(self, state: AgentState) -> AgentState:
        """Selective memory writes: durable preferences + the key decision."""
        if state.get("status") != "ok":
            return {"write_proposals": []}
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
            {"clarify": "clarify", "continue": "resolve_destination", "failed": "synthesize"},
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
        started_at, workflow_id = time.time(), uuid.uuid4().hex
        observer = getattr(self.gateway, "observer", None)
        common = dict(run_id=workflow_id, workflow_id=workflow_id, started_at=started_at)
        if observer:
            observer.emit(request.session_id, "agent_started", agent_id="travel_orchestrator", **common)
        config = {"configurable": {"thread_id": request.user_id + ":" + request.session_id}}
        try:
            final = self.graph.invoke(
                {"_request": request, "request": request.request, "request_id": workflow_id,
                 "user_id": request.user_id, "session_id": request.session_id,
                 "page": request.page, "confirmed_booking": request.confirmed_booking,
                 "answers": request.answers}, config=config)
        except BaseException as error:
            elapsed=round((time.perf_counter()-started)*1000,2)
            if observer:
                observer.emit(request.session_id, "agent_completed", agent_id="travel_orchestrator", **common,
                    status="failed", summary="Workflow failed: " + type(error).__name__, errors=[str(error)],
                    elapsed_ms=elapsed, latency_ms=elapsed)
            raise
        elapsed=round((time.perf_counter()-started)*1000,2)
        if observer:
            observer.emit(request.session_id, "agent_completed", agent_id="travel_orchestrator", **common,
                status=final.get("status", "failed"), summary=final.get("response", "Workflow completed"),
                elapsed_ms=elapsed, latency_ms=elapsed, errors=final.get("errors", []),
                result=dict(agent_runs=len(final.get("agent_results", [])), revisions=final.get("revision_count", 0),
                            validation_issues=[i.model_dump(mode="json") for i in final.get("validation_issues", [])]))
        final["_elapsed_ms"] = int((time.perf_counter() - started) * 1000)  # type: ignore[assignment]
        return final
