"""
Unified Memory Engine for Iron Web / Hybrid Long-Term AI Memory Architecture.
High-level public facade coordinating:
- Semantic Vector Store (Qdrant)
- Structural Graph Store (Kùzu)
- Neural Embeddings & Reranking (FastEmbed / ONNX Runtime)
- Ingestion, Retrieval, Updates, and Deletions
- Cross-Store Consistency with Compensating Rollbacks
- Optional GPU execution with observed provider and memory telemetry
"""

from __future__ import annotations
import os
import time
import uuid
from copy import deepcopy
import yaml
from threading import RLock
from functools import wraps
from typing import List, Dict, Any, Optional, Union

import numpy as np

from memory.models import (
    MemoryRecord,
    MemorySearchResult,
    DeviceStatus,
)
from memory.device import (
    inspect_device_status,
)
from memory.embeddings.embedder import Embedder, get_embedder
from memory.ranking.reranker import Reranker, get_reranker
from memory.schema import validate_metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.vector_store.qdrant_store import QdrantVectorStore
    from memory.graph.kuzu_store import KuzuGraphStore
from memory.storage import coordinated_write
from memory.retrieval.vector import VectorRetriever
from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig
from memory.ranking.scorer import ScoringWeights
from memory.ingestion.extractor import validate_extraction, canonicalize_entities
from memory.maintenance.maintenance import (
    MemoryDecay,
    MemoryDeduplication,
    MemoryConsolidation,
    MaintenanceScheduler,
)


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.graph_store.write_lock, self._operation_lock:
            if self._closed and method.__name__ != "close":
                raise RuntimeError("Memory engine is closed.")
            return method(self, *args, **kwargs)

    return call


