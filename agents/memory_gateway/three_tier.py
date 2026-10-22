"""Bind an authenticated application trip to the current three-tier core."""

from __future__ import annotations

from datetime import date
import json
import time
from threading import Lock

from agents.schemas import (
    MemoryContext,
    MemoryItem,
    MemoryProvenance,
    TripBrief,
    WriteResult,
)
from memory.context.contracts import AgentProfile, ContextPolicy
from memory.context.runtime import ContextRuntime
from memory.context.tokens import TokenBudget


PROFILES = {
    "travel_orchestrator": "Coordinate only the requested specialists using current trip evidence. Resolve missing or disputed requirements before planning.",
    "trip_consultant": "Build the brief from confirmed structured fields. Never invent dates, a budget, or a party size.",
    "explore_agent": "Find catalog destinations matching the current destination and stated interests.",
    "stay_agent": "Compare catalog stays within the current budget. Do not claim verified availability or accessibility without evidence.",
    "food_guide_agent": "Recommend catalog food matching the current dietary requirements. Unknown dietary suitability requires review.",
    "tour_guide_agent": "Find catalog experiences matching the current trip. Do not relax protected requirements.",
    "itinerary_planner": "Build a dated draft from supported catalog results and current pace. Mark assumptions and unresolved constraints.",
    "budget_booking_agent": "Calculate indicative costs against the exact current budget. Advice never executes a booking or payment.",
    "travel_support_agent": "Provide preparation guidance using the current brief and clearly label unverified conditions.",
}


class _BytesConsumer:
    """Exact byte accounting for deterministic Python agents, not LLM tokens."""

    def encode(self, text):
        return list(text.encode("utf-8"))


def application_context_runtime(*, tokenizer_path="", tokenizer_id="", use_gpu=False):
    from memory.cache.cards import CardRouter

    if bool(tokenizer_path) != bool(tokenizer_id):
        raise ValueError("Configure both the consumer tokenizer path and identity.")
    tokens = (
        TokenBudget.from_file(tokenizer_path, tokenizer_id)
        if tokenizer_path and tokenizer_id
        else TokenBudget(_BytesConsumer(), "voyara-deterministic-utf8-v1")
    )
    return ContextRuntime(
        profiles=[
            AgentProfile(actor_id=key, version="voyara-v1", instructions=value)
            for key, value in PROFILES.items()
        ],
        tokens=tokens,
        policy=ContextPolicy(
            half_tokens=2048,
            card_tokens=1024,
            evidence_tokens=4096,
            context_limit=24000,
            output_tokens=2048,
        ),
        ranker=CardRouter(use_gpu=use_gpu),
    )


