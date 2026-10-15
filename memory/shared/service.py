"""Receipt-first ingestion, token-bound tenancy and safe graph task ownership."""

from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
from threading import Event, RLock, Thread
import time

from pydantic import BaseModel, ConfigDict, Field

from memory.engine import MemoryEngine
from memory.lifecycle.models import ClaimInput, canonical_json
from memory.shared.journal import EventJournal
from memory.storage import coordinated_write


@dataclass(frozen=True)
class Principal:
    tenant: str
    actor: str
    role: str

    def __post_init__(self):
        if self.role not in {"user", "agent", "tool"} or any(
            not isinstance(v, str) or not v.strip() or len(v) > 200
            for v in (self.tenant, self.actor)
        ):
            raise ValueError("Invalid authenticated principal.")


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    event_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=100000)
    subject: str = Field(min_length=1, max_length=200)
    scope: dict = Field(default_factory=dict)
    session_id: str = Field(default="", max_length=200)
    claims: list[ClaimInput] | None = Field(default=None, min_length=1, max_length=32)
    confirmed: bool = False


class PendingMemory(RuntimeError):
    def __init__(self, receipts):
        super().__init__(
            "New memory is not ready; resolve pending or failed events before acting."
        )
        self.receipts = receipts


class RuntimeLock:
    """One local owner for embedded Qdrant and the journal, including processes."""

    def __init__(self, path):
        self.file = open(path, "a+b")
        self.file.seek(0)
        if not self.file.read(1):
            self.file.write(b"1")
            self.file.flush()
        self.file.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError(
                "This runtime already has a memory-service owner."
            ) from None

    def close(self):
        self.file.close()


