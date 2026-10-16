"""Trip Consultant: understands customer needs and produces a structured brief.

Extraction is deterministic (regex + vocabulary) with optional LLM refinement
through the shared NIM client. Unknown fields stay None — never fabricated.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta

from agents.schemas import (
    AgentResult,
    AgentStatus,
    MemoryContext,
    MemoryWriteProposal,
    TripBrief,
)

from .resource_manager.model_registry import get_nim_client

logger = logging.getLogger(__name__)

_KNOWN_DESTINATIONS = {
    "goa": "Goa", "jaipur": "Jaipur", "manali": "Manali", "munnar": "Munnar",
    "varanasi": "Varanasi", "udaipur": "Udaipur", "rishikesh": "Rishikesh",
    "kochi": "Kochi", "andaman": "Andaman Islands", "ladakh": "Ladakh",
    "kerala": "Kerala", "darjeeling": "Darjeeling", "shimla": "Shimla",
}

_INTEREST_WORDS = ["beach", "heritage", "culture", "food", "mountain", "adventure",
                   "nature", "relax", "spiritual", "wildlife", "nightlife", "wellness",
                   "romance", "trekking", "photography"]

_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), "dmy"),
]

_BUDGET_RE = re.compile(r"(?:budget|under|below|up to|within)\s*(?:of\s*)?(?:rs\.?|₹|inr)?\s*([\d,]+)(?:\s*(k|thousand|lakh|lakhs))?", re.IGNORECASE)
_PARTY_RE = re.compile(r"\b(?:for|party of|group of|we are|we're|family of)\s*(\d{1,2})\s*(?:people|persons|adults|members)?\b", re.IGNORECASE)
_DURATION_RE = re.compile(r"\b(\d{1,2})\s*[- ]?\s*(?:day|days|night|nights|d)\b", re.IGNORECASE)
_FLEX_RE = re.compile(r"\b(flexible|somewhere|anywhere|not sure|open to|suggest)\b", re.IGNORECASE)


class TripConsultant:
    agent_id = "trip_consultant"

    def extract(self, request: str, memory: MemoryContext | None = None) -> TripBrief:
        text = request or ""
        brief = TripBrief()

        # Destination: vocabulary match first, then capitalized unknown tokens.
        lowered = text.lower()
        for slug, name in _KNOWN_DESTINATIONS.items():
            if slug in lowered:
                brief.destination = name
                break

        if _FLEX_RE.search(text) and not brief.destination:
            brief.destination_flexible = True

        # Dates
        for pattern, kind in _DATE_PATTERNS:
            matches = pattern.findall(text)
            if len(matches) >= 2:
                try:
                    if kind == "iso":
                        first, second = (date(int(y), int(m), int(d)) for y, m, d in matches[:2])
                    else:
                        first = date(int(matches[0][2]), int(matches[0][1]), int(matches[0][0]))
                        second = date(int(matches[1][2]), int(matches[1][1]), int(matches[1][0]))
                    if second > first:
                        brief.start_date, brief.end_date = first, second
                        brief.duration_days = (second - first).days + 1
                        break
                except ValueError:
                    continue

        # Duration (also covers "3 days" without dates)
        duration_match = _DURATION_RE.search(text)
        if duration_match and brief.duration_days is None:
            brief.duration_days = min(int(duration_match.group(1)), 60)
            if brief.start_date is None:
                brief.start_date = date.today() + timedelta(days=14)
                brief.end_date = brief.start_date + timedelta(days=brief.duration_days - 1)

        # Party size
        party = _PARTY_RE.search(text)
        if party:
            brief.party_size = min(int(party.group(1)), 30)

        # Budget
        budget = _BUDGET_RE.search(text)
        if budget:
            amount = int(budget.group(1).replace(",", ""))
            unit = (budget.group(2) or "").lower()
            if unit in {"k", "thousand"}:
                amount *= 1_000
            elif unit.startswith("lakh"):
                amount *= 100_000
            if "per person" in lowered or "each" in lowered:
                brief.budget_per_person_inr = amount
            else:
                brief.budget_total_inr = amount

        # Interests / pace / preferences
        brief.interests = [word for word in _INTEREST_WORDS if word in lowered]
        if any(word in lowered for word in ["relax", "slow", "quiet", "unhurried"]):
            brief.pace = "relaxed"
        elif any(word in lowered for word in ["packed", "see everything", "as much as"]):
            brief.pace = "packed"
        elif any(word in lowered for word in ["balanced", "mix"]):
            brief.pace = "moderate"
        for mode in ["train", "flight", "bus", "car", "ferry"]:
            if mode in lowered:
                brief.transport_preferences.append(mode)
        for diet in ["vegetarian", "vegan", "halal", "jain", "gluten-free"]:
            if diet in lowered:
                brief.dietary_requirements.append(diet)
        for need in ["wheelchair", "step-free", "accessible", "low-sensory"]:
            if need in lowered:
                brief.accessibility_needs.append(need)
        for marker in ["must", "only", "definitely"]:
            for interest in brief.interests:
                if f"{marker} {interest}" in lowered:
                    brief.hard_constraints.append(f"{marker} {interest}")

        # Memory-informed defaults: past preferences only fill *soft* fields.
        if memory:
            self._apply_memory(brief, memory)

        self._finalize(brief)
        refined = self._llm_refine(text, brief)
        if refined is not None:
            brief = refined
            self._finalize(brief)
        return brief

    # ------------------------------------------------------------------
    def _apply_memory(self, brief: TripBrief, memory: MemoryContext) -> None:
        joined = " ".join(item.content.lower() for item in memory.items)
        for diet in ["vegetarian", "vegan", "halal", "jain", "gluten-free"]:
            if diet in joined and diet not in brief.dietary_requirements:
                brief.dietary_requirements.append(diet)
        if brief.pace is None:
            for item in memory.items:
                if "slow travel" in item.content.lower() or "relaxed pace" in item.content.lower():
                    brief.pace = "relaxed"
                    break

    def _llm_refine(self, request: str, brief: TripBrief) -> TripBrief | None:
        """Optional structured LLM refinement; falls back silently."""
        client = get_nim_client()
        if not client.available:
            return None
        system = (
            "Extract travel requirements as JSON with keys destination, start_date "
            "(YYYY-MM-DD or null), end_date, duration_days, party_size, budget_total_inr, "
            "budget_per_person_inr, interests (array), pace (relaxed|moderate|packed or null), "
            "dietary_requirements (array), accessibility_needs (array), "
            "destination_flexible (bool). Use null for unknown values; never invent details."
        )
        payload = client.chat_json(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": request[:1200]},
            ],
            max_tokens=400,
        )
        if not payload:
            return None
        merged = brief.model_dump()
        try:
            for key, value in payload.items():
                if key not in merged or value in (None, "", []):
                    continue
                if key in {"start_date", "end_date"} and isinstance(value, str):
                    try:
                        merged[key] = date.fromisoformat(value)
                    except ValueError:
                        continue
                elif key == "pace" and value not in {"relaxed", "moderate", "packed"}:
                    continue
                else:
                    merged[key] = value
            return TripBrief(**merged)
        except Exception as error:  # malformed LLM output keeps the deterministic brief
            logger.debug("LLM refinement rejected: %s", error)
            return None

    def _finalize(self, brief: TripBrief) -> None:
        missing: list[str] = []
        if brief.destination is None and not brief.destination_flexible:
            missing.append("destination")
        if not brief.has_dates() and brief.duration_days is None:
            missing.append("dates_or_duration")
        if brief.party_size is None:
            missing.append("party_size")
        if brief.effective_budget_per_person() is None:
            missing.append("budget")
        brief.missing_fields = missing
        if {"destination", "dates_or_duration"} & set(missing):
            brief.clarification_question = (
                "Where would you like to go, and around which dates (or for how many days)?"
            )
        elif "party_size" in missing:
            brief.clarification_question = "How many people are travelling?"
        elif "budget" in missing:
            brief.clarification_question = "Roughly what budget should I plan around (total or per person)?"
        else:
            brief.clarification_question = None
        brief.confidence = round(1.0 - 0.15 * len(missing), 2)

    # ------------------------------------------------------------------
    def memory_queries(self, brief: TripBrief) -> list[str]:
        queries = ["travel preferences budget pace dietary"]
        if brief.destination:
            queries.append(f"previous trips {brief.destination}")
        return queries

    def preference_writes(self, brief: TripBrief, user_id: str, session_id: str) -> list[MemoryWriteProposal]:
        """Only explicit, durable statements become preference memories."""
        proposals: list[MemoryWriteProposal] = []
        now = int(time.time())
        for diet in brief.dietary_requirements:
            proposals.append(MemoryWriteProposal(
                user_id=user_id, session_id=session_id, agent_id=self.agent_id,
                content=f"Dietary requirement: {diet}",
                kind="preference", importance=0.85, confidence=0.9,
            ))
        if brief.pace:
            proposals.append(MemoryWriteProposal(
                user_id=user_id, session_id=session_id, agent_id=self.agent_id,
                content=f"Preferred travel pace: {brief.pace}",
                kind="preference", importance=0.6, confidence=0.7,
            ))
        return proposals

    def run(self, request: str, memory: MemoryContext | None = None) -> AgentResult:
        started = time.perf_counter()
        try:
            brief = self.extract(request, memory)
            return AgentResult(
                agent_id=self.agent_id,
                status="needs_clarification" if brief.clarification_question else "ok",
                summary=self._summary(brief),
                trip_brief=brief,
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as error:
            return AgentResult(agent_id=self.agent_id, status="failed",
                               errors=[str(error)],
                               latency_ms=int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _summary(brief: TripBrief) -> str:
        parts = []
        if brief.destination:
            parts.append(brief.destination)
        elif brief.destination_flexible:
            parts.append("flexible destination")
        if brief.duration_days:
            parts.append(f"{brief.duration_days} days")
        if brief.party_size:
            parts.append(f"party of {brief.party_size}")
        budget = brief.effective_budget_per_person()
        if budget:
            parts.append(f"~₹{budget:,}/person")
        return "Trip brief: " + (", ".join(parts) or "details pending")
