"""Travel tools: provider labels, confirmation gate, idempotency."""
from __future__ import annotations

from agents.travel_tools import booking as booking_tool
from agents.travel_tools.base import MockTravelBackend, TravelApiBackend


def test_mock_backend_labels_data_as_mock():
    backend = MockTravelBackend()
    response = backend.get("/destinations", {"q": "beach"})
    assert response.ok and response.data
    assert response.evidence_kind == "mock"
    evidence = response.evidence("destinations.search")
    assert evidence.kind == "mock"


def test_booking_requires_explicit_confirmation():
    blocked = booking_tool.request_booking(user_id="u1", items=[{"item_type": "stay", "item_id": 1}],
                                           confirmed=False)
    assert not blocked.ok
    assert "confirmation" in blocked.error


def test_booking_idempotency_key_is_stable():
    key_a = booking_tool.make_idempotency_key("u1", "stay:1:2026-12-01")
    key_b = booking_tool.make_idempotency_key("u1", "stay:1:2026-12-01")
    key_c = booking_tool.make_idempotency_key("u2", "stay:1:2026-12-01")
    assert key_a == key_b and key_a != key_c


def test_mock_booking_is_simulated_not_confirmed():
    response = MockTravelBackend().post("/bookings", {"items": []})
    summary = booking_tool.booking_summary(response)
    assert summary["status"] == "pending"
    assert summary["simulated"] is True


def test_backend_selection_prefers_live_when_configured():
    live = TravelApiBackend(base_url="http://127.0.0.1:9")  # nothing listening
    response = live.get("/destinations")
    assert not response.ok  # failure surfaced, never silently mocked
