"""Food Guide Agent: cuisine and restaurant recommendations."""
from __future__ import annotations

import logging
import time
import math

from agents.schemas import (
    AgentResult,
    AgentStatus,
    FoodOption,
    MemoryContext,
    TripBrief,
)

from .travel_tools import restaurants as food_tool

logger = logging.getLogger(__name__)


class FoodGuideAgent:
    agent_id = "food_guide_agent"

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
            dietary = set(brief.dietary_requirements if brief else [])
            if memory:
                for item in memory.items:
                    lowered = item.content.lower()
                    for diet in ("vegetarian", "vegan", "halal", "jain", "gluten-free"):
                        if diet in lowered:
                            dietary.add(diet)
            # Never assume a diet the user has not stated.
            diet_param = None
            if {"vegetarian", "vegan", "jain"} & dietary:
                diet_param = "veg"

            budget_per_person = brief.effective_budget_per_person() if brief else None
            max_price = int(budget_per_person * 0.12) if budget_per_person else None

            response = food_tool.search_food(
                destination_id, destination_name=destination_name, diet=diet_param, max_price=max_price, limit=limit + 2,
            )
            options: list[FoodOption] = []
            if response.ok:
                for row in response.data[:limit]:
                    row_diet = row.get("diet")
                    dietary_fit = self._dietary_fit(dietary, row_diet)
                    options.append(FoodOption(
                        place_id=row.get("id"),
                        name=row.get("name") or "Unnamed place",
                        cuisine=row.get("cuisine"),
                        approx_price_per_guest_inr=math.ceil(row["price_inr"] / 2) if row.get("price_inr") is not None else None,
                        location=row.get("destination_name") or destination_name,
                        diet=row_diet,
                        dietary_fit=dietary_fit,
                        hours_caveat="opening hours not verified against a live source",
                        reservation_status="unknown",
                        evidence=response.evidence("food.search", ref=str(row.get("id"))),
                    ))
            status: AgentStatus = "ok" if response.ok else "failed"
            return AgentResult(
                agent_id=self.agent_id,
                status=status,
                summary=f"{len(options)} food recommendations"
                        + (f" in {destination_name}" if destination_name else "")
                        + ("" if response.ok else f" ({response.error})"),
                food_options=options,
                evidence=[response.evidence("food.search")] if response.ok else [],
                errors=[] if response.ok else [response.error or "food search failed"],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _dietary_fit(dietary: set[str], row_diet: str | None) -> str | None:
        if not dietary:
            return None
        if row_diet == "veg" or row_diet == "both":
            return "suits your stated dietary requirements"
        return "may not match your stated dietary requirements — verify with the venue"

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        return ["food preferences cuisine dietary restrictions liked disliked"]
