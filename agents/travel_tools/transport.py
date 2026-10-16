"""Transport route search tool (Budget & Booking / Support agents)."""
from __future__ import annotations

from .base import ToolResponse, get_tools


def search_routes(
    destination_id: int | None = None,
    *,
    mode: str | None = None,
    max_price: int | None = None,
    limit: int = 10,
) -> ToolResponse:
    backend, _live = get_tools()
    params: dict = {"limit": str(limit)}
    if destination_id is not None:
        params["destination_id"] = str(destination_id)
    if mode and mode != "any":
        params["type"] = mode[:20]
    if max_price is not None:
        params["max_price"] = str(max_price)
    response = backend.get("/transport", params)
    if response.ok:
        response.data = response.data[:limit]
    return response
