"""Restaurant and food-experience search tool (Food Guide Agent)."""
from __future__ import annotations

from .base import ToolResponse, get_tools


def search_food(
    destination_id: int | None = None,
    *,
    diet: str | None = None,
    cuisine: str | None = None,
    max_price: int | None = None,
    limit: int = 10,
) -> ToolResponse:
    backend, _live = get_tools()
    params: dict = {"limit": str(limit)}
    if destination_id is not None:
        params["destination_id"] = str(destination_id)
    if diet:
        params["diet"] = diet[:20]
    if cuisine:
        params["cuisine"] = cuisine[:60]
    if max_price is not None:
        params["max_price"] = str(max_price)
    response = backend.get("/food", params)
    if response.ok:
        response.data = response.data[:limit]
    return response
