"""Tour Guide Agent: attractions, culture and sightseeing recommendations."""
from __future__ import annotations

import logging
import time

from agents.schemas import (
    AgentResult,
    AgentStatus,
    Attraction,
    MemoryContext,
    TripBrief,
)

from .travel_tools import maps as guide_tool

logger = logging.getLogger(__name__)

_SPECIALTIES = ["history", "food walks", "adventure", "nature", "culture", "spiritual"]


class TourGuideAgent:
    agent_id = "tour_guide_agent"

    def recommend(
        self,
        brief: TripBrief | None,
        memory: MemoryContext | None = None,
        *,
        destination_id: int | None = None,
        destination_name: str | None = None,
        limit: int = 5,
    ) -> AgentResult:
        started = time.perf_counter()
        try:
            interests = set(brief.interests) if brief else set()
            visited: set[str] = set()
            disliked: set[str] = set()
            if memory:
                for item in memory.items:
                    lowered = item.content.lower()
                    if "visited" in lowered or "been to" in lowered:
                        visited.add(item.content.lower())
                    if "disliked" in lowered or "did not enjoy" in lowered or "skip" in lowered:
                        disliked.add(item.content.lower())
                    interests |= {tag for tag in _SPECIALTIES if tag in lowered}

            specialty = next((s for s in _SPECIALTIES if s in interests), None)
            response = guide_tool.search_guides(
                destination_id, specialty=specialty, limit=limit + 2,
            )
            attractions: list[Attraction] = []
            if response.ok:
                for row in response.data[:limit]:
                    name = str(row.get("name") or "Unnamed experience")
                    if any(name.lower() in seen for seen in visited) and not any(
                        name.lower() in want for want in ("revisit", "again")
                    ):
                        continue
                    if any(name.lower() in bad for bad in disliked):
                        continue
                    specialties = [s for s in (row.get("specialties") or []) if s in interests]
                    attractions.append(Attraction(
                        guide_id=row.get("id"),
                        name=name,
                        category=", ".join(row.get("specialties") or []) or "local experience",
                        why_fit=(f"aligns with your interest in {', '.join(specialties)}"
                                 if specialties else "a well-reviewed local experience"),
                        approx_duration_min=180,
                        location=destination_name,
                        price_per_person_inr=row.get("price_inr"),
                        hours_caveat="hours not verified against a live source",
                        evidence=response.evidence("guides.search", ref=str(row.get("id"))),
                    ))
            status: AgentStatus = "ok" if response.ok else "failed"
            return AgentResult(
                agent_id=self.agent_id,
                status=status,
                summary=f"{len(attractions)} experience ideas"
                        + (f" in {destination_name}" if destination_name else "")
                        + ("" if response.ok else f" ({response.error})"),
                attractions=attractions,
                evidence=[response.evidence("guides.search")] if response.ok else [],
                errors=[] if response.ok else [response.error or "guide search failed"],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        return ["visited places interests pace accessibility"]
