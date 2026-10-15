"""Accommodation search tool (Stay Agent)."""
from __future__ import annotations

from .base import ToolResponse, get_tools

_KIND_ALIASES = {"hotel": "hotel", "hostel": "hostel", "homestay": "homestay",
                 "resort": "resort", "any": None}


def search_stays(
    destination_id: int | None = None,
    *,
    kind: str | None = None,
    max_price: int | None = None,
    amenity: str | None = None,
    min_rating: float | None = None,
    limit: int = 10,
) -> ToolResponse:
    backend, _live = get_tools()
    params: dict = {"limit": str(limit)}
    if destination_id is not None:
        params["destination_id"] = str(destination_id)
    normalized = _KIND_ALIASES.get((kind or "any").lower(), None)
    if normalized:
        params["type"] = normalized
    if max_price is not None:
        params["max_price"] = str(max_price)
    if amenity:
        params["amenity"] = amenity[:60]
    if min_rating is not None:
        params["min_rating"] = str(min_rating)
    response = backend.get("/stays", params)
    if response.ok:
        response.data = response.data[:limit]
    return response


def estimate_stay_total(price_per_night_inr: int | None, nights: int) -> int | None:
    """Total for the whole party is computed by the budget agent; this is a
    per-room total and always an estimate until a provider confirms."""
    if price_per_night_inr is None or nights < 1:
        return None
    return price_per_night_inr * nights
