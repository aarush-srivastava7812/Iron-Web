"""Stay Agent: accommodation search, comparison and shortlisting."""
from __future__ import annotations

import logging
import time

from agents.schemas import (
    AgentResult,
    AgentStatus,
    MemoryContext,
    StayOption,
    TripBrief,
)

from .travel_tools import accommodation as stay_tool

logger = logging.getLogger(__name__)

_AMENITY_HINTS = {"wifi": "Wi-Fi", "breakfast": "breakfast", "home-food": "home food"}


class StayAgent:
    agent_id = "stay_agent"

    def search(
        self,
        brief: TripBrief | None,
        memory: MemoryContext | None = None,
        *,
        destination_id: int | None = None,
        destination_name: str | None = None,
        nights: int = 2,
        limit: int = 4,
    ) -> AgentResult:
        started = time.perf_counter()
        try:
            wanted_amenity = None
            if memory:
                joined = " ".join(item.content.lower() for item in memory.items)
                for token, label in _AMENITY_HINTS.items():
                    if token in joined:
                        wanted_amenity = token
                        break
            budget_per_person = brief.effective_budget_per_person() if brief else None
            max_price = None
            if budget_per_person and nights:
                # Keep stay costs within ~55% of the per-person budget.
                max_price = max(500, int(budget_per_person * 0.55 / max(nights, 1)))

            response = stay_tool.search_stays(
                destination_id,
                max_price=max_price,
                amenity=wanted_amenity,
                limit=limit + 2,
            )
            options: list[StayOption] = []
            if response.ok:
                for row in response.data[:limit]:
                    price = row.get("price_inr")
                    options.append(StayOption(
                        stay_id=row.get("id"),
                        name=row.get("name") or "Unnamed stay",
                        location=row.get("destination_name") or destination_name,
                        kind=row.get("kind"),
                        price_per_night_inr=price,
                        total_price_inr=stay_tool.estimate_stay_total(price, nights),
                        rating=row.get("rating"),
                        amenities=list(row.get("amenities") or []),
                        availability_status="unknown",  # no live availability feed
                        cancellation_note=None,
                        pros=self._pros(row, wanted_amenity),
                        cons=self._cons(row, max_price),
                        evidence=response.evidence("stays.search", ref=str(row.get("id")),
                                                   note="indicative listing; availability not verified"),
                    ))
                options.sort(key=self._rank_key, reverse=True)
            status: AgentStatus = "ok" if response.ok and options else \
                ("failed" if not response.ok else "ok")
            summary = (f"{len(options)} stay options" +
                       (f" near {destination_name}" if destination_name else "")) \
                if response.ok else f"stay search failed: {response.error}"
            return AgentResult(
                agent_id=self.agent_id,
                status=status,
                summary=summary,
                stay_options=options,
                evidence=[response.evidence("stays.search")] if response.ok else [],
                errors=[] if response.ok else [response.error or "stay search failed"],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _pros(row: dict, wanted_amenity: str | None) -> list[str]:
        pros = []
        rating = row.get("rating")
        if rating and rating >= 4.5:
            pros.append(f"highly rated ({rating})")
        amenities = set(row.get("amenities") or [])
        if wanted_amenity and wanted_amenity in amenities:
            pros.append(f"has {_AMENITY_HINTS[wanted_amenity]} you prefer")
        if row.get("kind") == "homestay":
            pros.append("local homestay character")
        return pros

    @staticmethod
    def _cons(row: dict, max_price: int | None) -> list[str]:
        cons = []
        if max_price and row.get("price_inr") and row["price_inr"] > max_price * 0.8:
            cons.append("toward the top of your budget range")
        if not row.get("amenities"):
            cons.append("amenity details missing")
        return cons

    @staticmethod
    def _rank_key(option: StayOption) -> float:
        score = (option.rating or 0.0) * 2.0
        if option.price_per_night_inr:
            score += max(0.0, 6.0 - option.price_per_night_inr / 1000.0)
        score += len(option.pros)
        return score

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        return ["accommodation preferences amenities homestay hotel feedback"]
