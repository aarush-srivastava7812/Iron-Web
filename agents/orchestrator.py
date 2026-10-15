"""Travel Orchestrator: the single entry point every page talks to.

Routes requests to only the required agents, coordinates dependencies,
combines results, and returns a typed OrchestrationResponse. Failures degrade
gracefully — gaps are reported, never filled with invented data.
"""
from __future__ import annotations

import logging

from agents.schemas import AgentResult, OrchestrationRequest, OrchestrationResponse

from .memory_gateway.gateway import MemoryGateway
from .orchestration.graph import TravelWorkflow

logger = logging.getLogger(__name__)


class TravelOrchestrator:
    def __init__(self, gateway: MemoryGateway | None = None,
                 workflow: TravelWorkflow | None = None) -> None:
        self.workflow = workflow or TravelWorkflow(gateway=gateway)

    @property
    def gateway(self) -> MemoryGateway:
        return self.workflow.gateway

    def handle(self, request: OrchestrationRequest) -> OrchestrationResponse:
        try:
            final = self.workflow.run(request)
        except Exception as error:
            logger.exception("orchestration failed")
            return OrchestrationResponse(
                request_id="unknown",
                status="failed",
                response="Something went wrong coordinating your request. Please try again.",
                page=request.page,
                errors=[str(error)],
            )
        results: list[AgentResult] = final.get("agent_results", [])
        writes = final.get("write_proposals", [])
        return OrchestrationResponse(
            request_id=final.get("request_id", ""),
            status=final.get("status", "ok") if final.get("status") in {"ok", "needs_clarification", "failed"} else "ok",
            response=final.get("response", ""),
            page=request.page,
            trip_brief=final.get("trip_brief"),
            itinerary=final.get("itinerary"),
            budget=final.get("budget"),
            agent_results=results,
            validation_issues=final.get("validation_issues", []),
            memory_write_proposals=writes,
            clarification_question=final.get("clarification_question"),
            errors=final.get("errors", []),
        )
