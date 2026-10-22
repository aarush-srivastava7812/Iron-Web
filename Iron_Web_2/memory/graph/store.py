"""Source-backed graph memory with bounded writes and optimistic revisions.

Optional NLP extraction proposes grounded claims; Python resolves named entities.
Model tools cannot choose identity, authority or confirmation.
Each event and its claims are published by one parameterized graph statement.
"""

import hashlib
import json
import math
import time
from threading import RLock
from uuid import uuid4
from weakref import WeakSet

from .models import Claim, canonical
from .retention import EvidenceCache, RetentionPolicy
from ..vector.store import MAX_CANDIDATES, MODEL, VectorMemory, checked_text
from ..vector.reranker import RERANKER_MODEL, default_reranker
from ..context import ContextProfile, build_context

DEFAULT_CANDIDATES = 50
DEFAULT_RESULTS = 50


class ConcurrentChange(RuntimeError):
    pass


class Memory:
    _instances = WeakSet()
    _instances_lock = RLock()

    def __init__(
        self,
        owner,
        *,
        role="agent",
        policy=None,
        clock=time.time,
        cache_timer=time.monotonic,
        reranker=None,
        candidate_limit=DEFAULT_CANDIDATES,
        result_limit=DEFAULT_RESULTS,
        profile=None,
        extractor=None,
        **settings,
    ):
        if role not in {"user", "agent", "tool"}:
            raise ValueError("Unknown caller role.")
        self.role = role
        self.policy = policy or RetentionPolicy()
        self.clock = clock
        self.reranker = reranker
        self.profile = ContextProfile.model_validate({} if profile is None else profile)
        self.extractor = extractor
        self._owns_extractor = False
        self._limits(candidate_limit, result_limit)
        self.candidate_limit, self.result_limit = candidate_limit, result_limit
        self.last_search = {}
        self.vectors = VectorMemory(owner, **settings)
        self.graph, self.lock = self.vectors.graph, self.vectors.lock
        self.graph.query(
            "MERGE (s:MemoryState {id:'state'}) ON CREATE SET s.revision=0"
        )
        indexes = self.graph.query("CALL db.indexes()").result_set
        for label, properties in (
            ("Claim", ("subject", "predicate", "scope_json", "id")),
            ("Source", ("scope_json", "id")),
        ):
            missing = [
                p
                for p in properties
                if not any(
                    r[0] == label and "RANGE" in r[2].get(p, []) for r in indexes
                )
            ]
            if missing:
                self.graph.create_node_range_index(label, *missing)
        for label in ("Source", "Claim", "Entity"):
            constraints = self.graph.query("CALL db.constraints()").result_set
            if not any(
                r[0] == "UNIQUE" and r[1] == label and r[2] == ["id"]
                for r in constraints
            ):
                self.graph.create_node_unique_constraint(label, "id")
        deadline = time.monotonic() + 10
        while any(
            r[1] in {"Source", "Claim", "Entity"} and r[4] != "OPERATIONAL"
            for r in self.graph.query("CALL db.constraints()").result_set
        ):
            if time.monotonic() >= deadline:
                raise RuntimeError("Graph identifier constraints are not operational.")
            time.sleep(0.02)
        self._cache = EvidenceCache(timer=cache_timer)
        self._seen_revision = self.revision()
        with self._instances_lock:
            self._instances.add(self)

    def __call__(self, operation, **arguments):
        methods = {
            "ingest": self.ingest,
            "recall": self.recall,
            "history": self.history,
            "search": self.search,
            "context": self.context,
            "forget": self.forget,
        }
        if operation not in methods:
            raise ValueError(
                "Supported operations: ingest, recall, history, search, context, forget."
            )
        # The slow provider call must not hold the database/cache lock. Publication
        # re-enters through __call__ with structured claims and keeps the CAS check.
        if operation == "ingest" and arguments.get("claims") is None:
            return self.ingest(**arguments)
        with self.lock:
            return methods[operation](**arguments)

    def revision(self):
        return int(
            self.graph.query(
                "MATCH (s:MemoryState {id:'state'}) RETURN s.revision"
            ).result_set[0][0]
        )

    def _invalidate(self, *, clear_embeddings=False):
        with self._instances_lock:
            instances = list(self._instances)
        for instance in instances:
            if instance.vectors.graph_name == self.vectors.graph_name:
                instance._cache.cache_clear()
                if clear_embeddings and instance.vectors.embeddings:
                    instance.vectors.embeddings.clear()

    @staticmethod
    def _scope(scope):
        if scope is None:
            scope = {}
        if not isinstance(scope, dict):
            raise ValueError("Scope must be an explicit JSON object.")
        return canonical(scope)

    def _times(self, at, known_at):
        now = int(self.clock())
        at, known_at = now if at is None else at, now if known_at is None else known_at
        if any(type(v) is not int or v < 0 or v > now for v in (at, known_at)):
            raise ValueError(
                "Recall times must be nonnegative integer timestamps, no later than now."
            )
        return at, known_at

    def _initial_usage(self, importance, pinned, now):
        return {
            "retention_base": 1.0 if pinned else min(0.99, importance),
            "pinned": pinned,
            "last_decay_at": now,
            "half_life_days": self.policy.half_life_days,
            "last_accessed": 0,
            "access_count": 0,
            "usage_version": 0,
            "recent_uses_json": "{}",
        }

    def _usage(self, ids, *, request_id=None, expected_revision=None):
        """Read/touch utility metadata with per-record CAS, separate from fact revision.

        The bounded 15-minute / 32-request retry window is not a permanent
        exactly-once ledger. A retry in that window cannot reinforce twice.
        """
        ids = list(set(ids))
        if not ids:
            return {}
        now = self.clock()
        token = (
            hashlib.sha256(checked_text(request_id).encode()).hexdigest()
            if request_id is not None
            else None
        )
        for _ in range(4):
            rows = self.graph.query(
                "MATCH(n) WHERE (n:Source OR n:Claim) AND n.id IN $ids "
                "RETURN n.id,n.retention_base,coalesce(n.pinned,n.protected,false),n.last_decay_at,n.half_life_days,"
                "n.last_accessed,n.access_count,n.usage_version,n.recent_uses_json,n.recorded_at",
                {"ids": ids},
            ).result_set
            states = {}
            updates = []
            for row in rows:
                (
                    sid,
                    base,
                    pinned,
                    decay,
                    half,
                    visited,
                    count,
                    version,
                    recent,
                    recorded,
                ) = row
                state = self._initial_usage(0.5, False, recorded)
                for key, value in zip(
                    (
                        "retention_base",
                        "pinned",
                        "last_decay_at",
                        "half_life_days",
                        "last_accessed",
                        "access_count",
                        "usage_version",
                        "recent_uses_json",
                    ),
                    (base, pinned, decay, half, visited, count, version, recent),
                ):
                    if value is not None:
                        state[key] = value
                seen = {
                    k: v
                    for k, v in json.loads(state["recent_uses_json"]).items()
                    if now - v < self.policy.dedup_seconds
                }
                if token is not None and token not in seen:
                    seen[token] = now
                    seen = dict(sorted(seen.items(), key=lambda p: p[1])[-32:])
                    props = {
                        "retention_base": self.policy.reinforce(state, now),
                        "last_decay_at": max(now, state["last_decay_at"]),
                        "last_accessed": max(now, state["last_accessed"]),
                        "access_count": state["access_count"] + 1,
                        "usage_version": state["usage_version"] + 1,
                        "recent_uses_json": canonical(seen),
                    }
                    updates.append(
                        {"id": sid, "version": state["usage_version"], "props": props}
                    )
                    state.update(props)
                states[sid] = state
            if updates:
                updated = self.graph.query(
                    "MATCH(state:MemoryState {id:'state'}) WHERE state.revision=$revision "
                    "WITH state UNWIND $items AS item MATCH(n) WHERE (n:Source OR n:Claim) "
                    "AND n.id=item.id AND coalesce(n.usage_version,0)=item.version "
                    "SET n += item.props RETURN n.id",
                    {"items": updates, "revision": expected_revision},
                ).result_set
                if len(updated) != len(updates):
                    if self.revision() != expected_revision:
                        raise ConcurrentChange(
                            "Evidence changed before recording its use; retry."
                        )
                    continue
            return {
                sid: {
                    "fuzzy_score": self.policy.score(s, now),
                    "pinned": s["pinned"],
                    "last_accessed": s["last_accessed"],
                    "access_count": s["access_count"],
                }
                for sid, s in states.items()
            }
        raise ConcurrentChange("Usage changed concurrently; retry the same request ID.")

    def _rows(self, subject, predicate, scope):
        return [
            dict(row[0])
            for row in self.graph.query(
                "MATCH (c:Claim) WHERE c.subject=$subject AND c.predicate=$predicate AND c.scope_json=$scope "
                "RETURN properties(c) ORDER BY c.recorded_at,c.id LIMIT 513",
                {"subject": subject, "predicate": predicate, "scope": scope},
            ).result_set
        ]

    def _recall(self, revision, subject, predicate, scope, at, known_at):
        rows = self._rows(subject, predicate, scope)
        if len(rows) > 512:
            raise ValueError(
                "Field history exceeds the bounded recall limit; archive or narrow the scope."
            )
        changes = self.graph.query(
            "MATCH (n)-[r:SUPERSEDES|RETRACTS]->(old:Claim) "
            "WHERE old.subject=$subject AND old.predicate=$predicate AND old.scope_json=$scope "
            "AND n.recorded_at<=$known AND r.effective_at<=$at RETURN old.id",
            {
                "subject": subject,
                "predicate": predicate,
                "scope": scope,
                "known": known_at,
                "at": at,
            },
        ).result_set
        ended = {r[0] for r in changes}
        active = [
            c
            for c in rows
            if c["recorded_at"] <= known_at
            and c.get("accepted_at", c["valid_from"]) <= at
            and c["valid_from"] <= at <= c["valid_until"]
            and c["id"] not in ended
            and c["action"] != "retract"
        ]
        accepted = [c for c in active if c["accepted"]]
        candidates = accepted or active
        values = {c["value_json"] for c in candidates}
        # Unconfirmed observations cannot displace a confirmed value, but disputes remain visible.
        conflicts = [
            c["id"]
            for c in active
            if accepted
            and c["cardinality"] == "single"
            and c["value_json"] not in values
        ]
        status = (
            "missing"
            if not candidates
            else "unconfirmed"
            if not accepted
            else "conflict"
            if conflicts
            or (len(values) > 1 and candidates[0]["cardinality"] == "single")
            else "supported"
        )
        evidence = []
        sources = (
            {
                r[0]: r[1:]
                for r in self.graph.query(
                    "MATCH(c:Claim)-[:SUPPORTED_BY]->(s:Source) WHERE c.id IN $ids "
                    "RETURN c.id,s.id,s.text,s.origin,s.confirmed",
                    {"ids": [c["id"] for c in active]},
                ).result_set
            }
            if active
            else {}
        )
        for c in active:
            source = sources.get(c["id"])
            if source is None:
                raise ConcurrentChange(
                    "Source evidence changed during interpretation; retry."
                )
            evidence.append(
                {
                    "claim_id": c["id"],
                    "value": json.loads(c["value_json"]),
                    "accepted": c["accepted"],
                    "protected": c["protected"],
                    "source_id": source[0],
                    "source_text": source[1],
                    "quote": c.get("evidence", ""),
                    "origin": source[2],
                    "confirmed": source[3],
                }
            )
        return {
            "status": status,
            "values": [json.loads(v) for v in sorted(values)]
            if status == "supported"
            else [],
            "evidence": evidence,
            "revision": revision,
            # Current-query cache must expire at the next temporal transition,
            # including a future replacement's valid_from/recorded_at.
            "_expires_at": min(
                [
                    t
                    for c in rows
                    for t in (c["valid_from"], c["valid_until"] + 1, c["recorded_at"], c.get("accepted_at", c["valid_from"]))
                    if t > min(at, known_at)
                ],
                default=2**63 - 1,
            ),
        }

    def recall(
        self,
        subject,
        predicate,
        scope=None,
        at=None,
        known_at=None,
        *,
        request_id=None,
        used=True,
    ):
        historical = at is not None or known_at is not None
        at, known_at = self._times(at, known_at)
        revision = self.revision()
        if revision != self._seen_revision:
            self._cache.cache_clear()
            self._seen_revision = revision
        subject, predicate, scope_json = (
            checked_text(subject),
            checked_text(predicate),
            self._scope(scope),
        )
        key = (
            "recall",
            revision,
            subject,
            predicate,
            scope_json,
            (at, known_at) if historical else "current",
        )
        result = self._cache.get(key)
        missed = result is None
        if missed:
            result = self._recall(
                revision, subject, predicate, scope_json, at, known_at
            )
        ids = [e["claim_id"] for e in result["evidence"]]
        relevant = result["status"] == "supported" and not historical
        token = (request_id or uuid4().hex) if used and relevant else None
        # Read authority first. Only accepted, applicable evidence is reinforced.
        accepted = [e for e in result["evidence"] if e["accepted"]]
        touched = (
            [i for e in accepted for i in (e["claim_id"], e["source_id"])]
            if token
            else []
        )
        usage = (
            self._usage(touched, request_id=token, expected_revision=revision)
            if touched
            else {}
        )
        usage.update(self._usage([i for i in ids if i not in usage]))
        score = max(
            (usage.get(e["claim_id"], {}).get("fuzzy_score", 0) for e in accepted),
            default=0,
        )
        if missed:
            ttl = 300 if score == 1 and relevant else 5 + 55 * score
            if not historical:
                ttl = min(ttl, result["_expires_at"] - self.clock())
            self._cache.put(key, result, score=score, eligible=relevant, ttl=ttl)
        for e in result["evidence"]:
            e["retention"] = usage.get(e["claim_id"], {})
        result.pop("_expires_at", None)
        if self.revision() != revision:
            self._cache.cache_clear()
            raise ConcurrentChange("Memory changed during recall; retry.")
        return result

    def _extracted_replay(self, sid, request):
        if self.graph.query(
            "MATCH(e:RedactedEvent {id:$id}) RETURN e.id", {"id": sid}
        ).result_set:
            raise ValueError("This event was forgotten; supply a new event ID.")
        existing = self.graph.query(
            "MATCH(s:Source {id:$id}) RETURN s.metadata_json", {"id": sid}
        ).result_set
        if not existing:
            return None
        info = json.loads(existing[0][0]).get("extraction", {})
        if not isinstance(info, dict) or info.get("request_sha256") != request:
            raise ValueError("Event ID was reused with different input.")
        ids = self.graph.query(
            "MATCH(c:Claim)-[:SUPPORTED_BY]->(s:Source {id:$id}) "
            "RETURN c.id ORDER BY c.position,c.id",
            {"id": sid},
        ).result_set
        return {
            "source_id": sid,
            "claim_ids": [r[0] for r in ids],
            "replayed": True,
            "revision": self.revision(),
            "extraction": info,
        }

    def _ingest_text(
        self,
        text,
        subject,
        scope,
        event_id,
        confirmed,
        metadata,
        recorded_at,
        importance,
    ):
        """Extract once per event; replay without another model call or invented facts."""
        from .extraction import NIMExtractor, Extraction

        if subject is None:
            raise ValueError("Text extraction requires an application-bound subject.")
        subject = checked_text(subject)
        if len(subject) > 200:
            raise ValueError("Bound subject exceeds 200 characters.")
        if "extraction" in (metadata or {}):
            raise ValueError("Extraction provenance metadata is application-managed.")
        event_id = checked_text(event_id) if event_id is not None else uuid4().hex
        sid = "source_" + hashlib.sha256(event_id.encode()).hexdigest()
        request = hashlib.sha256(
            canonical(
                {
                    "text": text,
                    "subject": subject,
                    "scope": scope,
                    "confirmed": confirmed,
                    "origin": self.role,
                    "metadata": metadata or {},
                    "importance": importance,
                }
            ).encode()
        ).hexdigest()
        with self.lock:
            replay = self._extracted_replay(sid, request)
            if replay is not None:
                return replay
        catalog = [
            dict(predicate=r[0], kind=r[1], cardinality=r[2])
            for r in self.graph.query(
                "MATCH(c:Claim) WHERE c.scope_json=$scope AND c.subject=$subject "
                "RETURN DISTINCT c.predicate,c.kind,c.cardinality LIMIT 128",
                {"scope": canonical(scope), "subject": subject},
            ).result_set
        ]
        existing_fields = {entry["predicate"] for entry in catalog}
        catalog += [
            {"predicate": field.predicate}
            for field in self.profile.required_fields
            if field.subject == subject and field.predicate not in existing_fields
        ]
        if self.extractor is None:
            with self.lock:
                if self.extractor is None:
                    self.extractor = NIMExtractor.from_env()
                    self._owns_extractor = True
        now = int(self.clock()) if recorded_at is None else recorded_at
        self._times(now, now)
        proposal = self.extractor.extract(
            text, field_catalog=catalog, reference_time=now
        )
        proposal = Extraction.model_validate(proposal)
        claims, entities = proposal.grounded(text, subject)
        info = {
            "extractor": self.extractor.name,
            "version": 1,
            "request_sha256": request,
            "status": "extracted" if claims else "episode_only",
            "entity_count": len(entities),
            "claim_count": len(claims),
        }
        with self.lock:
            replay = self._extracted_replay(sid, request)
            if replay is not None:
                return replay
            result = self(
                "ingest",
                text=text,
                claims=claims,
                scope=scope,
                event_id=event_id,
                confirmed=confirmed,
                metadata={**(metadata or {}), "extraction": info},
                recorded_at=now,
                importance=importance,
                _entities=entities,
            )
        return {**result, "extraction": info}

    def ingest(
        self,
        text,
        claims=None,
        scope=None,
        *,
        event_id=None,
        confirmed=False,
        metadata=None,
        recorded_at=None,
        importance=0.5,
        subject=None,
        _entities=None,
        _embedding=None,
        _application=None,
    ):
        text = checked_text(text)
        scope = {} if scope is None else scope
        if not isinstance(scope, dict) or (
            metadata is not None and not isinstance(metadata, dict)
        ):
            raise ValueError("Scope and metadata must be objects.")
        if type(confirmed) is not bool or (confirmed and self.role != "user"):
            raise PermissionError("Only a user-bound caller can confirm claims.")
        # Reject invalid JSON/utility before sending anything to the extractor.
        scope = json.loads(canonical(scope))
        metadata = json.loads(canonical(metadata or {}))
        if "_application" in metadata:
            raise ValueError("Application metadata is reserved for the trusted adapter.")
        importance = Claim(
            subject="source", predicate="utility", value=True, importance=importance
        ).importance
        if importance == 1 and not confirmed:
            raise PermissionError(
                "Non-decaying importance=1 requires user confirmation."
            )
        if claims is None:
            return self._ingest_text(
                text,
                subject,
                scope,
                event_id,
                confirmed,
                metadata,
                recorded_at,
                importance,
            )
        if not isinstance(claims, list) or len(claims) > 32:
            raise ValueError("Supply at most 32 structured claims.")
        parsed = [Claim.model_validate(c) for c in claims]
        if any(c.evidence is not None and c.evidence not in text for c in parsed):
            raise ValueError("Claim evidence must be a verbatim source quote.")
        # Importance is utility, not permission or evidence quality.
        if (
            importance == 1 or any(c.importance == 1 for c in parsed)
        ) and not confirmed:
            raise PermissionError(
                "Non-decaying importance=1 requires explicit user confirmation."
            )
        if any(c.action != "assert" for c in parsed) and not confirmed:
            raise PermissionError(
                "Replacing, correcting or retracting claims requires user confirmation."
            )
        application = json.loads(canonical(_application or {}))
        if not isinstance(application, dict):
            raise ValueError("Application metadata must be an object.")
        claim_metadata = application.get("claims", [{} for _ in parsed])
        if not isinstance(claim_metadata, list) or len(claim_metadata) != len(parsed) or any(not isinstance(item, dict) for item in claim_metadata):
            raise ValueError("Application claim metadata does not match the claims.")
        claim_scopes = [canonical(item.get("scope", scope)) for item in claim_metadata]
        if any(item.get("alias_target") for item in claim_metadata) and not confirmed:
            raise PermissionError("Identity changes require user confirmation.")
        keys = [(c.subject, c.predicate, claim_scopes[i]) for i, c in enumerate(parsed)]
        if len(keys) != len(set(keys)):
            raise ValueError("One event can change a field only once.")
        now = int(self.clock()) if recorded_at is None else recorded_at
        self._times(now, now)
        event_id = checked_text(event_id) if event_id is not None else uuid4().hex
        source_id = "source_" + hashlib.sha256(event_id.encode()).hexdigest()
        if self.graph.query(
            "MATCH(e:RedactedEvent {id:$id}) RETURN e.id", {"id": source_id}
        ).result_set:
            raise ValueError(
                "This event was forgotten; supply a new event ID for a new source."
            )
        content = {
            "text": text,
            "claims": claims,
            "scope": scope,
            "origin": self.role,
            "confirmed": confirmed,
            "metadata": metadata or {},
        }
        # Keep default-priority event IDs replayable from before retention metadata.
        if importance != 0.5:
            content["importance"] = importance
        if application:
            content["application"] = application
        digest = hashlib.sha256(canonical(content).encode()).hexdigest()
        revision = self.revision()
        existing = self.graph.query(
            "MATCH (s:Source {id:$id}) RETURN s.digest", {"id": source_id}
        ).result_set
        if existing:
            if existing[0][0] != digest:
                raise ValueError("Event ID was reused with different content.")
            return {"source_id": source_id, "replayed": True, "revision": revision}
        scope_json = canonical(scope)
        items = []
        for i, c in enumerate(parsed):
            field_scope = claim_scopes[i]
            prior = self._rows(c.subject, c.predicate, field_scope)
            if any(p["cardinality"] != c.cardinality for p in prior):
                raise ValueError("Field cardinality cannot change inside a scope.")
            current = self._recall(
                revision, c.subject, c.predicate, field_scope, now, now
            )["evidence"]
            if (
                self.role != "user"
                and any(p["protected"] for p in current)
                and c.kind in {"rule", "instruction"}
            ):
                raise PermissionError("Agents cannot rewrite protected rules.")
            targets = [p["claim_id"] for p in current] if c.action != "assert" else []
            explicit_targets = claim_metadata[i].get("targets")
            if explicit_targets is not None:
                if not isinstance(explicit_targets, list) or not explicit_targets:
                    raise ValueError("Change targets must name current claims in this exact field and scope.")
                if not set(explicit_targets).issubset(targets) and not (application.get("migration") and confirmed):
                    raise ValueError("Change targets must name current claims in this exact field and scope.")
                targets = [target for target in explicit_targets if target in targets]
            if c.action != "assert" and not targets and not (application.get("migration") and confirmed):
                raise ValueError("There is no current claim to replace or retract.")
            start = c.valid_from if c.valid_from is not None else now
            if start > c.valid_until:
                raise ValueError("Validity end precedes its start.")
            # A correction may repair history; a normal change starts when recorded.
            effective = claim_metadata[i].get("effective_at", now if application else start)
            props = {
                "id": source_id + "_" + str(i),
                "position": i,
                "subject": c.subject,
                "subject_id": c.subject,
                "subject_name": claim_metadata[i].get("subject_name", c.subject),
                "source_id": source_id,
                "memory_id": application.get("memory_id", source_id),
                "accepted_at": claim_metadata[i].get("accepted_at", now if application else start),
                "original_targets_json": canonical(claim_metadata[i].get("targets")),
                "reason": claim_metadata[i].get("reason", ""),
                "references": canonical(claim_metadata[i].get("references", [])),
                "references_json": canonical(claim_metadata[i].get("references", [])),
                "group_key": "field_" + hashlib.sha256(canonical([c.subject, c.predicate, json.loads(field_scope)]).encode()).hexdigest()[:32],
                "predicate": c.predicate,
                "value_json": canonical(c.value),
                "scope_json": field_scope,
                "kind": c.kind,
                "cardinality": c.cardinality,
                "action": c.action,
                "evidence": c.evidence or "",
                "valid_from": start,
                "valid_until": c.valid_until,
                "recorded_at": now,
                "accepted": confirmed or self.role == "tool",
                "protected": confirmed and c.kind in {"rule", "instruction"} and claim_metadata[i].get("protected") is not False,
            }
            props.update(
                self._initial_usage(
                    c.importance,
                    confirmed and (props["protected"] or c.importance == 1),
                    now,
                )
            )
            if claim_metadata[i].get("half_life_days") is not None:
                props["half_life_days"] = claim_metadata[i]["half_life_days"]
            items.append(
                {
                    "props": props,
                    "subject": c.subject,
                    "subject_entity": (_entities or {}).get(c.subject, {}),
                    "aliases": [claim_metadata[i]["alias_target"]] if claim_metadata[i].get("alias_target") else [],
                    "references": [
                        {"id": ref, "props": (_entities or {}).get(ref, {})}
                        for ref in ([c.object_id] if c.object_id else c.object_ids)
                    ],
                    "supersedes": targets
                    if c.action in {"supersede", "correct"}
                    else [],
                    "retracts": targets if c.action == "retract" else [],
                    "effective": effective,
                    "confirms": [
                        p["claim_id"]
                        for p in current
                        if canonical(p["value"]) == props["value_json"]
                    ],
                    "conflicts": [
                        p["claim_id"]
                        for p in current
                        if c.action == "assert"
                        and c.cardinality == "single"
                        and canonical(p["value"]) != props["value_json"]
                    ],
                }
            )
        vector = self.vectors._encoder().encode(text) if _embedding is None else _embedding
        if len(vector) != 384 or not all(type(v) in {float, int} and math.isfinite(v) for v in vector):
            raise ValueError("Embedding must contain 384 finite numbers.")
        query = (
            "MATCH (state:MemoryState {id:'state'}) WHERE state.revision=$revision "
            "CREATE (s:Source:VectorMemory {id:$id,text:$text,metadata_json:$metadata,embedding:vecf32($vector),"
            "model:$model,scope_json:$scope,origin:$origin,confirmed:$confirmed,digest:$digest,recorded_at:$now}) "
            "SET state.revision=state.revision+1 "
            "SET s += $usage SET s += $application "
        )
        if items:
            query += (
                "WITH state,s UNWIND $items AS item MERGE (e:Entity {id:item.subject}) "
                "ON CREATE SET e += item.subject_entity "
                "CREATE (c:Claim {id:item.props.id}) SET c += item.props "
                "CREATE (c)-[:ABOUT]->(e) CREATE (c)-[:SUPPORTED_BY]->(s) "
                "FOREACH (alias IN item.aliases | MERGE (target:Entity {id:alias}) "
                "CREATE (e)-[:CANONICAL_ALIAS {recorded_at:$now,evidence_claim_id:item.props.id}]->(target)) "
                "FOREACH (ref IN item.references | "
                "MERGE (o:Entity {id:ref.id}) ON CREATE SET o += ref.props "
                "CREATE (c)-[:REFERS_TO]->(o)) "
                "FOREACH (target IN item.supersedes | MERGE (old:Claim {id:target}) "
                "CREATE (c)-[:SUPERSEDES {effective_at:item.effective}]->(old)) "
                "FOREACH (target IN item.retracts | MERGE (old:Claim {id:target}) "
                "CREATE (c)-[:RETRACTS {effective_at:item.effective}]->(old)) "
                "FOREACH (target IN item.confirms | MERGE (old:Claim {id:target}) CREATE(c)-[:CONFIRMS]->(old)) "
                "FOREACH (target IN item.conflicts | MERGE (old:Claim {id:target}) CREATE(c)-[:CONTRADICTS]->(old)) "
            )
        query += "RETURN DISTINCT s.id,state.revision"
        result = self.graph.query(
            query,
            {
                "revision": revision,
                "id": source_id,
                "text": text,
                "metadata": canonical(metadata or {}),
                "vector": vector,
                "model": MODEL,
                "scope": scope_json,
                "origin": self.role,
                "confirmed": confirmed,
                "digest": digest,
                "now": now,
                "items": items,
                "application": {
                    "memory_id": application.get("memory_id", source_id),
                    "actor_id": application.get("actor_id", ""),
                    "event_id": event_id,
                    "user_confirmed": confirmed,
                    "quality": application.get("quality", 0.7),
                    "evidence_group": application.get("evidence_group", self.role),
                    "scope_keys": sorted(set(claim_scopes or [scope_json])),
                    "record_valid_from": application.get("record_valid_from", 0),
                    "record_valid_until": application.get("record_valid_until", 2**63 - 1),
                },
                "usage": self._initial_usage(
                    max([importance] + [c.importance for c in parsed]),
                    confirmed
                    and (
                        importance == 1
                        or any(item["props"]["protected"] or c.importance == 1 for item, c in zip(items, parsed))
                    ),
                    now,
                ),
            },
        ).result_set
        if not result:
            raise ConcurrentChange(
                "Memory changed before publication; retry the same event ID."
            )
        self._invalidate()
        return {
            "source_id": source_id,
            "claim_ids": [i["props"]["id"] for i in items],
            "revision": result[0][1],
            "replayed": False,
        }

    def history(self, subject, predicate, scope=None):
        rows = self._rows(
            checked_text(subject), checked_text(predicate), self._scope(scope)
        )
        if len(rows) > 512:
            raise ValueError("History exceeds limit; narrow the scope.")
        return rows

    @staticmethod
    def _limits(candidates, results):
        if type(candidates) is not int or not 1 <= candidates <= MAX_CANDIDATES:
            raise ValueError("Vector candidate limit must be 1 to 1000.")
        if type(results) is not int or not 1 <= results <= 100:
            raise ValueError("Final result limit must be 1 to 100.")

    def context(self, query, scope=None, limit=None, *, request_id=None, used=True):
        """Compile the configured persona, fixed cache, hot cache and similar memory."""
        return build_context(
            self, query, scope, limit, request_id=request_id, used=used
        )

    def _touch_results(self, results, revision, request_id):
        relevant = [
            r
            for r in results[:5]
            if r["distance"] <= self.policy.relevance_distance and self._usable(r)
        ]
        ids = {r["source_id"] for r in relevant}
        ids.update(
            e["claim_id"]
            for r in relevant
            for f in r["current_fields"]
            if f["status"] == "supported"
            for e in f["evidence"]
            if e["source_id"] == r["source_id"] and e["accepted"]
        )
        return self._usage(ids, request_id=request_id, expected_revision=revision)

    @staticmethod
    def _usable(result):
        return result["source_status"] == "episode" or any(
            f["status"] == "supported"
            and any(
                e["source_id"] == result["source_id"] and e["accepted"]
                for e in f["evidence"]
            )
            for f in result["current_fields"]
        )

    def _pinned(self, result, usage):
        if result["distance"] > self.policy.relevance_distance:
            return False
        if result["source_status"] == "episode":
            return usage.get(result["source_id"], {}).get("fuzzy_score") == 1
        return any(
            f["status"] == "supported"
            and e["accepted"]
            and e["source_id"] == result["source_id"]
            and usage.get(e["claim_id"], {}).get("fuzzy_score") == 1
            for f in result["current_fields"]
            for e in f["evidence"]
        )

    def search(
        self,
        query,
        scope=None,
        limit=None,
        *,
        candidate_limit=None,
        rerank=True,
        validate_pins=False,
        min_score=None,
        min_query_score=None,
        score_window=None,
        request_id=None,
        used=True,
    ):
        """Vector top-K (<=1000) -> current KG -> pins + reranked remainder.

        Pins bypass the cross-encoder only when relevant and currently valid.
        Pins and ordinary hits share one final budget (<=100 source chunks).
        Historical/unconfirmed evidence remains explicitly labelled, never pinned.
        Only relevant returned top-five hits count as used, not all candidates.
        """
        limit = self.result_limit if limit is None else limit
        candidate_limit = (
            self.candidate_limit if candidate_limit is None else candidate_limit
        )
        self._limits(candidate_limit, limit)
        if type(rerank) is not bool:
            raise ValueError("Rerank must be boolean.")
        if type(validate_pins) is not bool or (validate_pins and not rerank):
            raise ValueError("Pin relevance validation requires reranking.")
        if min_score is not None and (
            isinstance(min_score, bool)
            or not isinstance(min_score, (int, float))
            or not math.isfinite(min_score)
            or not rerank
        ):
            raise ValueError(
                "Minimum relevance score must be finite and requires reranking."
            )
        for bound in (min_query_score, score_window):
            if bound is not None and (
                isinstance(bound, bool)
                or not isinstance(bound, (float, int))
                or not math.isfinite(bound)
                or not validate_pins
            ):
                raise ValueError(
                    "Relative relevance filtering requires finite bounds and validated pins."
                )
        if score_window is not None and score_window <= 0:
            raise ValueError("Relevance score window must be positive.")
        started = time.perf_counter()
        query = checked_text(query)
        revision = self.revision()
        if revision != self._seen_revision:
            self._cache.cache_clear()
            self._seen_revision = revision
        now, scope_json = int(self.clock()), self._scope(scope)
        key = (
            "search",
            revision,
            scope_json,
            query,
            candidate_limit,
            limit,
            RERANKER_MODEL if rerank else "semantic-only",
            validate_pins,
            min_score,
            min_query_score,
            score_window,
        )
        cached = self._cache.get(key)
        missed = cached is None
        if missed:
            vector = self.vectors._encoder().encode(query, query=True)
            # Filter the private scope before vector top-K and graph interpretation.
            rows = self.graph.query(
                "MATCH (s:Source) WHERE (s.scope_json=$scope OR $scope IN coalesce(s.scope_keys,[])) AND s.recorded_at<=$now "
                "WITH s,vec.cosineDistance(s.embedding,vecf32($vector)) AS distance "
                "RETURN s.id,s.text,distance ORDER BY distance ASC,s.id LIMIT $limit",
                {
                    "scope": scope_json,
                    "vector": vector,
                    "limit": candidate_limit,
                    "now": now,
                },
            ).result_set
            fields_by_source = {}
            for sid, subject, predicate in self.graph.query(
                "MATCH(c:Claim)-[:SUPPORTED_BY]->(s:Source) WHERE s.id IN $ids AND c.scope_json=$scope "
                "RETURN DISTINCT s.id,c.subject,c.predicate",
                {"ids": [r[0] for r in rows], "scope": scope_json},
            ).result_set:
                fields_by_source.setdefault(sid, []).append((subject, predicate))
            interpreted = {}
            results, expires = [], now + 300
            for sid, text, distance in rows:
                fields = fields_by_source.get(sid, [])
                current_fields = []
                for subject, predicate in fields:
                    field = (subject, predicate)
                    if field not in interpreted:
                        interpreted[field] = self._recall(
                            revision, subject, predicate, scope_json, now, now
                        )
                    current = interpreted[field]
                    expires = min(expires, current["_expires_at"])
                    current_fields.append(
                        {k: v for k, v in current.items() if not k.startswith("_")}
                        | {"subject": subject, "predicate": predicate}
                    )
                source_status = (
                    "episode"
                    if not fields
                    else "current_evidence"
                    if any(
                        e["source_id"] == sid
                        for f in current_fields
                        for e in f["evidence"]
                    )
                    else "historical_evidence"
                )
                results.append(
                    {
                        "source_id": sid,
                        "source_text": text,
                        "distance": distance,
                        "source_status": source_status,
                        "current_fields": current_fields,
                    }
                )
            cached = {"results": results, "_expires_at": expires}
        results = cached["results"]
        all_ids = {r["source_id"] for r in results}
        all_ids.update(
            e["claim_id"]
            for r in results
            for f in r["current_fields"]
            for e in f["evidence"]
        )
        usage = self._usage(all_ids)
        if missed:
            vector_kg_ms = (time.perf_counter() - started) * 1000
            pins, remaining = [], []
            for result in results:
                (pins if rerank and self._pinned(result, usage) else remaining).append(
                    result
                )
            count = len(results)
            rerank_start = time.perf_counter()
            scored = 0
            to_score = pins + remaining if validate_pins else remaining
            if rerank and to_score and (validate_pins or len(pins) < limit):
                ranker = self.reranker or default_reranker(
                    self.vectors._encoder().device
                )
                scores = ranker.score(query, [r["source_text"] for r in to_score])
                scored = len(scores)
                for result, score in zip(to_score, scores):
                    result["rerank_score"] = score
                    result["retrieval_path"] = "reranked"
                remaining.sort(
                    key=lambda r: (-r["rerank_score"], r["distance"], r["source_id"])
                )
            else:
                for result in remaining:
                    result["rerank_score"] = None
                    result["retrieval_path"] = "semantic"
            for result in pins:
                if not validate_pins:
                    result["rerank_score"] = None
                result["retrieval_path"] = "pinned_cache"
            all_scored = pins + remaining
            anchors = [
                r
                for r in all_scored
                if self._usable(r)
                or any(
                    f["status"] == "conflict"
                    and e["accepted"]
                    and e["source_id"] == r["source_id"]
                    for f in r["current_fields"]
                    for e in f["evidence"]
                )
            ]
            best_score = max(
                (r["rerank_score"] for r in anchors if r["rerank_score"] is not None),
                default=None,
            )
            cutoff = (
                best_score - score_window
                if best_score is not None and score_window is not None
                else None
            )
            if min_query_score is not None and (
                best_score is None or best_score < min_query_score
            ):
                pins, remaining = [], []
            elif cutoff is not None:
                pins = [r for r in pins if r["rerank_score"] >= cutoff]
                remaining = [r for r in remaining if r["rerank_score"] >= cutoff]
            if min_score is not None:
                remaining = [
                    r
                    for r in remaining
                    if r["rerank_score"] is not None and r["rerank_score"] >= min_score
                ]
                if validate_pins:
                    pins = [r for r in pins if r["rerank_score"] >= min_score]
            if validate_pins:
                pins.sort(
                    key=lambda r: (-r["rerank_score"], r["distance"], r["source_id"])
                )
            for result in pins + remaining:
                result["cache_eligible"] = bool(rerank and self._pinned(result, usage))
            results = (pins + remaining)[:limit]
            cached["results"] = results
            cached["diagnostics"] = {
                "candidate_limit": candidate_limit,
                "candidate_count": count,
                "result_limit": limit,
                "pinned_candidates": len(pins),
                "reranked_candidates": scored,
                "vector_kg_ms": vector_kg_ms,
                "rerank_ms": (time.perf_counter() - rerank_start) * 1000,
                "best_score": best_score,
                "relevance_cutoff": cutoff,
            }
        self.last_search = dict(cached["diagnostics"], result_cache_hit=not missed)
        if not missed:
            self.last_search.update(vector_kg_ms=0.0, rerank_ms=0.0)
        relevant = [
            r
            for r in results[:5]
            if r["distance"] <= self.policy.relevance_distance and self._usable(r)
        ]
        token = (request_id or uuid4().hex) if used else None
        usage.update(self._touch_results(results, revision, token))
        priority = 0.0
        for r in relevant:
            state = usage.get(r["source_id"], {})
            score = state.get("fuzzy_score", 0)
            current_pin = any(
                f["status"] == "supported"
                and e["source_id"] == r["source_id"]
                and e["accepted"]
                and usage.get(e["claim_id"], {}).get("pinned")
                for f in r["current_fields"]
                for e in f["evidence"]
            )
            # Previously stored protected claims predate Source utility metadata.
            if current_pin:
                score = 1.0
            # A source pin from an expired rule cannot promote another unpinned field.
            if score == 1 and r["source_status"] != "episode" and not current_pin:
                score = 0.99
            priority = max(priority, score)
        if missed:
            self._cache.put(
                key,
                cached,
                score=priority,
                eligible=bool(relevant),
                ttl=min(
                    300 if priority == 1 else 5 + 55 * priority,
                    cached["_expires_at"] - self.clock(),
                ),
            )
        for r in results:
            r["retention"] = usage.get(r["source_id"], {})
            for f in r["current_fields"]:
                for e in f["evidence"]:
                    e["retention"] = usage.get(e["claim_id"], {})
        if self.revision() != revision:
            self._cache.cache_clear()
            raise ConcurrentChange("Memory changed during search; retry.")
        self.last_search["elapsed_ms"] = (time.perf_counter() - started) * 1000
        return results

    def forget(self, source_id):
        if self.role != "user":
            raise PermissionError("Only a user-bound caller can forget a source.")
        revision = self.revision()
        # Keep a content-free retraction marker where other history was ended by this source.
        # Otherwise forgetting a correction could silently resurrect the old assertion.
        result = self.graph.query(
            "MATCH(state:MemoryState {id:'state'}),(s:Source {id:$id}) WHERE state.revision=$revision "
            "OPTIONAL MATCH(c:Claim)-[:SUPPORTED_BY]->(s) WITH state,s,collect(c) AS claims "
            "OPTIONAL MATCH(c:Claim)-[r:ABOUT|REFERS_TO|CONFIRMS|CONTRADICTS]-(e) WHERE c IN claims "
            "WITH state,s,claims,collect(DISTINCT r) AS edges,"
            "collect(DISTINCT CASE WHEN e:Entity THEN e ELSE null END) AS entities "
            "CREATE (:RedactedEvent {id:s.id}) "
            "SET state.revision=state.revision+1 FOREACH(r IN edges | DELETE r) "
            "FOREACH(c IN claims | REMOVE c:Claim SET c:RedactedChange "
            "SET c = {id:c.id,recorded_at:c.recorded_at}) "
            "FOREACH(e IN entities | FOREACH(orphan IN CASE WHEN inDegree(e)+outDegree(e)=0 THEN [e] ELSE [] END | DELETE orphan)) "
            "DETACH DELETE s RETURN state.revision",
            {"id": checked_text(source_id), "revision": revision},
        ).result_set
        if not result and self.revision() != revision:
            raise ConcurrentChange("Memory changed before deletion; retry.")
        self._invalidate(clear_embeddings=True)
        return {"source_id": source_id, "forgotten": bool(result)}

    def close(self):
        if self._owns_extractor:
            self.extractor.close()
            self._owns_extractor = False
        self._cache.cache_clear()
        with self._instances_lock:
            self._instances.discard(self)
        self.vectors.close()
