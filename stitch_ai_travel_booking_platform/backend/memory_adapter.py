"""Bridge travel recommendations to the user's external memory service."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class MemoryServiceError(RuntimeError):
    """Raised when the configured preference service cannot return valid data."""


class CustomMemoryBridge:
    def __init__(
        self,
        external_chat_service_url: str | None = None,
        service_token: str | None = None,
    ) -> None:
        self.service_url = (external_chat_service_url or settings.memory_service_url).rstrip("/")
        self.service_token = service_token or settings.memory_service_token

    async def get_user_long_term_preferences(self, user_id: str) -> dict[str, Any]:
        if not self.service_url:
            from app.agent_runtime import get_agent_runtime
            try:
                traveler = get_agent_runtime().for_user(user_id)
                engine = traveler.service.engine(user_id)
                preferences = {}
                for field in ("budget_tier", "dietary_choices", "preferred_transport", "travel_style", "favorite_environments", "pace", "dietary", "interests"):
                    answer = engine.recall(field, subject="Traveller", predicate=field, scope={})
                    if answer["answer_status"] == "supported":
                        values = [item["value"] for item in answer["evidence"] if item["accepted_for_current_use"]]
                        if values:
                            preferences[field] = values[0] if len(values) == 1 else values
                return preferences
            except Exception as error:
                raise MemoryServiceError("Iron Web 2 preference memory is unavailable") from error

        headers = {"Accept": "application/json"}
        if self.service_token:
            headers["Authorization"] = f"Bearer {self.service_token}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.service_url}/users/{user_id}/preferences",
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MemoryServiceError("The travel preference service is unavailable") from exc

        if not isinstance(payload, dict):
            raise MemoryServiceError("The travel preference service returned invalid data")
        preferences = payload.get("preferences", payload)
        if not isinstance(preferences, dict):
            raise MemoryServiceError("The travel preference service returned invalid preferences")
        return preferences

    async def filter_inventory_by_memory(
        self, user_id: str, raw_catalog: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        preferences = await self.get_user_long_term_preferences(user_id)
        return self.filter_inventory_by_preferences(raw_catalog, preferences)

    def filter_inventory_by_preferences(
        self, raw_catalog: list[dict[str, Any]], preferences: dict[str, Any]
    ) -> list[dict[str, Any]]:
        dietary_choices = self._string_set(preferences.get("dietary_choices"))
        preferred_modes = self._string_set(preferences.get("preferred_transport"))
        environments = self._string_set(preferences.get("favorite_environments"))
        ranked: list[tuple[float, int, dict[str, Any]]] = []

        for index, original in enumerate(raw_catalog):
            item = dict(original)
            score = self._score(item, preferences, dietary_choices, preferred_modes, environments)
            item["ai_match_score"] = round(score, 2)
            ranked.append((score, index, item))

        ranked.sort(key=lambda entry: (-entry[0], entry[1]))
        return [item for _, _, item in ranked]

    @staticmethod
    def _string_set(value: Any) -> set[str]:
        if isinstance(value, str):
            return {value.lower().replace("-", "_").replace(" ", "_")}
        if not isinstance(value, list):
            return set()
        return {
            str(item).lower().replace("-", "_").replace(" ", "_")
            for item in value
        }

    @staticmethod
    def _score(
        item: dict[str, Any],
        preferences: dict[str, Any],
        dietary: set[str],
        preferred_modes: set[str],
        environments: set[str],
    ) -> float:
        score = 1.0
        kind = item.get("catalogKind")
        price = item.get("price_inr")
        budget = str(preferences.get("budget_tier", "")).lower().replace("-", "_")
        budget_ranges = {
            "low": (0, 2500),
            "budget": (0, 2500),
            "mid_range": (2500, 10000),
            "luxury": (10000, float("inf")),
        }
        if budget.startswith("under"):
            budget = "low"
        elif "premium" in budget:
            budget = "luxury"
        elif "15,000" in budget or "30,000" in budget:
            budget = "luxury" if "30,000" in budget else "mid_range"
        elif "5,000" in budget:
            budget = "low"
        price_range = budget_ranges.get(budget)
        if isinstance(price, (int, float)) and price_range:
            lower, upper = price_range
            if lower <= price < upper:
                score += 0.2

        if kind == "food":
            diet = str(item.get("diet", "")).lower()
            prefers_vegetarian = dietary.intersection({"vegetarian", "veg"})
            prefers_vegan = "vegan" in dietary
            if (prefers_vegetarian and diet in {"vegetarian", "veg", "both"}) or (
                prefers_vegan and diet == "vegan"
            ):
                score += 0.5
            if "local_cafes" in dietary and str(item.get("kind", "")).lower() == "cafe":
                score += 0.25

        if kind == "transport":
            mode_aliases = {
                "rail": "train",
                "high_speed_rail": "train",
                "high_speed_train": "train",
                "scenic_train": "train",
                "budget_flight": "flight",
                "budget_flights": "flight",
                "scenic_bus": "bus",
                "scenic_road_trip": "bus",
                "scenic_road_trips": "bus",
            }
            modes = {mode_aliases.get(mode, mode) for mode in preferred_modes}
            if str(item.get("mode", "")).lower() in modes:
                score += 0.4

        search_values = [
            item.get("name"),
            item.get("description"),
            item.get("kind"),
            item.get("mode"),
            item.get("state"),
            item.get("slug"),
            item.get("destination_slug"),
            item.get("destination_name"),
            item.get("cuisine"),
        ]
        for key in ("tags", "amenities", "specialties", "destination_tags"):
            values = item.get(key) or []
            search_values.extend(values if isinstance(values, list) else [values])
        searchable = " ".join(str(value) for value in search_values if value).lower()
        travel_style = str(preferences.get("travel_style", "")).lower().replace("_", " ")
        if travel_style and travel_style in searchable:
            score += 0.3

        if any(environment.replace("_", " ") in searchable for environment in environments):
            score += 0.2

        return score
