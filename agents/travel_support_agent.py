"""Travel Support Agent: preparation, disruption handling, in-trip changes."""
from __future__ import annotations

import logging
import re
import time

from agents.schemas import (
    AgentResult,
    DraftItinerary,
    SupportGuidance,
    TripBrief,
)

from .travel_tools import weather as weather_tool

logger = logging.getLogger(__name__)

_REPLAN_WORDS = re.compile(r"\b(change|cancel|move|postpone|reschedule|delay|closed|storm|rain)\b", re.IGNORECASE)
_EMERGENCY_RE = re.compile(r"\b(emergency|ambulance|police|hospital|accident)\b", re.IGNORECASE)

_PACKING_BASE = ["Comfortable walking shoes", "Refillable water bottle", "Phone charger + power bank",
                 "Basic medicines and prescriptions", "ID copies"]


class TravelSupportAgent:
    agent_id = "travel_support_agent"

    def support(
        self,
        request: str,
        brief: TripBrief | None,
        memory=None,
        *,
        destination_id: int | None = None,
        destination_name: str | None = None,
        itinerary: DraftItinerary | None = None,
    ) -> AgentResult:
        started = time.perf_counter()
        try:
            text = request or ""
            if _EMERGENCY_RE.search(text):
                guidance = SupportGuidance(
                    topic="emergency",
                    guidance=("For emergencies contact local emergency services immediately "
                              "(India: 112). I can help with logistics afterwards, but I cannot "
                              "replace emergency services or official advisories."),
                    source_freshness="general",
                    risks=["life-safety situations require official responders"],
                )
                return AgentResult(agent_id=self.agent_id, status="ok",
                                   summary="Directed to official emergency services",
                                   guidance=guidance,
                                   latency_ms=int((time.perf_counter() - started) * 1000))

            needs_replanning = bool(_REPLAN_WORDS.search(text))
            topic = ("itinerary change" if needs_replanning
                     else "packing" if "pack" in text.lower()
                     else "transport guidance" if any(w in text.lower() for w in ("train", "flight", "bus", "reach", "airport"))
                     else "trip preparation")

            notes: list[str] = []
            affected: list[str] = []
            source_freshness = "general"
            weather = None
            if destination_id is not None and destination_name:
                weather = weather_tool.weather_note(destination_id, destination_name)
                source_freshness = "current"

            if topic == "packing":
                items = list(_PACKING_BASE)
                climate = weather.summary if weather else ""
                if "cold" in climate.lower() or "alpine" in climate.lower() or "highland" in climate.lower():
                    items += ["Warm layers", "Windproof jacket"]
                if "tropical" in climate.lower() or "coast" in climate.lower() or "monsoon" in climate.lower():
                    items += ["Light cottons", "Rain shell", "Sunscreen"]
                if brief and brief.duration_days:
                    items.append(f"Clothes for ~{brief.duration_days} days")
                for diet in (brief.dietary_requirements if brief else []):
                    items.append(f"Snack options that fit your {diet} requirement")
                notes = items
                guidance_text = ("Packing list tailored to destination climate, season and your "
                                 "stated needs. Adjust for personal habits.")
            elif needs_replanning:
                if itinerary:
                    affected = [f"day {day.day}: {day.stops[0].title}"
                                for day in itinerary.days if day.stops][:3]
                guidance_text = ("This change affects the draft itinerary. Tell me which day or "
                                 "stop to adjust and I will re-plan and re-check budget and "
                                 "schedules; bookings already sent to providers need explicit "
                                 "cancellation.")
                notes = ["Cross-agent impact detected: itinerary and budget may need revision."]
            else:
                guidance_text = ("Here is practical guidance based on your trip context. For "
                                 "advisories and closures, verify against official sources close "
                                 "to your travel date.")
                if weather:
                    notes.append(f"Climate note for {weather.location}: {weather.summary} "
                                 f"({weather.freshness}) — {weather.note}")

            guidance = SupportGuidance(
                topic=topic,
                guidance=guidance_text,
                source_freshness=source_freshness,  # type: ignore[arg-type]
                affected_items=affected,
                risks=[] if not needs_replanning else ["provider bookings may need separate cancellation"],
                needs_confirmation=False,
                needs_replanning=needs_replanning,
            )
            return AgentResult(
                agent_id=self.agent_id,
                status="ok",
                summary=f"Support guidance for {topic}",
                guidance=guidance,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed", errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    def memory_queries(self, brief: TripBrief | None) -> list[str]:
        return ["trip details support history preferences"]
