"""Budget & Booking Agent: cost estimates, comparison, booking assistance.

Estimates are always labeled; a booking is only attempted with an explicit
``confirmed`` flag and an idempotency key, and success is reported strictly
from the provider response.
"""
from __future__ import annotations

import logging
import time

from agents.schemas import (
    AgentResult,
    AgentStatus,
    BudgetEstimate,
    BudgetLine,
    DraftItinerary,
    Evidence,
    MemoryContext,
    TripBrief,
)

from .travel_tools import booking as booking_tool
from .travel_tools import transport as transport_tool
from .validation.budget_validator import validate_budget

logger = logging.getLogger(__name__)

_CONTINGENCY_RATE = 0.10


class BudgetBookingAgent:
    agent_id = "budget_booking_agent"

    def estimate(
        self,
        brief: TripBrief | None,
        memory: MemoryContext | None = None,
        *,
        stay_options: list = None,
        transport_options: list = None,
        food_options: list = None,
        attractions: list = None,
        itinerary: DraftItinerary | None = None,
        nights: int = 2,
        party_size: int = 1,
        per_person: bool = True,
    ) -> AgentResult:
        started = time.perf_counter()
        try:
            stay_options = stay_options or []
            transport_options = transport_options or []
            food_options = food_options or []
            attractions = attractions or []

            lines: list[BudgetLine] = []

            stay_total = stay_options[0].total_price_inr if stay_options and stay_options[0].total_price_inr else None
            if stay_total is None and stay_options:
                stay_total = (stay_options[0].price_per_night_inr or 0) * nights
            if stay_total:
                lines.append(BudgetLine(category="stay", amount_inr=stay_total,
                                        basis="estimate", note="per room; availability unverified"))

            transport = transport_options[0] if transport_options else None
            transport_total = (transport.price_per_seat_inr or 0) * party_size if transport else 0
            if transport_total:
                lines.append(BudgetLine(category="transport", amount_inr=transport_total,
                                        basis="estimate",
                                        note=f"{transport.mode} sample fare; seats not held"))

            food_per_day = max((f.approx_price_per_guest_inr or 0) for f in food_options) if food_options else 400
            food_total = food_per_day * party_size * max(nights + 1, 1)
            if itinerary:
                food_total = sum(stop.est_cost_inr for day in itinerary.days for stop in day.stops
                                 if stop.kind == "food") * party_size
            lines.append(BudgetLine(category="food", amount_inr=food_total,
                                    basis="estimate", note="one sit-down meal per day"))

            activity_per_person = sum(a.price_per_person_inr or 0 for a in attractions[:4])
            activity_total = activity_per_person * party_size
            if itinerary:
                activity_total = sum(stop.est_cost_inr for day in itinerary.days for stop in day.stops
                                     if stop.kind == "attraction") * party_size
            if activity_total:
                lines.append(BudgetLine(category="activities", amount_inr=activity_total,
                                        basis="estimate", note="guide/experience fees"))

            subtotal = sum(line.amount_inr for line in lines)
            contingency = int(subtotal * _CONTINGENCY_RATE)
            lines.append(BudgetLine(category="contingency", amount_inr=contingency,
                                    basis="estimate", note="10% buffer for local travel and extras"))

            total = sum(line.amount_inr for line in lines)
            estimate = BudgetEstimate(
                per_person=per_person,
                lines=lines,
                total_inr=total,
                price_checked_at=None,  # no provider price check performed
                status="estimate",
                warnings=["All figures are estimates from catalog data, not live prices.",
                          "Includes the scheduled catalog activities and one meal per day; unverified transport and extra meals are excluded."],
            )
            if brief is not None:
                validation = validate_budget(estimate, brief)
                estimate.warnings.extend(w.message for w in validation.warnings)
            return AgentResult(
                agent_id=self.agent_id,
                status="ok",
                summary=f"Estimated ₹{total:,} "
                        + ("per person" if per_person else f"for {party_size} travellers"),
                budget=estimate,
                evidence=[Evidence(source="budget_calculator", kind="estimate",
                                   retrieved_at=int(time.time()),
                                   note="deterministic calculation from tool results")],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    # ------------------------------------------------------------------
    def attempt_booking(
        self,
        *,
        user_id: str,
        cart_items: list[dict],
        confirmed: bool,
        coupon_code: str | None = None,
        idempotency_key: str | None = None,
    ) -> AgentResult:
        """Explicit booking flow. Without ``confirmed=True`` nothing is sent."""
        started = time.perf_counter()
        response = booking_tool.request_booking(
            user_id=user_id,
            items=cart_items,
            confirmed=confirmed,
            coupon_code=coupon_code,
            idempotency_key=idempotency_key,
        )
        summary = booking_tool.booking_summary(response)
        status: AgentStatus
        if summary["status"] == "confirmed":
            text = f"Booking confirmed by provider (ref {summary.get('booking_id')})."
            status = "ok"
        elif summary["status"] == "pending":
            text = ("Request sent to the provider. Nothing is charged or confirmed until "
                    "the provider accepts it.")
            status = "ok"
        else:
            text = f"Booking could not be completed: {summary.get('detail')}"
            status = "failed"
        return AgentResult(
            agent_id=self.agent_id,
            status=status,
            summary=text,
            budget=BudgetEstimate(status=summary["status"], total_inr=summary.get("total_inr") or 0,
                                  price_checked_at=summary.get("checked_at"),
                                  warnings=[] if summary["status"] != "failed"
                                  else [str(summary.get("detail"))]),
            evidence=[Evidence(source="booking.provider", kind="mock" if summary.get("simulated")
                               else "live", retrieved_at=int(time.time()),
                               ref=str(summary.get("booking_id")),
                               note="simulated provider response" if summary.get("simulated") else None)],
            errors=[] if status == "ok" else [text],
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def refresh_routes(self, destination_id: int | None, mode: str | None = None):
        """Price check before presenting anything as current."""
        return transport_tool.search_routes(destination_id, mode=mode, limit=3)

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        return ["budget preferences currency booking decisions"]