class MemoryNeedsInformation(RuntimeError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__(
            "Please confirm or update these trip details: "
            + ", ".join(
                key.replace("_", " ") + " (" + value + ")"
                for key, value in issues.items()
            )
            + ". Use Trip details to save exact requirements."
        )


class ThreeTierGateway:
    """One request's user/trip binding; no unscoped search or private cache."""

    graph_live = True

    def __init__(self, service, principals, user_id, trip_id, observer=None, external_evidence=None):
        self.service, self.principals = service, principals
        self.user_id, self.trip_id = user_id, trip_id
        self.observer = observer
        self.external_evidence = external_evidence
        self.packets = []
        self._lock = Lock()

    def retrieve(self, *, query, user_id, session_id, agent_id, **_):
        if user_id != self.user_id or session_id != self.trip_id:
            raise PermissionError(
                "The gateway is bound to the authenticated traveler and trip."
            )
        started = time.perf_counter()
        if self.observer:
            self.observer.emit(self.trip_id, "context_requested", agent_id=agent_id)
        task = {"stay_agent": "hotel", "budget_booking_agent": "flight"}.get(
            agent_id, "itinerary"
        )
        try:
            packet = self.service.context(
                self.principals[agent_id],
                subject="Traveller",
                scope={"trip_id": self.trip_id},
                session_id=self.trip_id,
                task_type=task,
                query=query,
            )
        except Exception:
            if self.observer:
                self.observer.emit(self.trip_id, "context_failed", agent_id=agent_id,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2))
            raise
        with self._lock:
            self.packets.append((agent_id, packet))
        if self.observer:
            self.observer.emit(self.trip_id, "context_assembled", agent_id=agent_id,
                packet=packet, status=packet["status"], cache_hit=packet["cache_hit"],
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                claims=len(packet["claim_ids"]), cards=len(packet["cards"]),
                tokens=packet["tokens"], residency=packet["residency"])
        if packet["status"] != "ready":
            raise MemoryNeedsInformation(packet["required_issues"])
        items = [
            MemoryItem(
                content=field["predicate"]
                + ": "
                + json.dumps(field["values"], ensure_ascii=False),
                provenance=MemoryProvenance(
                    memory_id=field["claim_ids"][0], retrieval_method="three_tier"
                ),
            )
            for field in packet["fields"]
            if field["status"] == "supported" and field["claim_ids"]
        ]
        return MemoryContext(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            graph_live=True,
            retrieval_mode="three_tier",
            items=items,
            packet=packet,
            external_evidence=(self.external_evidence or {}).get("evidence", []),
        )

    def trip_brief(self, context):
        fields = {}
        issues = {}
        supported_rules = {
            "destination",
            "dates",
            "budget",
            "currency",
            "traveller_count",
            "dietary",
            "pace",
            "hard_requirements",
        }
        for field in context.packet["fields"]:
            if field["required"] and field["predicate"] not in supported_rules:
                issues[field["predicate"]] = "catalog cannot verify this requirement"
            if field["status"] != "supported":
                continue
            values = field["values"]
            if len(values) != 1:
                issues[field["predicate"]] = "ambiguous"
            elif (
                field["predicate"] in fields and fields[field["predicate"]] != values[0]
            ):
                issues[field["predicate"]] = "conflicting scopes"
            else:
                fields[field["predicate"]] = values[0]
        if fields.get("currency") != "INR":
            issues["currency"] = "the catalog supports INR"
        party = fields.get("traveller_count")
        if type(party) is not int or not 1 <= party <= 30:
            issues["traveller_count"] = "confirm 1 to 30 travelers"
        budget = fields.get("budget")
        if type(budget) not in {int, float} or budget <= 0 or budget != int(budget):
            issues["budget"] = "confirm a positive total in whole INR"
        try:
            start, end = (
                date.fromisoformat(v) for v in fields.get("dates", "").split(" to ")
            )
            if not 1 <= (end - start).days <= 59:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            issues["dates"] = "confirm start and end dates, up to 60 days"
        diet = fields.get("dietary", [])
        diet = [diet] if isinstance(diet, str) else diet
        if not isinstance(diet, list) or any(not isinstance(v, str) for v in diet):
            issues["dietary"] = "confirm your dietary requirements"
        if fields.get("pace") not in {None, "relaxed", "moderate", "packed"}:
            issues["pace"] = "unsupported pace"
        if issues:
            raise MemoryNeedsInformation(issues)
        brief = TripBrief(
            destination=fields["destination"],
            start_date=start,
            end_date=end,
            duration_days=(end - start).days + 1,
            party_size=party,
            budget_total_inr=int(budget),
            dietary_requirements=diet,
            interests=fields.get("interests", []),
            pace=fields.get("pace"),
            hard_constraints=fields.get("hard_requirements", []),
        )
        return brief

    def validate_current(self, *, renew_expired=False):
        if renew_expired:
            renewed = []
            for actor, packet in self.packets:
                principal = self.principals[actor]
                if not self.service.validate_context(principal, packet["context_token"])["valid"]:
                    fresh = self.service.renew_context(principal, packet["context_token"])
                    if fresh is None:
                        return False
                    packet = dict(fresh, proof_renewed=True)
                renewed.append((actor, packet))
            self.packets = renewed
        valid = bool(self.packets) and all(
            self.service.validate_context(
                self.principals[actor], packet["context_token"]
            )["valid"]
            for actor, packet in self.packets
        )

        if self.observer:
            self.observer.emit(self.trip_id, "context_validated", valid=valid, packets=len(self.packets))
        return valid

    def diagnostics(self):
        return [
            dict(
                agent_id=actor,
                proof_renewed=packet.get("proof_renewed", False),
                cache_hit=packet["cache_hit"],
                tokens=packet["tokens"],
                residency=packet["residency"],
                cards=[c["card_id"] for c in packet["cards"]],
                claim_ids=packet["claim_ids"],
            )
            for actor, packet in self.packets
        ]

    def propose_writes(self, proposals):
        if self.observer:
            self.observer.emit(self.trip_id, "inferred_writes_rejected", count=len(proposals))
        # The original workflow proposes inferred preferences. User changes now
        # enter through confirmed intake; generated repetitions are not sources.
        return [
            WriteResult(
                status="rejected",
                reason="Use confirmed user intake for preference changes.",
            )
            for _ in proposals
        ]
