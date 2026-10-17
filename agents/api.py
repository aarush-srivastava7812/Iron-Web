"""Agent HTTP service.

Runs beside the existing applications: Iron Web's dashboard server (server.py)
and the travel app backend stay untouched. Page→agent mapping follows the
architecture's page table; user/session context is propagated end to end.

Run:  <venv-cpu python> -m uvicorn agents.api:app --port 8100
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.config import settings
from agents.schemas import OrchestrationRequest, OrchestrationResponse
from agents.validation.result_validator import validate_results

from .orchestrator import TravelOrchestrator
from .resource_manager.resource_monitor import ResourceMonitor

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("agents.api")

app = FastAPI(title="Iron Web Travel Agents", version="0.1.0")
_orchestrator: TravelOrchestrator | None = None


def get_orchestrator() -> TravelOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TravelOrchestrator()
    return _orchestrator


class QueryBody(BaseModel):
    request: str
    user_id: str
    session_id: str
    page: str = "home"
    confirmed_booking: bool = False
    answers: dict = {}


@app.get("/agents/health")
def health():
    gateway = get_orchestrator().gateway
    return {
        "status": "ok",
        "llm_configured": settings.has_llm(),
        "memory_graph_live": gateway.graph_live,
    }


@app.post("/agents/query", response_model=OrchestrationResponse)
def query(body: QueryBody):
    try:
        request = OrchestrationRequest(
            request=body.request,
            user_id=body.user_id,
            session_id=body.session_id,
            page=body.page,  # type: ignore[arg-type]
            confirmed_booking=body.confirmed_booking,
            answers=body.answers,
        )
    except Exception as error:
        raise HTTPException(422, f"invalid request: {error}") from error
    return get_orchestrator().handle(request)


@app.get("/agents/memory/{user_id}")
def memory(user_id: str, query: str = "travel preferences", k: int = 8):
    gateway = get_orchestrator().gateway
    context = gateway.retrieve(
        query=query[:300], user_id=user_id, session_id="introspection",
        agent_id="travel_orchestrator", limit=max(1, min(k, 20)),
        use_cache=False,
    )
    return context.model_dump()


@app.get("/agents/resources")
def resources():
    monitor = ResourceMonitor(memory_gateway=get_orchestrator().gateway)
    return monitor.snapshot()


@app.post("/agents/validate")
def validate(results: list[dict]):
    """Re-run result validation on previously returned agent results."""
    from agents.schemas import AgentResult

    try:
        parsed = [AgentResult(**row) for row in results]
    except Exception as error:
        raise HTTPException(422, f"invalid agent results: {error}") from error
    validation = validate_results(parsed)
    return validation.model_dump()