class MemoryEngine:
    """
    Unified public interface for the Hybrid Long-Term AI Memory Engine.

    Coordinates Qdrant and Kùzu stores behind a consistent, typed API:
    - add: Ingest memory with coordinated cross-store writes.
    - add_batch: Batch ingestion with safe batch sizes.
    - get: Retrieve complete memory record by stable identifier.
    - search: Time-aware vector and hybrid retrieval.
    - update: Synchronized update with compensating rollback on partial failure.
    - delete: Coordinated removal preserving shared graph entities.
    - get_device_status: Real-time GPU telemetry and provider status.
    """

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
        config: Optional[Union[Dict[str, Any], str]] = None,
        vector_store: Optional[QdrantVectorStore] = None,
        graph_store: Optional[KuzuGraphStore] = None,
        embedder: Optional[Embedder] = None,
        reranker: Optional[Reranker] = None,
        extractor: Optional[Any] = None,
        use_gpu: Optional[bool] = None,
        qdrant_path: Optional[str] = None,
        kuzu_path: Optional[str] = None,
    ):
        self._operation_lock = RLock()
        self._closed = False
        # 1. Load and resolve configuration
        self.config_data = self._load_config(config)
        if use_gpu is not None and not isinstance(use_gpu, bool):
            raise ValueError("GPU preference must be a boolean.")

        # Resolve GPU preference: explicit param > env var > config > False
        if use_gpu is not None:
            self.use_gpu = use_gpu
        else:
            env_gpu = os.getenv("USE_GPU")
            if env_gpu is not None:
                if env_gpu.lower() not in {"true", "false"}:
                    raise ValueError("USE_GPU must be true or false.")
                self.use_gpu = env_gpu.lower() == "true"
            else:
                self.use_gpu = self.config_data.get("USE_GPU", False)

        # 2. Reusable neural models (lazy or injected)
        self._embedder = embedder
        self._reranker = reranker
        self._extractor = extractor

        # Paths
        self.qdrant_path = qdrant_path or self.config_data.get("qdrant", {}).get(
            "path", "./data/qdrant"
        )
        self.kuzu_path = kuzu_path or self.config_data.get("kuzu", {}).get(
            "path", "./data/kuzu/memory.db"
        )
        if not self.kuzu_path.endswith(".db"):
            self.kuzu_path = os.path.join(self.kuzu_path, "memory.db")

        self.config_data["qdrant"]["path"] = self.qdrant_path
        self.config_data["kuzu"]["path"] = self.kuzu_path
        # 3. Storage stores (injected or instantiated)
        self._owns_vector_store = vector_store is None
        self._owns_graph_store = graph_store is None
        self.vector_store = (
            vector_store if vector_store is not None else self._init_vector_store()
        )
        try:
            self.graph_store = (
                graph_store if graph_store is not None else self._init_graph_store()
            )
        except Exception:
            if self._owns_vector_store:
                self.vector_store.close()
            raise

        # 4. Retrieval helpers
        self._vector_retriever: Optional[VectorRetriever] = None
        self._hybrid_retriever: Optional[HybridRetriever] = None

    def _load_config(
        self, config_input: Optional[Union[Dict[str, Any], str]]
    ) -> Dict[str, Any]:
        from pathlib import Path
        from memory.config import EngineSettings

        if config_input is None:
            path = Path(__file__).resolve().parents[1] / "config.yaml"
            raw = (
                yaml.safe_load(path.read_text(encoding="utf-8"))
                if path.exists()
                else {}
            )
        elif isinstance(config_input, dict):
            raw = config_input
        elif isinstance(config_input, str):
            raw = yaml.safe_load(Path(config_input).read_text(encoding="utf-8"))
        else:
            raise ValueError("Configuration must be a dictionary or YAML file path.")
        resolved = EngineSettings.model_validate(raw or {}).model_dump()
        base = (
            Path(config_input).resolve().parent
            if isinstance(config_input, str)
            else Path(__file__).resolve().parents[1]
        )
        for section, keys in (
            ("qdrant", ("path",)),
            ("kuzu", ("path",)),
            ("embeddings", ("cache_dir",)),
            ("reranker", ("cache_dir", "tensorrt_cache_path")),
            ("nim", ("cache_dir",)),
        ):
            for key in keys:
                if resolved[section].get(key) is not None:
                    value = Path(resolved[section][key]).expanduser()
                    resolved[section][key] = str(
                        value if value.is_absolute() else (base / value).resolve()
                    )
        return resolved

    @property
    def embedder(self) -> Embedder:
        """Lazy access to shared Embedder instance."""
        if self._embedder is None:
            emb_conf = self.config_data.get("embeddings", {})
            model_name = emb_conf.get("model", "BAAI/bge-small-en-v1.5")
            self._embedder = get_embedder(
                model_name=model_name,
                use_gpu=self.use_gpu,
                batch_size=emb_conf["batch_size"],
                cache_dir=emb_conf.get("cache_dir"),
            )
        if hasattr(self, "vector_store") and self.vector_store._embedder is None:
            self.vector_store._embedder = self._embedder
        return self._embedder

    @property
    def reranker(self) -> Reranker:
        """Lazy access to shared Reranker instance."""
        if self._reranker is None:
            rerank_conf = self.config_data.get("reranker", {})
            model_name = rerank_conf.get("model", "BAAI/bge-reranker-base")
            self._reranker = get_reranker(
                model_name=model_name,
                use_gpu=self.use_gpu,
                batch_size=rerank_conf["batch_size"],
                cache_dir=rerank_conf.get("cache_dir"),
                prefer_tensorrt=rerank_conf.get("prefer_tensorrt", False),
                tensorrt_cache_path=rerank_conf.get("tensorrt_cache_path"),
            )
        return self._reranker

    @property
    def extractor(self) -> Any:
        """Use only an explicitly selected extractor; failures never fabricate data."""
        if (
            self._extractor is None
            and self.config_data.get("extraction_policy", "none") == "nim"
        ):
            from memory.ingestion.cached_nim_extractor import CachedNIMExtractor

            conf = self.config_data.get("nim", {})
            self._extractor = CachedNIMExtractor(
                cache_dir=conf.get("cache_dir"),
                api_key=os.getenv("NVIDIA_API_KEY"),
                base_url=conf.get("base_url"),
                model=conf.get("extractor_model", "meta/llama-3.1-70b-instruct"),
            )
        return self._extractor

    def _init_vector_store(self) -> QdrantVectorStore:
        """Initialize Qdrant with local storage and shared embedder."""
        from memory.vector_store.qdrant_store import QdrantVectorStore

        q_conf = self.config_data.get("qdrant", {})
        col_name = q_conf.get("collection_name", "semantic_memory")
        dim = q_conf.get("vector_size", 384)
        return QdrantVectorStore(
            path=self.qdrant_path,
            collection_name=col_name,
            embedder=self._embedder,
            dimension=dim,
        )

    def _init_graph_store(self) -> KuzuGraphStore:
        """Initialize Kùzu local graph store."""
        from memory.graph.kuzu_store import KuzuGraphStore

        return KuzuGraphStore(db_path=self.kuzu_path)

    # =========================================================================
    # Public CRUD Operations
    # =========================================================================

    @serialized
    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        entity_ids: Optional[List[str]] = None,
        timestamp: Optional[int] = None,
        valid_from: int = 0,
        valid_until: int = 2**63 - 1,
        importance: float = 1.0,
        memory_id: Optional[str] = None,
        extraction: Optional[Dict[str, Any]] = None,
        enrich_graph=None,
    ) -> str:
        """
        Ingest a memory across both Qdrant and Kùzu stores with compensating rollback.

        Args:
            content: Raw text content
            metadata: Associated metadata dictionary
            entity_ids: Optional explicit entity identifiers
            timestamp: Unix timestamp (defaults to current time)
            valid_from: Validity start timestamp
            valid_until: Validity expiration timestamp
            importance: Relative importance (0.0 to 1.0)
            memory_id: Stable memory ID (generated if not provided)

        Returns:
            memory_id of the ingested memory.
        """
        from memory.validation import MemoryInput

        checked = MemoryInput(
            content=content,
            metadata=metadata,
            entity_ids=entity_ids,
            timestamp=timestamp,
            valid_from=valid_from,
            valid_until=valid_until,
            importance=importance,
            memory_id=memory_id,
        )
        entity_ids = checked.entity_ids

        ts = int(time.time()) if timestamp is None else timestamp
        mem_id = memory_id or f"mem_{uuid.uuid4().hex}"
        validate_metadata(metadata)
        meta = deepcopy(metadata) if metadata else {}

        # 1. Compute embedding
        embedding = self.embedder.embed_single(content)

        # 2. Extract entities and relations
        resolved_entities = []
        resolved_relations = []
        if entity_ids is not None:
            meta.update(
                extraction_status="explicit_entities",
                extraction_is_mock=False,
                extractor_name="manual",
            )
            for eid in entity_ids:
                resolved_entities.append(
                    {
                        "id": eid,
                        "name": eid.replace("_", " ").title(),
                        "type": "Concept",
                        "description": "",
                    }
                )
        else:
            selected = self.extractor if extraction is None else None
            raw = (
                extraction
                if extraction is not None
                else (
                    selected.extract_entities_and_relations(content)
                    if selected is not None
                    else None
                )
            )
            meta["extraction_status"] = "disabled" if raw is None else "completed"
            meta["extraction_is_mock"] = False
            meta["extractor_name"] = "disabled"
            if raw is not None:
                meta["extraction_is_mock"] = bool(
                    getattr(selected, "is_mock", raw.get("is_mock", False))
                )
                raw = canonicalize_entities(raw)
                result = validate_extraction(
                    raw,
                    extractor_name=raw.get("extractor_name", type(selected).__name__),
                    is_mock=meta["extraction_is_mock"],
                ).to_dict()
                meta["extractor_name"] = result["extractor_name"]
                resolved_entities, resolved_relations = (
                    result["entities"],
                    result["relations"],
                )
                if valid_from == 0:
                    valid_from = result["temporal"]["valid_from"]
                if valid_until == 2**63 - 1:
                    valid_until = result["temporal"]["valid_until"]
                if importance == 1.0:
                    importance = result["importance"]

        if (
            valid_from > valid_until
            or not np.isfinite(importance)
            or not 0 <= importance <= 1
        ):
            raise ValueError("Invalid validity or importance.")
        assigned_entity_ids = [e["id"] for e in resolved_entities]

        with coordinated_write(self.vector_store, self.graph_store, [mem_id]):
            self.graph_store.delete_memory(mem_id)
            # 3. Store in Qdrant (Vector Store)
            self.vector_store.upsert_memory(
                memory_id=mem_id,
                text=content,
                embedding=embedding,
                entity_ids=assigned_entity_ids,
                valid_from=valid_from,
                valid_until=valid_until,
                importance=importance,
                metadata=meta,
                timestamp=ts,
            )

            # 4a. Upsert Entities
            for entity in resolved_entities:
                self.graph_store.upsert_entity(
                    entity_id=entity["id"],
                    name=entity.get("name", entity["id"]),
                    entity_type=entity.get("type", "Concept"),
                    description=entity.get("description", ""),
                    importance=importance,
                    timestamp=ts,
                )

            # 4b. Upsert Relations
            for rel in resolved_relations:
                self.graph_store.upsert_relation(
                    from_id=rel["from"],
                    to_id=rel["to"],
                    relation_type=rel.get("type", "RELATED_TO"),
                    confidence=rel.get("confidence", 0.7),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    timestamp=ts,
                    metadata={"source_memory_id": mem_id},
                )

            # 4c. Upsert Observations (linked to entities)
            if resolved_entities:
                for entity in resolved_entities:
                    obs_id = f"obs_{mem_id}_{entity['id']}"
                    self.graph_store.upsert_observation(
                        obs_id=obs_id,
                        entity_id=entity["id"],
                        content=content,
                        embedding=embedding.tolist(),
                        valid_from=valid_from,
                        valid_until=valid_until,
                        importance=importance,
                        source=meta.get("source", "user"),
                        timestamp=ts,
                        source_memory_id=mem_id,
                    )
            else:
                # Create observation tied directly to memory ID
                self.graph_store.upsert_observation(
                    obs_id=f"obs_{mem_id}",
                    entity_id=mem_id,
                    content=content,
                    embedding=embedding.tolist(),
                    valid_from=valid_from,
                    valid_until=valid_until,
                    importance=importance,
                    source=meta.get("source", "user"),
                    timestamp=ts,
                    source_memory_id=mem_id,
                )

            if enrich_graph is not None:
                enrich_graph(mem_id)

        return mem_id

    @serialized
    def add_batch(
        self,
        contents: Union[List[str], List[Dict[str, Any]]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        timestamps: Optional[List[int]] = None,
    ) -> List[str]:
        """
        Batch ingest a collection of memories (e.g. conversation histories).
        Adheres to conservative batch boundaries to prevent memory spikes.
        Supports list of strings or list of item dictionaries.
        """
        from memory.validation import MemoryInput

        if not isinstance(contents, list):
            raise ValueError("Batch contents must be a list.")
        if metadatas is not None and len(metadatas) != len(contents):
            raise ValueError("Batch content and metadata lengths differ.")
        if timestamps is not None and len(timestamps) != len(contents):
            raise ValueError("Batch content and timestamp lengths differ.")
        metadatas = [None] * len(contents) if metadatas is None else metadatas
        timestamps = [None] * len(contents) if timestamps is None else timestamps
        prepared = []
        fields = {
            "content",
            "text",
            "metadata",
            "timestamp",
            "entity_ids",
            "valid_from",
            "valid_until",
            "importance",
            "memory_id",
        }
        for item, metadata, timestamp in zip(contents, metadatas, timestamps):
            if isinstance(item, dict):
                values = dict(
                    content=item.get("content", item.get("text", "")),
                    metadata=metadata
                    if metadata is not None
                    else item.get(
                        "metadata", {k: v for k, v in item.items() if k not in fields}
                    ),
                    timestamp=timestamp
                    if timestamp is not None
                    else item.get("timestamp"),
                    entity_ids=item.get("entity_ids"),
                    valid_from=item.get("valid_from", 0),
                    valid_until=item.get("valid_until", 2**63 - 1),
                    importance=item.get("importance", 1.0),
                    memory_id=item.get("memory_id"),
                )
            elif isinstance(item, str):
                values = dict(content=item, metadata=metadata, timestamp=timestamp)
            else:
                raise ValueError(
                    "Batch entries must be strings or record dictionaries."
                )
            prepared.append(MemoryInput(**values).model_dump())
        # Validate the complete request first. Storage commits remain per record.
        return [self.add(**values) for values in prepared]

    @staticmethod
    def _validate_id(memory_id):
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("Memory ID must be a nonempty string.")

    @serialized
    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """
        Retrieve a memory by stable ID across stores.
        """
        self._validate_id(memory_id)
        qdrant_point = self.vector_store.get_memory(memory_id)
        if qdrant_point is not None:
            payload = qdrant_point.get("payload", {})
            return MemoryRecord(
                memory_id=memory_id,
                content=payload.get("text", ""),
                metadata={
                    k: v
                    for k, v in payload.items()
                    if k
                    not in {
                        "text",
                        "memory_id",
                        "entity_ids",
                        "valid_from",
                        "valid_until",
                        "importance",
                        "timestamp",
                    }
                },
                entity_ids=payload.get("entity_ids", []),
                valid_from=payload.get("valid_from", 0),
                valid_until=payload.get("valid_until", 2**63 - 1),
                importance=payload.get("importance", 1.0),
                timestamp=payload.get("timestamp", 0),
                vector_stored=True,
                graph_stored=bool(self.graph_store.get_memory_observations(memory_id)),
            )

        observations = self.graph_store.get_memory_observations(memory_id)
        if observations:
            if len({o["content"] for o in observations}) != 1:
                from memory.models import EngineStorageError

                raise EngineStorageError(
                    "Graph observations disagree on memory contents.",
                    memory_id,
                    rolled_back=False,
                )
            observation = observations[0]
            return MemoryRecord(
                memory_id=memory_id,
                content=observation["content"],
                metadata={
                    "source": observation.get("source"),
                    "graph_only_recovery": True,
                },
                entity_ids=sorted(
                    {
                        o["entity_id"]
                        for o in observations
                        if o["entity_id"] != memory_id
                    }
                ),
                valid_from=observation["valid_from"],
                valid_until=observation["valid_until"],
                importance=observation["importance"],
                timestamp=observation["created_at"],
                vector_stored=False,
                graph_stored=True,
            )

        return None

    @serialized
    def search(
        self,
        query: str,
        k: int = 10,
        temporal_mode: str = "auto",
        query_time: Optional[int] = None,
        retrieval_mode: str = "hybrid",
        document_ids: Optional[List[str]] = None,
    ) -> List[MemorySearchResult]:
        """
        Search memories using vector or hybrid retrieval.

        Args:
            query: User or agent search query
            k: Top-k results limit
            temporal_mode: "auto", "now" (currently valid), "historical" (expired)
            query_time: Reference timestamp for temporal evaluation
            retrieval_mode: "hybrid" (Vector + Graph + Rerank) or "vector" (pure vector)
        """
        if document_ids is not None and (
            not isinstance(document_ids, list)
            or any(not isinstance(mid, str) for mid in document_ids)
        ):
            raise ValueError("Document scope must be a list of memory IDs.")
        if query_time is not None and (
            not isinstance(query_time, int) or isinstance(query_time, bool)
        ):
            raise ValueError("Reference timestamp must be an integer.")
        if not isinstance(query, str):
            raise ValueError("Query must be a string.")
        if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= 100:
            raise ValueError("Result count must be between 1 and 100.")
        if temporal_mode not in {"auto", "now", "historical"}:
            raise ValueError("Unknown temporal mode.")
        modes = self.retrieval_modes
        if retrieval_mode not in modes:
            raise ValueError(f"Unknown retrieval mode: {retrieval_mode}")
        if (
            not query.strip()
            or document_ids == []
            or retrieval_mode in {"no_memory", "none"}
        ):
            return []
        q_time = int(time.time()) if query_time is None else query_time
        if retrieval_mode == "vector":
            hits = VectorRetriever(self.embedder, self.vector_store).retrieve(
                query, k, q_time, temporal_mode, document_ids
            )
        else:
            settings = self.config_data.get("retrieval", {})
            use_rerank = retrieval_mode not in {
                "graph",
                "hybrid_no_rerank",
            } and settings.get("reranker_enabled", False)
            ret_conf = RetrievalConfig(
                final_top_k=k,
                use_vector=retrieval_mode != "graph",
                use_graph_expansion=retrieval_mode != "hybrid_no_graph",
                use_reranker=use_rerank,
                use_temporal_filter=retrieval_mode != "hybrid_no_temporal",
                default_query_time=q_time,
                vector_candidates=settings.get("vector_candidates", 100),
                graph_hops=settings.get("graph_hops", 2),
                graph_max_nodes=settings.get("graph_max_nodes", 50),
                use_entity_lookup_cache=settings.get("entity_lookup_cache", True),
                weights=ScoringWeights(**settings.get("weights", {})),
            )
            hits = HybridRetriever(
                self.embedder if retrieval_mode != "graph" else self._embedder,
                self.vector_store,
                self.graph_store,
                self.reranker if use_rerank else None,
                ret_conf,
            ).retrieve(query, k, q_time, temporal_mode, document_ids)
        return [self._search_result(hit, retrieval_mode) for hit in hits]

    @staticmethod
    def _search_result(hit, mode):
        payload = hit.get("payload", {})
        return MemorySearchResult(
            memory_id=hit["memory_id"],
            content=hit.get("text", payload.get("text", "")),
            score=float(hit.get("final_score", hit.get("score", 0))),
            metadata={
                key: value
                for key, value in payload.items()
                if key not in {"text", "memory_id", "entity_ids"}
            },
            entity_ids=payload.get("entity_ids", []),
            retrieval_method=hit.get("retrieval_method", mode),
            timestamp=payload.get("timestamp"),
            valid_from=payload.get("valid_from"),
            valid_until=payload.get("valid_until"),
            importance=payload.get("importance"),
            is_superseded=bool(hit.get("superseded", False)),
            retrieval_trace=hit.get("retrieval_trace", {}),
        )

    @serialized
    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: Optional[float] = None,
        valid_from: Optional[int] = None,
        valid_until: Optional[int] = None,
    ) -> bool:
        """
        Update an existing memory across both stores with rollback support.
        """
        self._validate_id(memory_id)
        if content is not None and (
            not isinstance(content, str) or not content.strip()
        ):
            raise ValueError("Memory content must be nonempty text.")
        old_point = self.vector_store.get_memory(memory_id)
        if old_point is None:
            return False

        old_payload = dict(old_point.get("payload", {}))
        old_vector = (
            np.array(old_point["vector"], dtype=np.float32)
            if old_point.get("vector") is not None
            else None
        )

        # Merge fields
        new_text = content if content is not None else old_payload.get("text", "")
        new_importance = (
            importance if importance is not None else old_payload.get("importance", 1.0)
        )
        new_valid_from = (
            valid_from if valid_from is not None else old_payload.get("valid_from", 0)
        )
        new_valid_until = (
            valid_until
            if valid_until is not None
            else old_payload.get("valid_until", 2**63 - 1)
        )

        new_meta = {
            k: v
            for k, v in old_payload.items()
            if k
            not in {
                "text",
                "memory_id",
                "entity_ids",
                "valid_from",
                "valid_until",
                "importance",
                "timestamp",
            }
        }
        validate_metadata(metadata)
        if metadata:
            new_meta.update(metadata)

        from memory.validation import MemoryInput

        MemoryInput(
            content=new_text,
            metadata=new_meta,
            importance=new_importance,
            valid_from=new_valid_from,
            valid_until=new_valid_until,
            memory_id=memory_id,
        )
        if (
            content is not None
            and content != old_payload.get("text")
            and old_payload.get("extraction_status") == "completed"
        ):
            self.add(
                new_text,
                metadata=new_meta,
                timestamp=old_payload.get("timestamp"),
                valid_from=new_valid_from,
                valid_until=new_valid_until,
                importance=new_importance,
                memory_id=memory_id,
            )
            return True
        # Re-embed if content changed
        if content is not None and content != old_payload.get("text", ""):
            new_embedding = self.embedder.embed_single(new_text)
        else:
            new_embedding = old_vector

        with coordinated_write(self.vector_store, self.graph_store, [memory_id]):
            # 1. Update Qdrant
            self.vector_store.upsert_memory(
                memory_id=memory_id,
                text=new_text,
                embedding=new_embedding,
                entity_ids=old_payload.get("entity_ids", []),
                valid_from=new_valid_from,
                valid_until=new_valid_until,
                importance=new_importance,
                metadata=new_meta,
                timestamp=old_payload.get("timestamp", int(time.time())),
            )

            entity_ids = old_payload.get("entity_ids", [])
            if entity_ids:
                for eid in entity_ids:
                    obs_id = f"obs_{memory_id}_{eid}"
                    self.graph_store.upsert_observation(
                        obs_id=obs_id,
                        entity_id=eid,
                        content=new_text,
                        embedding=new_embedding.tolist()
                        if new_embedding is not None
                        else None,
                        valid_from=new_valid_from,
                        valid_until=new_valid_until,
                        importance=new_importance,
                        source=new_meta.get("source", "user"),
                        source_memory_id=memory_id,
                        timestamp=old_payload.get("timestamp", int(time.time())),
                    )
            else:
                self.graph_store.upsert_observation(
                    obs_id=f"obs_{memory_id}",
                    entity_id=memory_id,
                    content=new_text,
                    embedding=new_embedding.tolist()
                    if new_embedding is not None
                    else None,
                    valid_from=new_valid_from,
                    valid_until=new_valid_until,
                    importance=new_importance,
                    source=new_meta.get("source", "user"),
                    source_memory_id=memory_id,
                    timestamp=old_payload.get("timestamp", int(time.time())),
                )

        return True

    @serialized
    def delete(self, memory_id: str, clean_orphaned_entities: bool = False) -> bool:
        """
        Delete a memory across Qdrant and Kùzu.

        Preserves shared graph entities by default (clean_orphaned_entities=False).
        If clean_orphaned_entities=True, entities with zero remaining observations
        are pruned safely.
        """
        self._validate_id(memory_id)
        with coordinated_write(self.vector_store, self.graph_store, [memory_id]):
            qdrant_deleted = self.vector_store.delete_memory(memory_id)
            kuzu_deleted = self.graph_store.delete_memory(
                memory_id=memory_id, clean_orphaned_entities=clean_orphaned_entities
            )
        return bool(qdrant_deleted or kuzu_deleted)

    # =========================================================================
    # Maintenance and Reliability Operations (Phase 4)
    # =========================================================================

    @serialized
    def decay_memories(
        self,
        half_life_days: float = 90.0,
        min_importance: float = 0.1,
        batch_size: int = 100,
        current_time: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply age-based exponential decay across all stored memories.
        Synchronizes importance between Qdrant vector points and Kùzu graph observations.
        Idempotent: computes decay relative to initial importance and creation timestamp.
        """
        decay_op = MemoryDecay(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            half_life_days=half_life_days,
            min_importance=min_importance,
        )
        return decay_op.apply_decay(
            batch_size=batch_size, current_time=current_time, dry_run=dry_run
        )

    @serialized
    def deduplicate_memories(
        self, min_samples: int = 2, limit: int = 1000, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Merge identical text, memory type and validity intervals; retain distinct similar facts.
        Safeguards:
        - Prevents merging temporally disjoint facts.
        - Prevents merging contradictory facts.
        Consolidates entity associations onto canonical record and prunes duplicates across stores.
        """
        dedup_op = MemoryDeduplication(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            embedder=self._embedder,
            min_samples=min_samples,
        )
        return dedup_op.run_deduplication(limit=limit, dry_run=dry_run)

    @serialized
    def consolidate_memories(
        self,
        window_days: int = 30,
        min_episodes: int = 3,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Synthesize recurring procedural patterns and skills from episodic memories.
        Maintains source traceability (provenance) pointing to constituent memory IDs.
        """
        now = int(time.time())
        end = end_time if end_time is not None else now
        start = start_time if start_time is not None else (now - window_days * 86400)

        consolidation_op = MemoryConsolidation(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            extractor=self._extractor if dry_run else self.extractor,
            embedder=self._embedder if dry_run else (lambda: self.embedder),
            window_days=window_days,
            min_episodes=min_episodes,
        )
        return consolidation_op.consolidate_window(
            start_time=start, end_time=end, dry_run=dry_run
        )

    @serialized
    def run_maintenance(
        self, tasks: Optional[List[str]] = None, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run scheduled maintenance pipeline (decay, deduplication, consolidation).
        """
        selected = ["decay", "dedup", "consolidate"] if tasks is None else tasks
        if not isinstance(selected, list) or set(selected) - {
            "decay",
            "dedup",
            "consolidate",
        }:
            raise ValueError("Unknown maintenance tasks.")
        needs_models = not dry_run and "consolidate" in selected
        scheduler = MaintenanceScheduler(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            embedder=(lambda: self.embedder) if needs_models else self._embedder,
            extractor=self.extractor if needs_models else self._extractor,
        )
        return scheduler.run_all(tasks=tasks, dry_run=dry_run)

    def get_device_status(self) -> DeviceStatus:
        """
        Inspect runtime execution providers, VRAM usage, and safety headroom.
        """
        return inspect_device_status(
            use_gpu_requested=self.use_gpu,
            embedder=self._embedder,
            reranker=self._reranker,
        )

    @serialized
    def storage_status(self):
        return dict(
            memories=self.vector_store.count(),
            nodes=self.graph_store.get_node_counts(),
            edges=self.graph_store.get_edge_counts(),
        )

    @serialized
    def memory_ids(self):
        """Inventory for isolated evaluation; does not load a neural model."""
        ids, offset = set(), None
        while True:
            batch, offset = self.vector_store.scroll(limit=100, offset=offset)
            ids.update(record.payload["memory_id"] for record in batch)
            if offset is None:
                return ids

    @serialized
    def close(self):
        """Close both stores, reporting any failure, and allow repeated close calls."""
        if self._closed:
            return
        errors = []
        stores = ([self.vector_store] if self._owns_vector_store else []) + (
            [self.graph_store] if self._owns_graph_store else []
        )
        for store in stores:
            try:
                store.close()
            except Exception as error:
                errors.append(error)
        self._closed = True
        if errors:
            raise ExceptionGroup("Memory store close failed", errors)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
