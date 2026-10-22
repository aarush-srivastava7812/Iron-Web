"""Application contract over Iron Web 2's single FalkorDB memory store.

The event journal, context proofs and work leases remain application concerns.
Sources, embeddings, temporal claims and retention belong to Iron Web 2. The
legacy engine is retained only for explicit imports and migration comparisons.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from functools import lru_cache
from threading import RLock
from uuid import uuid4

import numpy as np

from memory.graph.falkordb_store import FalkorDBGraphStore
from memory.lifecycle.models import ClaimInput, SourceInput, canonical_json
from memory.lifecycle.service import MemoryLifecycle, subject_id
from memory.models import DeviceStatus, MemoryRecord, MemorySearchResult


@lru_cache(maxsize=2)
def application_encoder(device):
    from Iron_Web_2.memory.vector.store import Embeddings
    return Embeddings(
        Path(
            os.getenv(
                "FASTEMBED_CACHE_PATH",
                str(Path(__file__).resolve().parents[1] / "Iron_Web_2/data/models"),
            )
        ),
        device=device,
    )


class ApplicationGraph(FalkorDBGraphStore):
    """Keep control-plane query contracts while using the native claim labels."""

    native_memory = True

    def execute(self, query, params=None):
        query = query.replace(":MemoryClaim", ":Claim").replace(
            ":MemorySource", ":Source"
        )
        return super().execute(query, params)


class ApplicationEmbeddings:
    def __init__(self, encoder):
        from Iron_Web_2.memory.vector.store import MODEL
        self.encoder = encoder
        self.model_name = MODEL
        self.provider = (
            "CUDAExecutionProvider"
            if encoder.device == "cuda"
            else "CPUExecutionProvider"
        )

    def embed_single(self, text, **_):
        tokens = self.encoder.tokenizer.encode(text).ids
        if len(tokens) <= 450:
            return np.asarray(self.encoder.encode(text), dtype=np.float32)
        # Long event text is retained verbatim. Pool bounded passage windows,
        # rather than accepting an embedding model's silent token truncation.
        parts = [
            self.encoder.tokenizer.decode(tokens[i : i + 384])
            for i in range(0, len(tokens), 384)
        ]
        vectors = np.asarray(
            [self.encoder.encode(p) for p in parts if p.strip()], dtype=np.float32
        )
        value = vectors.mean(axis=0)
        return value / max(float(np.linalg.norm(value)), 1e-12)

    def embed(self, texts):
        return np.asarray([self.embed_single(t) for t in texts])


class ApplicationVectors:
    dimension = 384
    distance = "Cosine"
    collection_name = "Source:VectorMemory"
    native_memory = True

    def __init__(self, engine):
        self.engine = engine
        self.path = None

    def get_memory(self, mid):
        record = self.engine.get(mid)
        if record is None:
            return None
        return {
            "id": mid,
            "payload": dict(
                record.metadata,
                text=record.content,
                entity_ids=record.entity_ids,
                timestamp=record.timestamp,
                valid_from=record.valid_from,
                valid_until=record.valid_until,
                importance=record.importance,
            ),
        }

    def get_all_memories(self, **_):
        return [self.get_memory(mid) for mid in self.engine.memory_ids()]

    def count(self):
        return len(self.engine.memory_ids())

    def close(self):
        pass


class ApplicationLifecycle(MemoryLifecycle):
    """Reuse work and vocabulary policies, resolve evidence through Iron Web 2."""

    def __init__(self, engine):
        self.engine = engine
        super().__init__(
            engine.graph_store,
            engine.vector_store,
            {
                "max_related_claims": 512,
                "max_affected_work": 512,
                "fuzzy_enabled": True,
            },
        )

    def ensure_schema(self):
        indexes = self._rows(
            "CALL db.indexes() YIELD label,properties RETURN label,properties"
        )
        if not any(
            label == "MemoryWork" and "id" in properties
            for label, properties in indexes
        ):
            self._rows("CREATE INDEX FOR (w:MemoryWork) ON (w.id)")

    def group(self, claim, at=None, historical=False, known_at=None):
        rows = self._rows(
            "MATCH(c:MemoryClaim) WHERE c.subject_id IN $subjects AND c.predicate=$predicate "
            "AND c.scope_json=$scope RETURN properties(c) LIMIT $limit",
            subjects=self.equivalent_subjects(claim["subject_id"], known_at),
            predicate=claim["predicate"],
            scope=claim["scope_json"],
            limit=self.limit + 1,
        )
        return [dict(r[0]) for r in self._bounded(rows)]

    def active(self, claim, at, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        result = self.engine.native._recall(
            self.engine.native.revision(),
            claim["subject_id"],
            claim["predicate"],
            claim["scope_json"],
            at,
            known_at,
        )
        return any(e["claim_id"] == claim["id"] for e in result["evidence"])

    def selected(self, claims, at, mode, known_at=None):
        known_at = int(time.time()) if known_at is None else known_at
        return [
            c
            for c in claims
            if c["recorded_at"] <= known_at
            and (
                not self.active(c, at, known_at)
                if mode == "historical"
                else self.active(c, at, known_at)
            )
        ]

    def view(self, claim, at, known_at=None, **_):
        native = self.engine.native
        known_at = int(time.time()) if known_at is None else known_at
        result = native._recall(
            native.revision(),
            claim["subject_id"],
            claim["predicate"],
            claim["scope_json"],
            at,
            known_at,
        )
        current = any(e["claim_id"] == claim["id"] for e in result["evidence"])
        sources = [
            dict(r[0])
            for r in self._rows(
                "MATCH(c:MemoryClaim {id:$id})-[:SUPPORTED_BY]->(s:MemorySource) RETURN properties(s)",
                id=claim["id"],
            )
        ]
        sources = [{k: v for k, v in s.items() if k != "embedding"} for s in sources]
        retention = native._usage([claim["id"]]).get(claim["id"], {})
        peers = self.group(claim, at, known_at=known_at)
        contrary = [
            c
            for c in peers
            if c["value_json"] != claim["value_json"]
            and c["cardinality"] == "single"
            and self.active(c, at, known_at)
        ]
        disputed = current and (result["status"] == "conflict" or bool(contrary))
        changes = self._rows(
            "MATCH(n)-[r:SUPERSEDES|RETRACTS]->(c:MemoryClaim {id:$id}) "
            "WHERE n.recorded_at <= $known AND r.effective_at <= $at "
            "RETURN n.id,type(r),n.reason,r.effective_at ORDER BY n.recorded_at DESC LIMIT 1",
            id=claim["id"],
            known=known_at,
            at=at,
        )
        change = changes[0] if changes else None
        return dict(
            claim_id=claim["id"],
            memory_id=claim["memory_id"],
            subject=claim.get("subject_name", claim["subject"]),
            subject_id=claim["subject_id"],
            predicate=claim["predicate"],
            value=json.loads(claim["value_json"]),
            kind=claim["kind"],
            scope=json.loads(claim["scope_json"]),
            status="disputed"
            if disputed
            else "accepted"
            if current and claim["accepted"]
            else "proposed"
            if current
            else "ended",
            accepted=bool(claim["accepted"]),
            current_eligible=current,
            accepted_for_current_use=bool(
                current and claim["accepted"] and not disputed
            ),
            protected=bool(current and claim["protected"]),
            protected_at_creation=claim["protected"],
            correction_known=bool(change and change[1] == "SUPERSEDES" and not current),
            fuzzy_score=retention.get("fuzzy_score", 0) if current else 0,
            fuzzy_explanation=retention,
            sources=sources,
            valid_from=claim["valid_from"],
            valid_until=claim["valid_until"],
            accepted_at=claim["accepted_at"],
            recorded_at=claim["recorded_at"],
            ended_at=change[3] if change else None,
            changed_by=change[0] if change else None,
            change_reason=change[2] if change else None,
            reason=claim.get("reason", ""),
            references=json.loads(claim.get("references_json", "[]")),
            conflicting_claim_ids=[
                e["claim_id"]
                for e in result["evidence"]
                if e["claim_id"] != claim["id"]
                and e["value"] != json.loads(claim["value_json"])
            ],
            evidence_path=[claim["id"], "SUPPORTED_BY", claim["source_id"]],
            identity_evidence=[],
        )

    def views(self, claims, at, known_at=None):
        return [self.view(c, at, known_at) for c in claims]

    def fetch_field(self, subject, predicate, scope, at, mode, known_at=None):
        rows = self._rows(
            "MATCH(c:MemoryClaim) WHERE c.subject_id IN $subjects "
            "AND c.predicate=$predicate AND c.scope_json=$scope RETURN properties(c) LIMIT $limit",
            subjects=self.equivalent_subjects(subject_id(subject), known_at),
            predicate=predicate,
            scope=canonical_json(scope),
            limit=self.limit + 1,
        )
        return self.selected(
            [dict(r[0]) for r in self._bounded(rows)], at, mode, known_at
        )


class ApplicationMemoryEngine:
    backend = "iron_web_2"
    retrieval_modes = frozenset(
        {
            "no_memory",
            "none",
            "vector",
            "graph",
            "hybrid",
            "hybrid_no_rerank",
            "hybrid_no_graph",
            "hybrid_no_temporal",
        }
    )

    def __init__(
        self,
        config=None,
        *,
        use_gpu=None,
        qdrant_path=None,
        graph_name=None,
        embedder=None,
        reranker=None,
        extractor=None,
        **unsupported,
    ):
        if unsupported:
            raise ValueError(
                "Injected legacy stores are not supported by the active single-store engine."
            )
        config = config or {}
        from Iron_Web_2.memory.graph.store import Memory
        from Iron_Web_2.memory.vector.store import MODEL
        if isinstance(config, str):
            import yaml

            config = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
        graph = config.get("falkordb", {})
        if use_gpu is not None and type(use_gpu) is not bool:
            raise ValueError("GPU preference must be a boolean.")
        self.use_gpu = (
            use_gpu
            if use_gpu is not None
            else os.getenv("USE_GPU", str(config.get("USE_GPU", True))).lower()
            == "true"
        )
        name = graph_name or graph.get("graph_name", "iron_web")
        self.legacy_graph_name = name
        self._operation_lock, self._closed = RLock(), False
        self.qdrant_path = (
            qdrant_path  # Retained only as the journal/migration identity.
        )
        self._encoder = (
            embedder.encoder if isinstance(embedder, ApplicationEmbeddings) else None
        )
        host = os.getenv("FALKORDB_HOST", graph.get("host", "127.0.0.1"))
        port = int(os.getenv("FALKORDB_PORT", graph.get("port", 6380)))
        self.native = Memory(
            name,
            role="user",
            namespace="iron_web_2_test"
            if name.startswith("test_")
            else "iron_web_2_app",
            embeddings=self._encoder,
            host=host,
            port=port,
            password=os.getenv("FALKORDB_PASSWORD"),
            tls=os.getenv("FALKORDB_TLS", str(graph.get("tls", False))).lower()
            == "true",
            reranker=reranker,
        )
        self.graph_store = ApplicationGraph(
            graph_name=self.native.vectors.graph_name,
            host=host,
            port=port,
            ssl=os.getenv("FALKORDB_TLS", str(graph.get("tls", False))).lower()
            == "true",
        )
        # Shared graph leases also cover native writes and context compilation.
        self.native.lock = self.native.vectors.lock = self.graph_store.write_lock
        self.graph_name = self.native.vectors.graph_name
        self.vector_store = ApplicationVectors(self)
        self.lifecycle = ApplicationLifecycle(self)
        self._repair_source_scopes()
        self.config_data = dict(
            config,
            embeddings={"model": MODEL},
            falkordb={
                "host": host,
                "port": port,
                "graph_name": self.graph_name,
                "tls": False,
            },
            retrieval={
                **{"reranker_enabled": False},
                **config.get("retrieval", {}),
                "vector_candidates": 50,
            },
            reranker={"model": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"},
            extraction_policy="explicit_claims",
            qdrant={"path": None, "collection_name": "Source:VectorMemory"},
            lifecycle=self.lifecycle.settings,
        )

    @property
    def embedder(self):
        if self._encoder is None:
            self._encoder = application_encoder("cuda" if self.use_gpu else "cpu")
            self.native.vectors.embeddings = self._encoder
        return ApplicationEmbeddings(self._encoder)

    def _repair_source_scopes(self):
        with self.graph_store.write_lock:
            done = self.graph_store.execute(
                "MATCH(m:MemoryMigration {id:'source_scopes_v1'}) RETURN m.id"
            ).rows
            if done:
                return
            self.graph_store.execute(
                "MATCH(s:Source) OPTIONAL MATCH(c:Claim)-[:SUPPORTED_BY]->(s) "
                "WITH s,collect(DISTINCT c.scope_json) AS scopes WHERE size(scopes)>0 "
                "SET s.scope_keys=scopes,s.scope_json=CASE WHEN size(scopes)=1 THEN scopes[0] ELSE $mixed END",
                {"mixed": canonical_json({"__application_event__": True})},
            )
            self.graph_store.execute(
                "MERGE(m:MemoryMigration {id:'source_scopes_v1'}) SET m.status='complete'"
            )

    def add(
        self,
        content,
        metadata=None,
        entity_ids=None,
        timestamp=None,
        valid_from=0,
        valid_until=2**63 - 1,
        importance=0.5,
        memory_id=None,
        claims=None,
        source_info=None,
        _migration=False,
        **_,
    ):
        from memory.validation import MemoryInput
        MemoryInput(content=content, metadata=metadata, entity_ids=entity_ids,
                    timestamp=timestamp, valid_from=valid_from, valid_until=valid_until,
                    importance=importance, memory_id=memory_id, claims=claims,
                    source_info=source_info)
        source = SourceInput.model_validate(
            source_info or dict(origin="agent", actor_id="local")
        )
        parsed = [ClaimInput.model_validate(c) for c in (claims or [])]
        mid = memory_id or uuid4().hex
        for c in parsed:
            if (
                c.protected or c.action in {"correct", "supersede", "retract", "alias"}
            ) and not source.user_confirmed:
                raise PermissionError(
                    "Accepted changes and protection require user confirmation."
                )
            if c.action in {"correct", "supersede", "retract"} and not c.reason.strip():
                raise ValueError("An accepted change requires a reason.")
        converted, descriptors = [], []
        for c in parsed:
            converted.append(
                dict(
                    subject=subject_id(c.subject),
                    predicate=c.predicate,
                    value=c.value,
                    kind=c.kind,
                    cardinality=c.cardinality,
                    action="assert" if c.action in {"confirm", "alias"} else c.action,
                    valid_from=c.valid_from,
                    valid_until=c.valid_until,
                    importance=1.0 if c.protected else min(float(importance), 0.99),
                    object_ids=[subject_id(r) for r in c.references],
                )
            )
            descriptors.append(
                dict(
                    subject_name=c.subject,
                    scope=c.scope,
                    reason=c.reason,
                    references=c.references,
                    protected=c.protected,
                    half_life_days=c.half_life_days,
                    targets=c.targets,
                    alias_target=subject_id(c.value) if c.action == "alias" else None,
                )
            )
            effective = (
                c.effective_at
                if c.effective_at is not None
                else source.recorded_at
                if source.recorded_at is not None
                else timestamp
            )
            if effective is not None:
                descriptors[-1].update(effective_at=effective, accepted_at=effective)
        app = dict(
            memory_id=mid,
            actor_id=source.actor_id,
            quality=source.quality,
            evidence_group=source.support_group(),
            claims=descriptors,
            migration=_migration,
        )
        if valid_from != 0 or valid_until != 2**63 - 1:
            app.update(record_valid_from=valid_from, record_valid_until=valid_until)
        entities = {
            subject_id(name): dict(id=subject_id(name), name=name, type="MemorySubject")
            for claim in parsed
            for name in [claim.subject, *claim.references]
        }
        original = dict(metadata or {})
        if "_application" in original:
            raise ValueError("Reserved application metadata.")
        original["memory_versioned"] = bool(parsed)
        vector = self.embedder.embed_single(content).tolist()
        with self.graph_store.write_lock, self._operation_lock:
            for c in parsed:
                if c.action == "alias":
                    alias, target = subject_id(c.subject), subject_id(c.value)
                    if alias in self.lifecycle.equivalent_subjects(target):
                        raise ValueError(
                            "Identity alias would introduce a cycle or duplicate mapping."
                        )
                    if self.lifecycle._canonical_subject(alias) != alias:
                        raise ValueError(
                            "An existing canonical identity cannot be overwritten."
                        )
            self.native.role = source.origin if source.origin != "import" else "agent"
            try:
                self.native(
                    "ingest",
                    text=content,
                    claims=converted,
                    scope=descriptors[0]["scope"]
                    if descriptors
                    and all(
                        item["scope"] == descriptors[0]["scope"] for item in descriptors
                    )
                    else {"__application_event__": True}
                    if descriptors
                    else {},
                    event_id=source.event_id or mid,
                    confirmed=source.user_confirmed,
                    metadata=original,
                    recorded_at=source.recorded_at
                    if source.recorded_at is not None
                    else timestamp,
                    importance=min(float(importance), 0.99),
                    _embedding=vector,
                    _entities=entities,
                    _application=app,
                )
            finally:
                self.native.role = "user"
        return mid

    def get(self, memory_id):
        rows = self.graph_store.execute(
            "MATCH(s:Source {memory_id:$id}) RETURN properties(s)", {"id": memory_id}
        ).rows
        if not rows:
            return None
        s = dict(rows[0][0])
        metadata = json.loads(s["metadata_json"])
        metadata.pop("_application", None)
        claims = self.graph_store.execute(
            "MATCH(c:Claim {memory_id:$id}) RETURN c.subject_id,c.valid_from,c.valid_until,c.id",
            {"id": memory_id},
        ).rows
        metadata.update(memory_source_id=s["id"], memory_claim_ids=[row[3] for row in sorted(claims, key=lambda row: int(row[3].rsplit("_", 1)[-1]))], memory_versioned=bool(claims))
        return MemoryRecord(
            memory_id=memory_id,
            content=s["text"],
            metadata=metadata,
            timestamp=s["recorded_at"],
            created_at=s["recorded_at"],
            entity_ids=sorted({c[0] for c in claims}),
            valid_from=max(s.get("record_valid_from", 0), min((c[1] for c in claims), default=0)),
            valid_until=min(s.get("record_valid_until", 2**63 - 1), max((c[2] for c in claims), default=2**63 - 1)),
            importance=s.get("importance", 0.5),
        )

    def recall(
        self,
        query,
        subject,
        predicate=None,
        scope=None,
        query_time=None,
        temporal_mode="now",
        known_at=None,
    ):
        with self.graph_store.write_lock, self._operation_lock:
            answer = self.lifecycle.recall(
                query, subject, predicate, scope, query_time, temporal_mode, known_at
            )
            if (
                answer["answer_status"] == "supported"
                and query_time is None
                and known_at is None
            ):
                ids = [
                    identifier
                    for row in answer["evidence"]
                    for identifier in (
                        row["claim_id"],
                        *[s["id"] for s in row["sources"]],
                    )
                ]
                self.native._usage(
                    ids,
                    request_id=uuid4().hex,
                    expected_revision=self.native.revision(),
                )
            return answer

    def inspect_claim(self, claim_id, query_time=None, known_at=None):
        claim = self.lifecycle.claim(claim_id)
        return (
            self.lifecycle.view(
                claim, int(time.time()) if query_time is None else query_time, known_at
            )
            if claim
            else None
        )

    def search(
        self,
        query,
        k=10,
        temporal_mode="auto",
        query_time=None,
        retrieval_mode="hybrid",
        document_ids=None,
        scope=None,
    ):
        if retrieval_mode not in self.retrieval_modes:
            raise ValueError("Unknown retrieval mode.")
        if retrieval_mode in {"none", "no_memory"}:
            return []
        if query_time is not None or temporal_mode == "historical":
            raise ValueError(
                "Historical questions require exact recall with an explicit subject and field."
            )
        self.embedder
        with self.graph_store.write_lock, self._operation_lock:
            hits = self.native(
                "search",
                query=query,
                scope=scope,
                limit=min(k, 100),
                candidate_limit=max(50, min(k, 100)),
                rerank=bool(
                    self.config_data["retrieval"].get("reranker_enabled", False)
                ),
            )
            output = []
            for hit in hits:
                s = self.graph_store.execute(
                    "MATCH(s:Source {id:$id}) RETURN s.memory_id",
                    {"id": hit["source_id"]},
                ).rows
                record = self.get(s[0][0]) if s else None
                if record and record.valid_from <= int(time.time()) <= record.valid_until and (
                    document_ids is None or record.memory_id in document_ids
                ):
                    output.append(
                        MemorySearchResult(
                            memory_id=record.memory_id,
                            content=record.content,
                            metadata=record.metadata,
                            entity_ids=record.entity_ids,
                            score=1 - hit["distance"],
                            retrieval_method="iron_web_2",
                            timestamp=record.timestamp,
                            valid_from=record.valid_from,
                            valid_until=record.valid_until,
                            importance=record.importance,
                            is_superseded=hit["source_status"] == "historical_evidence",
                            retrieval_trace=hit,
                        )
                    )
            return output

    def context(self, query, scope=None, *, profile=None, limit=None, used=True):
        """Return the native fixed_cache/hot_cache/persona/similar_memory API."""
        from Iron_Web_2.memory.context import ContextProfile

        self.embedder
        with self.graph_store.write_lock, self._operation_lock:
            previous = self.native.profile
            try:
                if profile is not None:
                    self.native.profile = ContextProfile.model_validate(profile)
                return self.native(
                    "context", query=query, scope=scope, limit=limit, used=used
                )
            finally:
                self.native.profile = previous

    def delete(self, memory_id, *, user_confirmed=False, **_):
        if not user_confirmed:
            raise PermissionError("Deletion requires user confirmation.")
        with self.graph_store.write_lock, self._operation_lock:
            rows = self.graph_store.execute(
                "MATCH(s:Source {memory_id:$id}) RETURN s.id", {"id": memory_id}
            ).rows
            return (
                self.native("forget", source_id=rows[0][0])["forgotten"]
                if rows
                else False
            )

    def record_work(
        self,
        work_id,
        claim_ids,
        depends_on=None,
        description="",
        agent_id="",
        requirement_context=None,
    ):
        from memory.storage import coordinated_write

        with self._operation_lock, coordinated_write(
            self.vector_store, self.graph_store, []
        ):
            return self.lifecycle.register_work(
                work_id,
                claim_ids,
                depends_on,
                description,
                agent_id,
                requirement_context,
            )

    def handoff(self, work_ids):
        with self.graph_store.write_lock, self._operation_lock:
            return self.lifecycle.handoff(work_ids)

    def complete_work(self, work_id, agent_id=""):
        with self.graph_store.write_lock, self._operation_lock:
            return self.lifecycle.complete_work(work_id, agent_id)

    def recall_path(self, *arguments, **request):
        return self.lifecycle.recall_path(*arguments, **request)

    def memory_ids(self):
        return [
            r[0]
            for r in self.graph_store.execute(
                "MATCH(s:Source) RETURN s.memory_id ORDER BY s.memory_id"
            ).rows
        ]

    def add_batch(self, memories, metadatas=None, timestamps=None, *, batch_size=32):
        if not isinstance(memories, list) or not 1 <= batch_size <= 128:
            raise ValueError("Use a list of memories and a batch size from one to 128.")
        from memory.validation import MemoryInput
        if metadatas is not None and (not isinstance(metadatas, list) or len(metadatas) != len(memories)):
            raise ValueError("Batch content and metadata lengths differ.")
        if timestamps is not None and (not isinstance(timestamps, list) or len(timestamps) != len(memories)):
            raise ValueError("Batch content and timestamp lengths differ.")
        records = []
        for index, item in enumerate(memories):
            if isinstance(item, str):
                values = {"content": item}
            elif isinstance(item, dict):
                values = dict(item)
                if "content" not in values and "text" in values:
                    values["content"] = values.pop("text")
            else:
                raise ValueError("Batch entries must be strings or record dictionaries.")
            if metadatas is not None:
                values["metadata"] = metadatas[index]
            if timestamps is not None:
                values["timestamp"] = timestamps[index]
            values.setdefault("importance", 0.5)
            records.append(MemoryInput.model_validate(values).model_dump(exclude_none=True))
        return [self.add(**record) for record in records]

    def update(self, memory_id, **changes):
        raise ValueError(
            "Source events are immutable. Add a confirmed superseding event with typed claims."
        )

    def run_maintenance(self, tasks=None, dry_run=True, **_):
        tasks = [] if tasks is None else tasks
        if not isinstance(tasks, list) or any(
            task not in {"decay", "dedup", "consolidate"} for task in tasks
        ):
            raise ValueError("Unknown maintenance task.")
        if any(task in {"dedup", "consolidate"} for task in tasks):
            raise ValueError(
                "Automatic evidence deletion/consolidation is disabled; source history must remain auditable."
            )
        if not tasks:
            return {}
        # Decay is evaluated against timestamps on reads; it does not require a
        # destructive background rewrite or deletion of low-utility evidence.
        if not dry_run:
            self.native._cache.cache_clear()
        return dict(
            backend=self.backend,
            tasks=tasks,
            dry_run=dry_run,
            decay="evaluated on reads",
            deleted=0,
            consolidated=0,
        )

    def storage_status(self):
        memories = len(self.memory_ids())
        return dict(
            backend=self.backend,
            graph_name=self.graph_name,
            graph_live=True,
            vector_backend="FalkorDB",
            atomic_event_writes=True,
            sources=memories,
            memories=memories,
        )

    def get_device_status(self):
        provider = self.embedder.provider
        return DeviceStatus(
            gpu_enabled_requested=self.use_gpu,
            cuda_available=self.use_gpu,
            active_providers=self._encoder.session.get_providers(),
            embedder_provider=provider,
            reranker_provider="disabled"
            if not self.config_data["retrieval"].get("reranker_enabled")
            else provider,
            execution_mode="GPU (CUDA)" if self.use_gpu else "CPU (explicit)",
            status_notes="Iron Web 2 multilingual embeddings; graph and vectors share one store.",
        )

    def close(self):
        if not self._closed:
            self.native.close()
            self.graph_store.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
