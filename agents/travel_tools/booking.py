"""Booking tool with an explicit confirmation gate and idempotency keys.

Estimates are never bookings. A consequential booking action requires
``confirmed=True`` from the user; retries reuse the same idempotency key so
the provider-side request is not duplicated. Success is only reported as
``confirmed`` when the provider response says so.
"""
from __future__ import annotations

import hashlib
import json
import time

from .base import ToolResponse, get_tools


def make_idempotency_key(user_id: str, cart_signature: str) -> str:
    digest = hashlib.sha1(f"{user_id}|{cart_signature}".encode()).hexdigest()[:24]
    return f"bk_{digest}"


def request_booking(
    *,
    user_id: str,
    items: list[dict],
    confirmed: bool,
    idempotency_key: str | None = None,
    coupon_code: str | None = None,
) -> ToolResponse:
    if not confirmed:
        return ToolResponse(
            data=[],
            error="booking requires explicit user confirmation before any provider call",
            evidence_kind="live",
        )
    if not items:
        return ToolResponse(data=[], error="no items to book")
    backend, _live = get_tools()
    key = idempotency_key or make_idempotency_key(
        user_id, json.dumps(items, sort_keys=True, default=str)
    )
    body: dict = {"items": items, "idempotency_key": key}
    if coupon_code:
        body["coupon_code"] = coupon_code
    response = backend.post("/bookings", body)
    if response.ok:
        for row in response.data:
            row["idempotency_key"] = key
    return response


def booking_summary(response: ToolResponse) -> dict:
    """Normalize a booking response into a status the Budget agent can report."""
    if not response.ok or not response.data:
        return {"status": "failed", "detail": response.error or "no provider response"}
    row = response.data[0]
    status = str(row.get("status", "unknown"))
    # Only trust explicit provider confirmation; requests stay "pending".
    if status not in {"confirmed", "requested", "pending", "cancelled", "failed"}:
        status = "pending"
    return {
        "status": "pending" if status == "requested" else status,
        "booking_id": row.get("id"),
        "total_inr": row.get("total_inr"),
        "simulated": bool(row.get("simulated", False)),
        "checked_at": int(time.time()),
        "idempotency_key": row.get("idempotency_key"),
    }
