"""Itinerary Planner: combines research into a practical day-wise schedule."""
from __future__ import annotations

import logging
import time

from agents.schemas import (
    AgentResult,
    AgentStatus,
    DraftItinerary,
    ItineraryDay,
    ItineraryStop,
    Evidence,
    TripBrief,
)

logger = logging.getLogger(__name__)

_DAY_START = {"relaxed": "09:30", "moderate": "09:00", "packed": "08:30"}
_MORNING_END = {"relaxed": "11:30", "moderate": "12:00", "packed": "12:30"}
_LUNCH = ("13:00", "14:00")
_AFTERNOON = {"relaxed": ("15:30", "17:30"), "moderate": ("15:00", "17:30"), "packed": ("14:30", "18:00")}


def _add_minutes(hhmm: str, minutes: int) -> str:
    hours, mins = map(int, hhmm.split(":"))
    total = hours * 60 + mins + minutes
    return f"{(total // 60) % 24:02d}:{total % 60:02d}"


class ItineraryPlanner:
    agent_id = "itinerary_planner"

    def draft(
        self,
        brief: TripBrief | None,
        *,
        destination_name: str | None = None,
        attractions: list = None,
        food_options: list = None,
        stay_options: list = None,
        transport_options: list = None,
        arrival_mode: str | None = None,
    ) -> AgentResult:
        started = time.perf_counter()
        try:
            attractions = attractions or []
            food_options = food_options or []
            stay_options = stay_options or []
            transport_options = transport_options or []

            duration = (brief.duration_days if brief and brief.duration_days else 3)
            pace = (brief.pace if brief and brief.pace else "moderate")
            title = (f"{duration}-day trip to {destination_name}"
                     if destination_name else f"{duration}-day trip")

            days: list[ItineraryDay] = []
            assumptions: list[str] = []
            attraction_cycle = list(attractions) or []
            lunch_cycle = list(food_options) or []
            attraction_index = lunch_index = 0

            for day_number in range(1, duration + 1):
                stops: list[ItineraryStop] = []
                if day_number == 1:
                    mode = arrival_mode or (transport_options[0].mode if transport_options else "surface transport")
                    stops.append(ItineraryStop(
                        day=1, start_time=_DAY_START[pace], end_time=_MORNING_END[pace],
                        title=f"Arrive by {mode}", kind="transport",
                        location=destination_name, est_cost_inr=0,
                        notes="travel time assumed within the morning window",
                    ))
                else:
                    stops.append(ItineraryStop(
                        day=day_number, start_time=_DAY_START[pace],
                        end_time=_MORNING_END[pace],
                        title=attraction_cycle[attraction_index % len(attraction_cycle)].name
                        if attraction_cycle else "Free morning to wander",
                        kind="attraction",
                        location=destination_name,
                        est_cost_inr=attraction_cycle[attraction_index % len(attraction_cycle)].price_per_person_inr or 0
                        if attraction_cycle else 0,
                        notes=(attraction_cycle[attraction_index % len(attraction_cycle)].why_fit
                               if attraction_cycle else None),
                        evidence=attraction_cycle[attraction_index % len(attraction_cycle)].evidence
                        if attraction_cycle else None,
                    ))
                    attraction_index += 1

                if lunch_cycle:
                    lunch = lunch_cycle[lunch_index % len(lunch_cycle)]
                    lunch_index += 1
                    stops.append(ItineraryStop(
                        day=day_number, start_time=_LUNCH[0], end_time=_LUNCH[1],
                        title=f"Lunch at {lunch.name}", kind="food",
                        location=destination_name,
                        est_cost_inr=lunch.approx_price_per_guest_inr or 0,
                        notes=lunch.dietary_fit,
                        evidence=lunch.evidence,
                    ))

                if day_number < duration:
                    start, end = _AFTERNOON[pace]
                    stops.append(ItineraryStop(
                        day=day_number, start_time=start, end_time=end,
                        title=attraction_cycle[attraction_index % len(attraction_cycle)].name
                        if attraction_cycle else "Local exploration",
                        kind="attraction",
                        location=destination_name,
                        est_cost_inr=attraction_cycle[attraction_index % len(attraction_cycle)].price_per_person_inr or 0
                        if attraction_cycle else 0,
                        evidence=attraction_cycle[attraction_index % len(attraction_cycle)].evidence
                        if attraction_cycle else None,
                    ))
                    attraction_index += 1
                else:
                    stops.append(ItineraryStop(
                        day=day_number, start_time=_AFTERNOON[pace][0],
                        end_time=_AFTERNOON[pace][1],
                        title="Pack up and head home", kind="buffer",
                        location=destination_name, est_cost_inr=0,
                    ))

                days.append(ItineraryDay(day=day_number,
                                         calendar_date=brief.start_date if brief and brief.has_dates() and duration >= day_number else None,
                                         stops=stops))

            stay = stay_options[0] if stay_options else None
            if stay:
                assumptions.append(f"Assumes a room at {stay.name} for all nights (per-night "
                                   f"₹{stay.price_per_night_inr:,}, availability unverified).")
            if not food_options:
                assumptions.append("Meal costs use a placeholder allowance; no venue data was available.")
            if not attraction_cycle:
                assumptions.append("No verified experiences were found; mornings are left open.")

            total = sum(stop.est_cost_inr for day in days for stop in day.stops)
            itinerary = DraftItinerary(
                title=title,
                days=days,
                total_est_cost_inr=total,
                assumptions=assumptions,
                alternatives=(["Swap the afternoon activity for a food walk if the weather turns."]
                              if attraction_cycle else []),
                unresolved_conflicts=[],
            )
            return AgentResult(
                agent_id=self.agent_id,
                status="ok",
                summary=f"Drafted a {duration}-day itinerary with {sum(len(d.stops) for d in days)} stops",
                itinerary=itinerary,
                evidence=[Evidence(source="itinerary_planner", kind="estimate", retrieved_at=int(time.time()),
                                   note="schedule built from catalog data; opening hours unverified")],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        return ["travel pace itinerary feedback"]