class SharedMemoryService:
    def __init__(
        self,
        runtime,
        credentials,
        *,
        namespace="shared",
        engine_factory=None,
        interpreter=None,
        autostart=True,
        fault_hook=None,
        worker_count=2,
        context_runtime=None,
    ):
        if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", namespace):
            raise ValueError("Invalid deployment namespace.")
        self.root = Path(runtime).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.runtime_lock = RuntimeLock(self.root / "owner.lock")
        try:
            self.journal = EventJournal(self.root / "events.sqlite3")
            self.credentials = []
            for entry in credentials:
                digest = entry["token_hash"]
                if not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise ValueError("Credentials require SHA-256 token hashes.")
                if any(existing == digest for existing, _ in self.credentials):
                    raise ValueError("One credential cannot bind multiple principals.")
                self.credentials.append(
                    (digest, Principal(entry["tenant"], entry["actor"], entry["role"]))
                )
            if not self.credentials:
                raise ValueError("At least one configured principal is required.")
            self.namespace = namespace
            self.engine_factory = engine_factory or (
                lambda path, name: MemoryEngine(
                    config={"extraction_policy": "none"},
                    qdrant_path=str(path),
                    graph_name=name,
                )
            )
            self.interpreter = interpreter
            self.fault_hook = fault_hook
            self.engines, self.engine_lock = {}, RLock()
            self.gates = {p.tenant: RLock() for _, p in self.credentials}
            self.stop, self.wake = Event(), Event()
            self.context_access = None
            if context_runtime is not None:
                from memory.context.access import ContextAccess

                self.context_access = ContextAccess(self, context_runtime)
            if (
                not isinstance(worker_count, int)
                or isinstance(worker_count, bool)
                or not 1 <= worker_count <= 8
            ):
                raise ValueError("Worker count must be between one and eight.")
            self.workers = []
            if autostart:
                for index in range(worker_count):
                    worker = Thread(
                        target=self._loop,
                        name="memory-event-worker-" + str(index),
                        daemon=True,
                    )
                    self.workers.append(worker)
                    worker.start()
        except Exception:
            if hasattr(self, "journal"):
                self.journal.close()
            self.runtime_lock.close()
            raise

    def authenticate(self, token):
        if not isinstance(token, str) or len(token) < 24:
            raise PermissionError("Authentication required.")
        digest = hashlib.sha256(token.encode()).hexdigest()
        for expected, principal in self.credentials:
            if hmac.compare_digest(digest, expected):
                return principal
        raise PermissionError("Invalid credentials.")

    def _gate(self, principal):
        if principal.tenant not in self.gates:
            raise PermissionError("Unknown tenant.")
        return self.gates[principal.tenant]

    def engine(self, tenant):
        with self.engine_lock:
            if tenant not in {p.tenant for _, p in self.credentials}:
                raise PermissionError("Unknown tenant.")
            if tenant not in self.engines:
                key = hashlib.sha256(
                    canonical_json([str(self.root), self.namespace, tenant]).encode()
                ).hexdigest()[:24]
                directory = self.root / "tenants" / key
                directory.mkdir(parents=True, exist_ok=True)
                self.engines[tenant] = self.engine_factory(
                    directory / "vectors", self.namespace + "_" + key
                )
            return self.engines[tenant]

    def submit(self, principal, body):
        checked = EventInput.model_validate(body)
        if (
            not checked.text.strip()
            or not checked.subject.strip()
            or not checked.event_id.strip()
        ):
            raise ValueError("Event text, subject and ID must be nonempty.")
        if checked.confirmed and principal.role != "user":
            raise PermissionError(
                "Only an authenticated user can confirm an instruction or change."
            )
        if checked.claims:
            for claim in checked.claims:
                if (
                    claim.protected
                    or claim.action in {"correct", "supersede", "alias", "retract"}
                ) and not checked.confirmed:
                    raise PermissionError(
                        "This change requires authenticated user confirmation."
                    )
                if claim.aliases and principal.role == "agent":
                    raise PermissionError("Agents cannot alter trusted field labels.")
        value = checked.model_dump()
        value["principal"] = dict(
            tenant=principal.tenant, actor=principal.actor, role=principal.role
        )
        digest = hashlib.sha256(canonical_json(value).encode()).hexdigest()
        mid = (
            "evt_"
            + hashlib.sha256(
                (self.namespace + principal.tenant + checked.event_id).encode()
            ).hexdigest()[:32]
        )
        with self._gate(principal):
            receipt = self.journal.submit(
                principal.tenant,
                checked.event_id,
                digest,
                principal.actor,
                value,
                mid,
                True,
            )
            if receipt["status"] != "ready":
                self._invalidate_context(principal.tenant, value)
        self.wake.set()
        return receipt

    def receipt(self, principal, eid):
        row = self.journal.get(principal.tenant, eid)
        if row is None:
            raise ValueError("Unknown event.")
        return self.journal.public(row)

    def _ready(self, principal, scope=None):
        pending = self.journal.pending(principal.tenant, scope)
        if pending:
            for receipt in pending:
                row = self.journal.get(principal.tenant, receipt["id"])
                self._invalidate_context(principal.tenant, json.loads(row["payload"]))
            raise PendingMemory(pending)

    def _invalidate_context(self, tenant, payload=None):
        if self.context_access:
            self.context_access.purge(tenant, payload)

    def _ready_for_claims(self, principal, claim_ids):
        """Work inherits the scopes of its evidence; unknown/global stays global."""
        if (
            not isinstance(claim_ids, list)
            or not 1 <= len(claim_ids) <= 64
            or any(not isinstance(cid, str) for cid in claim_ids)
        ):
            self._ready(principal)
            return
        engine = self.engine(principal.tenant)
        scopes = {}
        for cid in claim_ids:
            claim = engine.lifecycle.claim(cid)
            if claim is None:
                self._ready(principal)
                return
            scope = json.loads(claim["scope_json"])
            if not scope.get("trip_id"):
                continue  # A profile dependency applies within the work's trip.
            scopes[canonical_json(scope)] = scope
        if not scopes:
            self._ready(principal)
            return
        for scope in scopes.values():
            self._ready(principal, scope)

    def _ready_for_work(self, principal, work_ids):
        if (
            not isinstance(work_ids, list)
            or not 1 <= len(work_ids) <= 64
            or any(not isinstance(wid, str) for wid in work_ids)
        ):
            raise ValueError("Handoff needs one to 64 work IDs.")
        engine = self.engine(principal.tenant)
        seen, frontier, claim_ids = set(), list(work_ids), set()
        while frontier:
            wid = frontier.pop()
            if wid in seen:
                continue
            seen.add(wid)
            if len(seen) > 64:
                self._ready(principal)
                return
            work = engine.lifecycle.work(wid)
            if work is None:
                self._ready(principal)
                return
            claim_ids.update(json.loads(work["used_claim_ids"]))
            frontier.extend(json.loads(work["dependency_ids"]))
        self._ready_for_claims(principal, list(claim_ids))

    def context(self, principal, **body):
        if not self.context_access:
            raise ValueError(
                "Context is unavailable: configure agent profiles and the consumer tokenizer first."
            )
        return self.context_access.context(principal, **body)

    def validate_context(self, principal, context_token):
        if not self.context_access:
            raise ValueError("Context is not configured.")
        return self.context_access.validate(principal, context_token)

    def _loop(self):
        while not self.stop.is_set():
            if not self.process_one():
                self.wake.wait(0.1)
                self.wake.clear()

    def process_one(self):
        row = self.journal.take()
        if row is None:
            return False
        try:
            if (
                row["prepared"]
                and json.loads(row["prepared"]).get("operation") == "redact"
            ):
                prepared = json.loads(row["prepared"])
                self.engine(row["tenant"]).delete(row["memory_id"], user_confirmed=True)
                self.journal.redact(row, prepared["by"])
                self._invalidate_context(row["tenant"], json.loads(row["payload"]))
                return True
            payload = json.loads(row["payload"])
            principal = Principal(**payload["principal"])
            if row["prepared"]:
                prepared = json.loads(row["prepared"])
            else:
                claims = payload["claims"]
                mode = "structured"
                if claims is None:
                    mode = getattr(
                        self.interpreter,
                        "name",
                        "custom_interpreter" if self.interpreter else "episode_only",
                    )
                    claims = (
                        self.interpreter(
                            payload["text"],
                            dict(subject=payload["subject"], scope=payload["scope"]),
                        )
                        if self.interpreter
                        else []
                    )
                parsed = [ClaimInput.model_validate(c).model_dump() for c in claims]
                if len(parsed) > 32:
                    raise ValueError("Interpreter exceeded the claim budget.")
                # Interpretation never supplies identity/authority or broadens caller scope.
                for claim in parsed:
                    if payload["claims"] is None and (
                        claim["subject"] != payload["subject"]
                        or claim["scope"] != payload["scope"]
                        or claim["action"] == "alias"
                    ):
                        raise ValueError(
                            "Interpreter broadened the explicit subject, scope or identity boundary."
                        )
                prepared = dict(
                    claims=parsed
                    or [
                        ClaimInput(
                            subject=payload["subject"],
                            predicate="conversation_episode",
                            value=payload["text"],
                            kind="episode",
                            scope=dict(
                                payload["scope"],
                                **(
                                    {"session_id": payload["session_id"]}
                                    if payload["session_id"]
                                    else {}
                                ),
                            ),
                        ).model_dump()
                    ],
                    mode=mode,
                    recorded_at=int(row["submitted"]),
                )
                self.journal.prepared(row, prepared)
            engine = self.engine(principal.tenant)
            if self.fault_hook:
                self.fault_hook("prepared", row, engine)
            self._repair_orphan(engine, row, payload, prepared)
            engine.add(
                payload["text"],
                memory_id=row["memory_id"],
                timestamp=prepared["recorded_at"],
                claims=prepared["claims"],
                source_info=dict(
                    origin=principal.role,
                    actor_id=principal.actor,
                    user_confirmed=payload["confirmed"],
                    event_id=payload["event_id"],
                    quality=0.5 if principal.role == "agent" else 0.9,
                    recorded_at=prepared["recorded_at"],
                ),
                metadata=dict(
                    service_receipt=row["id"],
                    interpretation=prepared["mode"],
                    session_id=payload["session_id"],
                ),
            )
            if self.fault_hook:
                self.fault_hook("published", row, engine)
            unclear_requirement = payload["confirmed"] and all(
                c["kind"] == "episode" for c in (prepared["claims"] or [])
            )
            final_status = "needs_review" if unclear_requirement else "ready"
            self.journal.finish(
                row,
                dict(
                    memory_id=row["memory_id"],
                    status=final_status,
                    interpretation=prepared["mode"],
                    affected_work=self._affected(engine, row["memory_id"]),
                ),
                status=final_status,
                reason="Requirement preserved as an event, but its meaning needs review."
                if unclear_requirement
                else None,
            )
            self._invalidate_context(principal.tenant, payload)
        except Exception as error:
            self.journal.fail(row, str(error))
        return True

    def _repair_orphan(self, engine, row, payload, prepared):
        """Replay only service-owned partial writes, never unrelated memory data."""
        with engine.graph_store.write_lock, engine._operation_lock:
            sources = engine.graph_store.execute(
                "MATCH(s:MemorySource {memory_id:$mid}) RETURN properties(s)",
                {"mid": row["memory_id"]},
            ).rows
            point = engine.vector_store.get_memory(row["memory_id"])
            if point and point["payload"].get("service_receipt") != row["id"]:
                raise ValueError("Recovery memory ID belongs to unrelated data.")
            if not sources and point:
                engine.vector_store.delete_memory(row["memory_id"])
            elif sources and not point:
                source = dict(sources[0][0])
                observations = engine.graph_store.get_memory_observations(
                    row["memory_id"]
                )
                claims = engine.graph_store.execute(
                    "MATCH(c:MemoryClaim {memory_id:$mid}) RETURN c.id,c.subject_id",
                    {"mid": row["memory_id"]},
                ).rows
                metadata = json.loads(source["metadata_json"])
                metadata.update(
                    memory_versioned=True,
                    memory_source_id=source["id"],
                    memory_claim_ids=[c[0] for c in claims],
                    extraction_status="typed_claims",
                    extraction_is_mock=False,
                    extractor_name="explicit_claim_contract",
                )
                embedding = engine.embedder.embed_single(payload["text"])
                with coordinated_write(
                    engine.vector_store, engine.graph_store, [row["memory_id"]]
                ):
                    engine.vector_store.upsert_memory(
                        memory_id=row["memory_id"],
                        text=payload["text"],
                        embedding=embedding,
                        entity_ids=sorted({o["entity_id"] for o in observations})
                        or list({c[1] for c in claims}),
                        valid_from=observations[0]["valid_from"] if observations else 0,
                        valid_until=observations[0]["valid_until"]
                        if observations
                        else 2**63 - 1,
                        importance=observations[0]["importance"]
                        if observations
                        else 1.0,
                        metadata=metadata,
                        timestamp=prepared["recorded_at"],
                    )

    @staticmethod
    def _affected(engine, mid):
        claims = engine.graph_store.execute(
            "MATCH(c:MemoryClaim {memory_id:$mid}) RETURN c.id", {"mid": mid}
        ).rows
        return [
            r[0]
            for r in engine.graph_store.execute(
                "MATCH(w:MemoryWork) WHERE w.invalidated_by IN $ids RETURN w.id",
                {"ids": [c[0] for c in claims]},
            ).rows
        ]

    def recall(self, principal, **request):
        with self._gate(principal):
            self._ready(principal, request.get("scope"))
            return self.engine(principal.tenant).recall(**request)

    def recall_path(self, principal, **request):
        with self._gate(principal):
            self._ready(principal, request.get("scope"))
            return self.engine(principal.tenant).recall_path(**request)

    def search(self, principal, **request):
        with self._gate(principal):
            self._ready(principal)
            return [
                r.model_dump() for r in self.engine(principal.tenant).search(**request)
            ]

    def record_work(
        self, principal, work_id, claim_ids, depends_on=None, description=""
    ):
        with self._gate(principal):
            self._ready_for_claims(principal, claim_ids)
            if depends_on:
                self._ready_for_work(principal, depends_on)
            # Unowned until an agent explicitly acquires a fenced execution attempt.
            result = self.engine(principal.tenant).record_work(
                work_id, claim_ids, depends_on, description
            )
            result.pop("lease_token", None)
            return result

    def claim_work(self, principal, work_id, lease_seconds=300):
        if (
            principal.role != "agent"
            or not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or not 1 <= lease_seconds <= 3600
        ):
            raise PermissionError(
                "An agent can acquire a task with a lease of 1–3600 seconds."
            )
        with self._gate(principal):
            self._ready_for_work(principal, [work_id])
            engine = self.engine(principal.tenant)
            with engine.graph_store.write_lock, engine._operation_lock, coordinated_write(
                engine.vector_store, engine.graph_store, []
            ):
                work = engine.lifecycle.work(work_id)
                if work is None:
                    raise ValueError("Unknown work.")
                if work["status"] == "completed":
                    work.pop("lease_token", None)
                    return dict(status="already_completed", work=work)
                if not engine.lifecycle.handoff([work_id])["can_continue"]:
                    raise ValueError(
                        "Work requires current evidence and completed prerequisites."
                    )
                now = time.time()
                active = work.get("lease_until", 0) > now
                if active:
                    if work.get("agent_id") != principal.actor:
                        raise ValueError("Another agent holds this task.")
                    return dict(status="owned", work=work)
                token, version = secrets.token_hex(24), work.get("owner_version", 0) + 1
                engine.graph_store.execute(
                    "MATCH(w:MemoryWork {id:$id}) SET w.agent_id=$actor,w.lease_until=$until,w.lease_token=$token,w.owner_version=$version",
                    dict(
                        id=work_id,
                        actor=principal.actor,
                        until=now + lease_seconds,
                        token=token,
                        version=version,
                    ),
                )
                return dict(status="owned", work=engine.lifecycle.work(work_id))

    def complete_work(self, principal, work_id, lease_token):
        with self._gate(principal):
            self._ready_for_work(principal, [work_id])
            engine = self.engine(principal.tenant)
            with engine.graph_store.write_lock, engine._operation_lock, coordinated_write(
                engine.vector_store, engine.graph_store, []
            ):
                work = engine.lifecycle.work(work_id)
                if (
                    work is None
                    or principal.role != "agent"
                    or work.get("agent_id") != principal.actor
                    or not hmac.compare_digest(work.get("lease_token", ""), lease_token)
                ):
                    raise PermissionError("Task ownership proof is missing or stale.")
                if (
                    work["status"] != "completed"
                    and work.get("lease_until", 0) <= time.time()
                ):
                    raise PermissionError(
                        "Task lease expired; acquire a fresh attempt."
                    )
                return engine.lifecycle.complete_work(work_id, principal.actor)

    def handoff(self, principal, work_ids):
        with self._gate(principal):
            self._ready_for_work(principal, work_ids)
            packet = self.engine(principal.tenant).handoff(work_ids)
            # Another agent gets state/evidence, never the owner's completion credential.
            for item in packet["work"]:
                item["work"].pop("lease_token", None)
                for prerequisite in item["prerequisites"]:
                    if prerequisite:
                        prerequisite.pop("lease_token", None)
            return packet

    def retry(self, principal, eid):
        row = self.journal.get(principal.tenant, eid)
        if row is None or (
            row["actor"] != principal.actor and principal.role != "user"
        ):
            raise PermissionError("Only the source actor or user can retry this event.")
        result = self.journal.retry(principal.tenant, eid)
        self.wake.set()
        return result

    def history(self, principal, **request):
        return self.journal.history(principal.tenant, **request)

    def identity(self, principal):
        return dict(tenant=principal.tenant, actor=principal.actor, role=principal.role)

    def work_list(self, principal, limit=50):
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
        ):
            raise ValueError("Work list requires a limit of 1–200.")
        engine = self.engine(principal.tenant)
        rows = engine.graph_store.execute(
            "MATCH(w:MemoryWork) RETURN properties(w) ORDER BY w.created_at DESC LIMIT $limit",
            {"limit": limit},
        ).rows
        result = []
        for row in rows:
            work = dict(row[0])
            work.pop("lease_token", None)
            result.append(work)
        return result

    def forget(self, principal, eid):
        if principal.role != "user":
            raise PermissionError(
                "An authenticated user must request evidence deletion."
            )
        with self._gate(principal), self.journal.lock, self.journal.db:
            row = self.journal.get(principal.tenant, eid)
            if row is None or row["status"] == "interpreting":
                raise ValueError("Unknown event or processing is still in progress.")
            if row["status"] == "redacted":
                return self.journal.public(row)
            self.journal.db.execute(
                "UPDATE events SET status='queued',prepared=? WHERE tenant=? AND id=?",
                (
                    json.dumps(dict(operation="redact", by=principal.actor)),
                    principal.tenant,
                    eid,
                ),
            )
            self._invalidate_context(principal.tenant, json.loads(row["payload"]))
        self.wake.set()
        return self.receipt(principal, eid)

    def withdraw(self, principal, eid):
        if principal.role != "user":
            raise PermissionError("A user must resolve a failed or pending event.")
        with self._gate(principal), self.journal.lock, self.journal.db:
            row = self.journal.get(principal.tenant, eid)
            if row is None or row["status"] not in {"queued", "failed", "needs_review"}:
                raise ValueError(
                    "Only queued, failed or unclear events may be withdrawn."
                )
            # Preserve original evidence; explicitly decline its application.
            self.journal.db.execute(
                "UPDATE events SET status='withdrawn' WHERE tenant=? AND id=?",
                (principal.tenant, eid),
            )
            self._invalidate_context(principal.tenant, json.loads(row["payload"]))
            return self.receipt(principal, eid)

    def close(self):
        self.stop.set()
        self.wake.set()
        for worker in self.workers:
            worker.join(timeout=90)
            if worker.is_alive():
                raise RuntimeError(
                    "Interpreter still running; resources were not closed beneath it."
                )
        for engine in self.engines.values():
            engine.close()
        if self.context_access:
            self.context_access.runtime.cache.invalidate()
            if self.context_access.runtime.ranker:
                self.context_access.runtime.ranker.clear()
        self.journal.close()
        self.runtime_lock.close()
