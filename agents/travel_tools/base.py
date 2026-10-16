"""Tool backend selection, shared HTTP helpers and response envelopes."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

from agents.config import settings
from agents.schemas import Evidence

logger = logging.getLogger(__name__)


@dataclass
class ToolResponse:
    """Every tool returns data + evidence so agents can cite freshness."""

    data: list[dict] = field(default_factory=list)
    error: str | None = None
    evidence_kind: str = "mock"

    @property
    def ok(self) -> bool:
        return self.error is None

    def evidence(self, source: str, ref: str | None = None, note: str | None = None) -> Evidence:
        return Evidence(
            source=source,
            kind="live" if self.evidence_kind == "live" else "mock",
            retrieved_at=int(time.time()),
            ref=ref,
            note=note or (None if self.ok else f"tool error: {self.error}"),
        )


class TravelApiBackend:
    """HTTP adapter for the existing travel application API."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or settings.travel_api_url).rstrip("/")
        self.token = token or settings.travel_api_token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, params: dict | None = None) -> ToolResponse:
        try:
            response = httpx.get(
                f"{self.base_url}/api{path}",
                params=params,
                headers=self._headers(),
                timeout=6.0,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload if isinstance(payload, list) else [payload]
            return ToolResponse(data=[item for item in items if isinstance(item, dict)],
                                evidence_kind="live")
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("travel api GET %s failed: %s", path, error)
            return ToolResponse(error=str(error), evidence_kind="live")

    def post(self, path: str, body: dict) -> ToolResponse:
        try:
            response = httpx.post(
                f"{self.base_url}/api{path}",
                json=body,
                headers=self._headers(),
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload if isinstance(payload, list) else [payload]
            return ToolResponse(data=[item for item in items if isinstance(item, dict)],
                                evidence_kind="live")
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("travel api POST %s failed: %s", path, error)
            return ToolResponse(error=str(error), evidence_kind="live")


class MockTravelBackend:
    """Deterministic sample backend for development and tests.

    Clearly labeled mock data — never presented as live availability.
    """

    DESTINATIONS = [
        {"id": 1, "slug": "goa", "name": "Goa", "state": "Goa", "country": "India",
         "tags": ["beach", "nightlife", "slow travel"], "best_season": "Nov-Feb",
         "avg_cost_inr": 28000, "climate": "Tropical coast",
         "description": "Salt air, Portuguese lanes and quiet coves."},
        {"id": 2, "slug": "jaipur", "name": "Jaipur", "state": "Rajasthan", "country": "India",
         "tags": ["heritage", "culture", "food"], "best_season": "Oct-Mar",
         "avg_cost_inr": 22000, "climate": "Hot semi-arid",
         "description": "Pink sandstone, bazaars and courtyard cafes."},
        {"id": 3, "slug": "manali", "name": "Manali", "state": "Himachal Pradesh", "country": "India",
         "tags": ["mountain", "adventure", "nature"], "best_season": "Mar-Jun",
         "avg_cost_inr": 24000, "climate": "Alpine mountain",
         "description": "Pine walks and valley roads."},
        {"id": 4, "slug": "munnar", "name": "Munnar", "state": "Kerala", "country": "India",
         "tags": ["nature", "relax", "mountain"], "best_season": "Sep-Mar",
         "avg_cost_inr": 19000, "climate": "Cool highland",
         "description": "Tea gardens and misty trails."},
        {"id": 5, "slug": "varanasi", "name": "Varanasi", "state": "Uttar Pradesh", "country": "India",
         "tags": ["spiritual", "culture", "heritage"], "best_season": "Oct-Mar",
         "avg_cost_inr": 16000, "climate": "Humid subtropical",
         "description": "Ghats, temples and morning boat rides."},
        {"id": 6, "slug": "rishikesh", "name": "Rishikesh", "state": "Uttarakhand", "country": "India",
         "tags": ["river", "wellness", "adventure"], "best_season": "Sep-Nov",
         "avg_cost_inr": 18000, "climate": "Temperate foothills",
         "description": "River paths and quiet mornings beside the Ganga."},
    ]

    def get(self, path: str, params: dict | None = None) -> ToolResponse:
        params = params or {}
        if path.startswith("/destinations"):
            data = self._destinations(params)
        elif path.startswith("/stays"):
            data = self._stays(params)
        elif path.startswith("/food"):
            data = self._food(params)
        elif path.startswith("/guides"):
            data = self._guides(params)
        elif path.startswith("/transport"):
            data = self._transport(params)
        else:
            return ToolResponse(error=f"mock backend has no data for {path}")
        return ToolResponse(data=data, evidence_kind="mock")

    def post(self, path: str, body: dict) -> ToolResponse:
        # The mock backend never confirms a booking; callers must treat the
        # result as a simulated request.
        return ToolResponse(
            data=[{"status": "requested", "simulated": True, "echo": body}],
            evidence_kind="mock",
        )

    # -- deterministic sample rows -----------------------------------------
    def _destinations(self, params: dict) -> list[dict]:
        query = str(params.get("q", "")).lower()
        rows = [d for d in self.DESTINATIONS
                if not query or query in d["name"].lower() or query in d["description"].lower()
                or any(query in tag for tag in d["tags"])]
        return rows if rows else self.DESTINATIONS

    def _stays(self, params: dict) -> list[dict]:
        dest = int(params["destination_id"]) if params.get("destination_id") else 1
        return [
            {"id": dest * 10 + 1, "destination_id": dest, "name": "Courtyard House", "kind": "hotel",
             "price_inr": 3200, "rating": 4.6, "amenities": ["wifi", "breakfast"]},
            {"id": dest * 10 + 2, "destination_id": dest, "name": "Backpackers' Nook", "kind": "hostel",
             "price_inr": 750, "rating": 4.3, "amenities": ["wifi"]},
            {"id": dest * 10 + 3, "destination_id": dest, "name": "Slow Living Homestay", "kind": "homestay",
             "price_inr": 1850, "rating": 4.8, "amenities": ["home-food", "wifi"]},
        ]

    def _food(self, params: dict) -> list[dict]:
        dest = int(params["destination_id"]) if params.get("destination_id") else 1
        rows = [
            {"id": dest * 10 + 1, "destination_id": dest, "name": "Family Kitchen", "kind": "restaurant",
             "cuisine": "Regional", "diet": "veg", "price_inr": 480, "rating": 4.7},
            {"id": dest * 10 + 2, "destination_id": dest, "name": "Corner Cafe", "kind": "cafe",
             "cuisine": "Cafe", "diet": "both", "price_inr": 550, "rating": 4.5},
            {"id": dest * 10 + 3, "destination_id": dest, "name": "Market Bites", "kind": "street_stall",
             "cuisine": "Street food", "diet": "both", "price_inr": 180, "rating": 4.6},
        ]
        diet = params.get("diet")
        if diet:
            rows = [row for row in rows if row["diet"] in {diet, "both"}]
        return rows

    def _guides(self, params: dict) -> list[dict]:
        dest = int(params["destination_id"]) if params.get("destination_id") else 1
        return [
            {"id": dest, "destination_id": dest, "name": "Story Walk", "languages": ["English", "Hindi"],
             "specialties": ["history", "food walks"], "price_inr": 1800, "rating": 4.9},
        ]

    def _transport(self, params: dict) -> list[dict]:
        dest = int(params["destination_id"]) if params.get("destination_id") else 1
        return [
            {"id": dest * 10 + 1, "destination_id": dest, "mode": "flight",
             "operator": "Sample Air", "duration_min": 145, "price_inr": 4900, "seats_available": 40},
            {"id": dest * 10 + 2, "destination_id": dest, "mode": "train",
             "operator": "Indian Railways (sample)", "duration_min": 420, "price_inr": 1150, "seats_available": 120},
        ]


_backend: TravelApiBackend | MockTravelBackend | None = None


def _get_backend():
    global _backend
    if _backend is None:
        _backend = TravelApiBackend()
    return _backend


def set_backend(backend) -> None:
    """Test helper: swap the shared backend (mock or live)."""
    global _backend
    _backend = backend


def reset_backend() -> None:
    set_backend(None)


def get_tools():
    """Return ``(backend, is_live)`` — tools read data only through this."""
    backend = _get_backend()
    return backend, isinstance(backend, TravelApiBackend)
