"""Explore Agent: destination discovery and inspiration."""
from __future__ import annotations

import logging
import time

from agents.schemas import (
    AgentResult,
    AgentStatus,
    DestinationIdea,
    MemoryContext,
    TripBrief,
)

from .travel_tools import destinations as destination_tool

logger = logging.getLogger(__name__)

_COST_LEVELS = ((12_000, "budget"), (30_000, "mid"))


def _cost_level(avg_cost: int | None) -> str | None:
    if avg_cost is None:
        return None
    for threshold, level in _COST_LEVELS:
        if avg_cost <= threshold:
            return level
    return "premium"


class ExploreAgent:
    agent_id = "explore_agent"

    def discover(self, brief: TripBrief | None, memory: MemoryContext | None = None,
                 *, limit: int = 5) -> AgentResult:
        started = time.perf_counter()
        try:
            interests = set(brief.interests) if brief else set()
            if memory:
                for item in memory.items:
                    lowered = item.content.lower()
                    interests |= {tag for tag in
                                  ["beach", "mountain", "heritage", "culture", "nature",
                                   "spiritual", "wellness", "food", "adventure"]
                                  if tag in lowered}

            response = destination_tool.search_destinations(
                query=(brief.destination if brief and not brief.destination_flexible else None),
                limit=limit + 3,
            )
            ideas: list[DestinationIdea] = []
            if response.ok:
                for row in response.data:
                    tags = set(row.get("tags") or [])
                    overlap = len(tags & interests)
                    # Diversity: alternate between strong matches and fresh ideas.
                    ideas.append(DestinationIdea(
                        destination_id=row.get("id"),
                        slug=row.get("slug"),
                        name=row.get("name") or "Unknown destination",
                        region=", ".join(filter(None, [row.get("state"), row.get("country")])) or None,
                        why_fit=self._why_fit(row, interests, overlap),
                        suggested_duration_days=self._suggested_days(row, brief),
                        best_season=row.get("best_season"),
                        cost_level=_cost_level(row.get("avg_cost_inr")),
                        avg_cost_inr=row.get("avg_cost_inr"),
                        tags=sorted(tags),
                        seasonality_note=("Verify the season fits your dates; "
                                          f"best listed as {row.get('best_season')}"
                                          if row.get("best_season") else None),
                        evidence=response.evidence("destinations.search", ref=str(row.get("id"))),
                    ))
                strong = [i for i in ideas if i.why_fit and "matches your interest" in i.why_fit]
                others = [i for i in ideas if i not in strong]
                ideas = (strong[: limit - 1] + others[: max(1, limit - len(strong[: limit - 1]))])[:limit]
            status: AgentStatus = "ok" if response.ok else "failed"
            return AgentResult(
                agent_id=self.agent_id,
                status=status,
                summary=f"{len(ideas)} destination ideas" +
                        ("" if response.ok else f" ({response.error})"),
                destination_ideas=ideas,
                evidence=[response.evidence("destinations.search")] if response.ok else [],
                errors=[] if response.ok else [response.error or "destination search failed"],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _why_fit(row: dict, interests: set[str], overlap: int) -> str:
        tags = ", ".join(sorted(set(row.get("tags") or []) & interests))
        if tags:
            return f"matches your interest in {tags}"
        if overlap:
            return "matches your interests"
        return f"explored for its {', '.join(sorted(set(row.get('tags') or []))[:2]) or 'local character'}"

    @staticmethod
    def _suggested_days(row: dict, brief: TripBrief | None) -> int | None:
        if brief and brief.duration_days:
            return brief.duration_days
        return 3

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        queries = ["destinations explored wishlist interests"]
        if brief and brief.destination:
            queries.append(f"{brief.destination} impressions")
        return queries

    def wish_writes(self, brief: TripBrief | None, user_id: str, session_id: str) -> list:
        """A wish-list write happens only on an explicit user statement, which the
        orchestrator passes through; discovery itself never writes memory."""
        return []
