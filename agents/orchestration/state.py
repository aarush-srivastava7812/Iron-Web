"""Typed, bounded LangGraph workflow state.

Large payloads (tool responses, full memory records) live behind references:
agent results are held as AgentResult models, memory as a compact
MemoryContext. Full conversation history is never duplicated into state.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from agents.schemas import (
    AgentResult,
    BudgetEstimate,
    DraftItinerary,
    MemoryContext,
    MemoryWriteProposal,
    TripBrief,
    ValidationIssue,
)


def _merge_results(current: list[AgentResult], incoming: list[AgentResult]) -> list[AgentResult]:
    """Reducer: parallel specialists merge by agent id (latest wins)."""
    by_id = {result.agent_id: result for result in current}
    for result in incoming:
        by_id[result.agent_id] = result
    return list(by_id.values())


class AgentState(TypedDict, total=False):
    request_id: str
    user_id: str
    session_id: str
    page: str
    request: str
    confirmed_booking: bool
    answers: dict[str, Any]

    # workflow progress
    revision_count: int
    tasks: list[str]
    errors: list[str]
    status: str

    # context + understanding
    memory_context: MemoryContext | None
    trip_brief: TripBrief | None
    destination_id: int | None
    destination_name: str | None
    nights: int

    # research + results
    agent_results: Annotated[list[AgentResult], _merge_results]
    itinerary: DraftItinerary | None
    budget: BudgetEstimate | None
    validation_issues: list[ValidationIssue]
    write_proposals: list[MemoryWriteProposal]

    # output
    response: str
    clarification_question: str | None
    _request: Any
