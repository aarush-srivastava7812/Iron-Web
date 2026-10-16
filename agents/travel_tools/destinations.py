"""Destination discovery tool (Explore / Consultant / Planner)."""
from __future__ import annotations

import time

from .base import ToolResponse, get_tools


def search_destinations(query: str | None = None, *, limit: int = 8, tag: str | None = None) -> ToolResponse:
    backend, _live = get_tools()
    params: dict = {"limit": str(limit)}
    if query:
        params["q"] = query[:120]
    if tag:
        params["tag"] = tag[:60]
    response = backend.get("/destinations", params)
    if not response.ok:
        return response
    response.data = response.data[:limit]
    return response


def get_destination(destination_id: int) -> ToolResponse:
    backend, _live = get_tools()
    return backend.get(f"/destinations/{destination_id}")


def destination_name_map(rows: list[dict]) -> dict[int, str]:
    return {row.get("id"): row.get("name", "") for row in rows if row.get("id") is not None}


def season_note(best_season: str | None) -> str | None:
    """Flag whether the destination's best season is verifiable right now."""
    if not best_season:
        return None
    return f"Best season listed as {best_season}; verify current conditions before finalizing." if time.gmtime().tm_mon else None
