"""Authenticated Voyara → travel agents → three-tier memory composition.

The web process owns the stores. Each traveler gets an isolated durable
journal/vector/graph namespace; no browser can choose an actor or tenant.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import re
import secrets
from threading import RLock
import uuid

from sqlalchemy import select

from agents.memory_gateway.three_tier import (
    PROFILES,
    ThreeTierGateway,
    application_context_runtime,
)
from agents.orchestration.graph import TravelWorkflow
from agents.orchestrator import TravelOrchestrator
from agents.schemas import OrchestrationRequest
from agents.travel_tools.base import ToolResponse, TravelApiBackend, using_backend
from memory.observability import ObservationLog
from memory.shared.interpreter import TravelInterpreter
from memory.shared.service import PendingMemory, SharedMemoryService

from .config import settings
from .models import (
    AIMemory,
    Destination,
    FoodPlace,
    Guide,
    Stay,
    TransportRoute,
    UserProfile,
)

logger = logging.getLogger(__name__)
QUERY = re.compile(
    r"(?:please )?(?:plan my trip|plan an itinerary|show (?:my )?(?:itinerary|stays|food|budget|destinations|guides)|recommend (?:stays|food|destinations|guides)|what is my budget\??)",
    re.I,
)


class CatalogSnapshot(TravelApiBackend):
    """Public database rows copied before LangGraph starts worker threads."""

    def __init__(self, db):
        self.rows = {
            kind: [
                {c.name: getattr(obj, c.name) for c in model.__table__.columns}
                for obj in db.scalars(select(model).order_by(model.id).limit(1000))
            ]
            for kind, model in {
                "destinations": Destination,
                "stays": Stay,
                "food": FoodPlace,
                "guides": Guide,
                "transport": TransportRoute,
            }.items()
        }
        from .destination_content import REGIONS
        self.regions = {d["id"]: {d["id"], *(child["id"] for child in self.rows["destinations"]
                           if child["slug"] in REGIONS.get(d["slug"], ()))} for d in self.rows["destinations"]}
        names = {d["id"]: d["name"] for d in self.rows["destinations"]}
        for kind in ("stays", "food", "guides"):
            for row in self.rows[kind]:
                row["destination_name"] = names.get(row["destination_id"])

    def get(self, path, params=None):
        parts = path.strip("/").split("/")
        rows = list(self.rows.get(parts[0], []))
        params = params or {}
        if len(parts) == 2:
            rows = [r for r in rows if str(r["id"]) == parts[1]]
        for key in ("destination_id", "origin_id", "diet"):
            if params.get(key) is not None:
                if key == "destination_id" and parts[0] in {"stays", "food", "guides"}:
                    ids = self.regions.get(int(params[key]), {int(params[key])})
                    rows = [r for r in rows if r.get(key) in ids]
                else:
                    rows = [r for r in rows if str(r.get(key)) == str(params[key])]
        if params.get("q"):
            q = str(params["q"]).casefold()
            rows = [
                r for r in rows if q in json.dumps(r, ensure_ascii=False).casefold()
            ]
            if parts[0] == "destinations":
                exact=[r for r in rows if q in {str(r.get("name","")).casefold(),str(r.get("slug","")).casefold()}]
                rows=exact+[r for r in rows if r not in exact]
        for key, source in (
            ("amenity", "amenities"),
            ("tag", "tags"),
            ("specialty", "specialties"),
        ):
            if params.get(key):
                rows = [r for r in rows if params[key] in r.get(source, [])]
        if params.get("max_price") is not None:
            rows = [
                r
                for r in rows
                if r.get("price_inr") is not None
                and r["price_inr"] <= int(params["max_price"])
            ]
        return ToolResponse(
            data=rows[: int(params.get("limit", 20))], evidence_kind="live"
        )

    def post(self, path, body):
        return ToolResponse(
            error="Use the authenticated checkout to request bookings.",
            evidence_kind="live",
        )


class TravelerMemory:
    def __init__(
        self, user_id, root, context_runtime, *, engine_factory=None, namespace="voyara"
    ):
        self.lock = RLock()
        self.observations = ObservationLog()
        records, tokens = [], {}
        for actor in ["app_user", *PROFILES]:
            token = secrets.token_urlsafe(32)
            tokens[actor] = token
            records.append(
                dict(
                    tenant=user_id,
                    actor=actor,
                    role="user" if actor == "app_user" else "agent",
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                )
            )
        self.service = SharedMemoryService(
            root,
            records,
            namespace=namespace,
            engine_factory=engine_factory,
            autostart=False,
            context_runtime=context_runtime,
        )
        self.principals = {
            actor: self.service.authenticate(token) for actor, token in tokens.items()
        }
        self.user_id = user_id
        self.profile = None

    def submit(self, *, text, trip_id, claims, event_id=None):
        normalized, changes = [], []
        for claim in claims:
            current = None
            if claim.get("action") == "supersede":
                current = self.service.recall(
                    self.principals["app_user"],
                    query="Current " + claim["predicate"],
                    subject="Traveller",
                    predicate=claim["predicate"],
                    scope=claim["scope"],
                )
                if not current["evidence"]:
                    claim = dict(claim, action="assert")
            changes.append(dict(predicate=claim["predicate"], action=claim.get("action", "assert"), scope=claim.get("scope", {}), after=claim.get("value"), **({"before": ([row["value"] for row in current.get("evidence", [])][0] if len(current.get("evidence", [])) == 1 else [row["value"] for row in current.get("evidence", [])])} if current is not None else {})))
            normalized.append(claim)
        self.observations.invalidate(trip_id or None)
        self.observations.emit(trip_id, "memory_submitted", claims=len(normalized),
                               actions=[c.get("action", "assert") for c in normalized])
        receipt = self.service.submit(
            self.principals["app_user"],
            dict(
                event_id=event_id or uuid.uuid4().hex,
                text=text,
                subject="Traveller",
                scope={"trip_id": trip_id} if trip_id else {},
                session_id=trip_id,
                claims=normalized,
                confirmed=True,
            ),
        )
        while self.service.process_one():
            pass
        receipt = self.service.receipt(self.principals["app_user"], receipt["id"])
        self.observations.emit(trip_id, "memory_processed", event_id=receipt["id"],
                               status=receipt["status"], claims=len(normalized), changes=changes, memory_id=receipt.get("memory_id"))
        if receipt["status"] != "ready":
            raise PendingMemory([receipt])
        return receipt

    def save_requirements(self, trip_id, body):
        fields = body.model_dump(exclude_unset=True, mode="json")
        if "start_date" in fields:
            fields["dates"] = fields.pop("start_date") + " to " + fields.pop("end_date")
        claims = [
            dict(
                subject="Traveller",
                predicate=k,
                value=v,
                kind="rule"
                if k in {"budget", "traveller_count", "dietary"}
                else "fact"
                if k in {"destination", "dates", "currency"}
                else "preference",
                scope={"trip_id": trip_id},
                action="supersede",
                reason="Traveler saved Trip details.",
            )
            for k, v in fields.items()
        ]
        return self.submit(
            text="Confirmed Trip details: " + json.dumps(fields),
            trip_id=trip_id,
            claims=claims,
        )

    def sync_profile(self, db):
        profile = db.get(UserProfile, self.user_id)
        values = {}
        if profile:
            if profile.dietary_restrictions:
                values["dietary"] = (
                    profile.dietary_restrictions[0]
                    if len(profile.dietary_restrictions) == 1
                    else profile.dietary_restrictions
                )
            if profile.accessibility_needs:
                values["accessibility"] = profile.accessibility_needs
            pace = {"slow travel": "relaxed", "slow_travel": "relaxed"}.get(
                profile.travel_style, profile.travel_style
            )
            if pace in {"relaxed", "moderate", "packed"}:
                values["pace"] = pace
        # Only explicit context vocabulary is imported. Arbitrary snapshot JSON
        # is not promoted into instructions or authority.
        for snapshot in db.scalars(
            select(AIMemory)
            .where(AIMemory.user_id == self.user_id)
            .order_by(AIMemory.updated_at, AIMemory.id)
        ):
            for key in ("dietary", "pace", "interests"):
                if key in snapshot.value:
                    values[key] = snapshot.value[key]
        if self.profile == values:
            return
        # Re-read after a restart so removed preferences are retracted too.
        claims = []
        for key in ("dietary", "pace", "interests", "accessibility"):
            current = self.service.recall(
                self.principals["app_user"],
                query="Current " + key,
                subject="Traveller",
                predicate=key,
                scope={},
            )
            active = [
                e["value"]
                for e in current.get("evidence", [])
                if e.get("accepted_for_current_use")
            ]
            if key in values:
                if active == [values[key]]:
                    continue
                claims.append(
                    dict(
                        subject="Traveller",
                        predicate=key,
                        value=values[key],
                        kind="rule"
                        if key in {"dietary", "accessibility"}
                        else "preference",
                        scope={},
                        action="supersede",
                        reason="Saved application preferences.",
                    )
                )
            elif active:
                claims.append(
                    dict(
                        subject="Traveller",
                        predicate=key,
                        value=None,
                        kind="preference",
                        scope={},
                        action="retract",
                        reason="Application preference removed.",
                    )
                )
        if claims:
            self.submit(
                text="Saved traveler profile preferences.", trip_id="", claims=claims
            )
        self.profile = values

    def events(self, trip_id, after=0):
        return self.service.history(
            self.principals["app_user"], session_id=trip_id, after=after, limit=200
        )

    def forget_event(self, trip_id, event_id):
        self.observations.invalidate(trip_id, purge_history=True)
        self.observations.emit(trip_id, "memory_forget_requested")
        cursor = 0
        while True:
            page = self.events(trip_id, cursor)
            if any(e["receipt"]["id"] == event_id for e in page["events"]):
                self.service.forget(self.principals["app_user"], event_id)
                while self.service.process_one():
                    pass
                receipt = self.service.receipt(self.principals["app_user"], event_id)
                if receipt["status"] != "redacted":
                    raise PendingMemory([receipt])
                return
            if not page["events"]:
                raise ValueError("Memory event not found in this trip.")
            cursor = page["next_cursor"]

    def forget_trip(self, trip_id):
        self.observations.invalidate(trip_id, purge_history=True)
        self.observations.emit(trip_id, "trip_forget_requested")
        cursor = 0
        while True:
            page = self.events(trip_id, cursor)
            if not page["events"]:
                return
            for event in page["events"]:
                self.service.forget(self.principals["app_user"], event["receipt"]["id"])
            while self.service.process_one():
                pass
            for event in page["events"]:
                receipt = self.service.receipt(
                    self.principals["app_user"], event["receipt"]["id"]
                )
                if receipt["status"] != "redacted":
                    raise PendingMemory([receipt])
            cursor = page["next_cursor"]

    def delete_field(self, trip_id, predicate):
        if predicate not in {
            "destination",
            "dates",
            "budget",
            "currency",
            "traveller_count",
            "dietary",
            "pace",
            "interests",
            "mood",
        }:
            raise ValueError("Unknown trip field.")
        current = self.service.recall(
            self.principals["app_user"],
            query="Current " + predicate,
            subject="Traveller",
            predicate=predicate,
            scope={"trip_id": trip_id},
        )
        if not current["evidence"]:
            return {"status": "ready"}
        return self.submit(
            text="Traveler removed trip field " + predicate,
            trip_id=trip_id,
            claims=[
                dict(
                    subject="Traveller",
                    predicate=predicate,
                    value=None,
                    scope={"trip_id": trip_id},
                    action="retract",
                    reason="Traveler requested field deletion.",
                )
            ],
        )

    def reply(self, trip_id, text, page, catalog, before_validate=None, agentic=None):
        parsed = TravelInterpreter()(
            text, dict(subject="Traveller", scope={"trip_id": trip_id})
        )
        if parsed:
            self.submit(text=text, trip_id=trip_id, claims=parsed)
        elif not QUERY.fullmatch(text.strip()):
            return dict(
                status="needs_clarification",
                response="I could not safely turn that message into trip requirements. Save the exact destination, dates, total budget and travelers in Trip details, then ask ‘Plan my trip’. You can also send explicit updates such as ‘Lower my budget to INR 40000’.",
                agent_results=[],
                memory=[],
            )
        for _ in range(3):
            gateway = ThreeTierGateway(
                self.service, self.principals, self.user_id, trip_id,
                observer=self.observations
            )
            orchestrator = TravelOrchestrator(
                workflow=TravelWorkflow(gateway=gateway, checkpoint=False, agentic=agentic)
            )
            with using_backend(catalog):
                result = orchestrator.handle(
                    OrchestrationRequest(
                        request=text,
                        user_id=self.user_id,
                        session_id=trip_id,
                        page=page,
                    )
                )
            if before_validate:
                before_validate()
            if not gateway.packets:
                return dict(
                    status=result.status,
                    response=result.response,
                    agent_results=[],
                    memory=[],
                )
            if not gateway.validate_current():
                continue
            for item in result.agent_results:
                execution = item.execution.model_dump(mode="json") if item.execution else None
                self.observations.emit(trip_id, "agent_completed", agent_id=item.agent_id,
                    status=item.status, latency_ms=item.latency_ms, execution=execution)
            output = result.model_dump(mode="json")
            output.pop("memory_write_proposals", None)
            output["memory"] = gateway.diagnostics()
            budget = result.budget
            total = (
                budget.total_inr
                * (result.trip_brief.party_size if budget.per_person else 1)
                if budget
                else None
            )
            errors = [
                i.message for i in result.validation_issues if i.severity == "error"
            ]
            if total is not None and total > result.trip_brief.budget_total_inr:
                errors.append(
                    "The available catalog plan exceeds your current total budget. Adjust the plan or confirm a new budget."
                )
            if (
                errors
                or result.status == "failed"
                or any(r.status == "failed" for r in result.agent_results)
            ):
                output["status"] = "failed" if any(r.status == "failed" for r in result.agent_results) else "needs_clarification"
                output["response"] = " ".join(errors) or "A travel agent could not complete its work. Check the team’s execution details and NVIDIA configuration, then retry."
                output["itinerary"], output["budget"] = None, None
                return output
            return output
        return dict(
            status="context_changed",
            response="Your requirements changed while planning. Please try again using the latest details.",
            agent_results=[],
            memory=[],
        )


class AgentRuntime:
    def __init__(
        self,
        root=None,
        *,
        engine_factory=None,
        context_runtime=None,
        namespace="voyara",
    ):
        self.root = Path(root or settings.agent_memory_path)
        self.engine_factory, self.namespace = engine_factory, namespace
        self.context_runtime = context_runtime
        self.users, self.lock = {}, RLock()

    def for_user(self, user_id):
        with self.lock:
            if user_id not in self.users:
                if len(self.users) >= 32:
                    raise RuntimeError(
                        "This single-process demo has reached its active traveler limit."
                    )
                if self.context_runtime is None:
                    self.context_runtime = application_context_runtime(
                        tokenizer_path=settings.context_tokenizer_path,
                        tokenizer_id=settings.context_tokenizer_id,
                        use_gpu=settings.context_use_gpu,
                    )
                key = hashlib.sha256(user_id.encode()).hexdigest()[:24]
                self.users[user_id] = TravelerMemory(
                    user_id,
                    self.root / key,
                    self.context_runtime,
                    engine_factory=self.engine_factory,
                    namespace=self.namespace,
                )
            return self.users[user_id]

    def close(self):
        with self.lock:
            for user in self.users.values():
                user.service.close()
            self.users.clear()


runtime = AgentRuntime()


def get_agent_runtime():
    return runtime
