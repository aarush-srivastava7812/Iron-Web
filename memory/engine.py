"""
Unified Memory Engine for Iron Web / Hybrid Long-Term AI Memory Architecture.
High-level public facade coordinating:
- Semantic Vector Store (Qdrant)
- Structural Graph Store (Kùzu)
- Neural Embeddings & Reranking (FastEmbed / ONNX Runtime)
- Ingestion, Retrieval, Updates, and Deletions
- Cross-Store Consistency with Compensating Rollbacks
- Safe GPU Integration (RTX 4050 6GB Profile, 1GB Safety Buffer)
"""
import os
import time
import uuid
import yaml
from typing import List, Dict, Any, Optional, Union

import numpy as np

from memory.models import (
    MemoryRecord,
    MemorySearchResult,
    SearchFilter,
    DeviceStatus,
    EngineStorageError,
)
from memory.device import (
    inspect_device_status,
    SAFE_EMBED_BATCH_SIZE,
    SAFE_RERANK_BATCH_SIZE,
    TOTAL_VRAM_MB,
    RESERVED_BUFFER_MB,
    MAX_OPERATIONAL_VRAM_MB,
)
from memory.embeddings.embedder import Embedder, get_embedder
from memory.ranking.reranker import Reranker, get_reranker
from memory.vector_store.qdrant_store import QdrantVectorStore, validate_metadata
from memory.storage import coordinated_write
from memory.graph.kuzu_store import KuzuGraphStore
from memory.retrieval.vector import VectorRetriever
from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig
from memory.ingestion.mock_nim_extractor import MockNIMExtractor
from memory.maintenance.maintenance import (
    MemoryDecay,
    MemoryDeduplication,
    MemoryConsolidation,
    MaintenanceScheduler,
)


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
        # 1. Load and resolve configuration
        self.config_data = self._load_config(config)
        
        # Resolve GPU preference: explicit param > env var > config > False
        if use_gpu is not None:
            self.use_gpu = use_gpu
        else:
            env_gpu = os.getenv("USE_GPU")
            if env_gpu is not None:
                self.use_gpu = env_gpu.lower() == "true"
            else:
                self.use_gpu = self.config_data.get("USE_GPU", False)
        
        # 2. Reusable neural models (lazy or injected)
        self._embedder = embedder
        self._reranker = reranker
        self._extractor = extractor
        
        # Paths
        self.qdrant_path = qdrant_path or self.config_data.get("qdrant", {}).get("path", "./data/qdrant")
        self.kuzu_path = kuzu_path or self.config_data.get("kuzu", {}).get("path", "./data/kuzu/memory.db")
        if not self.kuzu_path.endswith(".db"):
            self.kuzu_path = os.path.join(self.kuzu_path, "memory.db")
            
        # 3. Storage stores (injected or instantiated)
        self.vector_store = vector_store or self._init_vector_store()
        self.graph_store = graph_store or self._init_graph_store()
        
        # 4. Retrieval helpers
        self._vector_retriever: Optional[VectorRetriever] = None
        self._hybrid_retriever: Optional[HybridRetriever] = None
    
    def _load_config(self, config_input: Optional[Union[Dict[str, Any], str]]) -> Dict[str, Any]:
        """Load YAML configuration from file or dict."""
        if isinstance(config_input, dict):
            return config_input
        if isinstance(config_input, str) and os.path.isfile(config_input):
            with open(config_input, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        # Default fallback to root config.yaml if exists
        default_yaml = os.path.join(os.getcwd(), "config.yaml")
        if os.path.isfile(default_yaml):
            try:
                with open(default_yaml, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}
    
    @property
    def embedder(self) -> Embedder:
        """Lazy access to shared Embedder instance."""
        if self._embedder is None:
            emb_conf = self.config_data.get("embeddings", {})
            model_name = emb_conf.get("model", "BAAI/bge-small-en-v1.5")
            quantize = emb_conf.get("quantize", True)
            self._embedder = get_embedder(
                model_name=model_name,
                use_gpu=self.use_gpu,
                quantize=quantize,
                batch_size=SAFE_EMBED_BATCH_SIZE
            )
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
                batch_size=SAFE_RERANK_BATCH_SIZE,
                prefer_tensorrt=rerank_conf.get("prefer_tensorrt", False),
                tensorrt_cache_path=rerank_conf.get("tensorrt_cache_path"),
            )
        return self._reranker
    
    @property
    def extractor(self) -> Any:
        """Access extractor (disk-cached NIMExtractor if API key present, else MockNIMExtractor)."""
        if self._extractor is None:
            api_key = os.getenv("NVIDIA_API_KEY")
            if api_key:
                try:
                    from memory.ingestion.nim_extractor import NIMExtractor
                    from memory.ingestion.cached_nim_extractor import CachedNIMExtractor
                    nim_conf = self.config_data.get("nim", {})
                    self._extractor = CachedNIMExtractor(
                        cache_dir=nim_conf.get("cache_dir"),
                        api_key=api_key,
                        model=nim_conf.get("extractor_model", "meta/llama-3.1-70b-instruct"),
                    )
                    print(f"Extractor: real NIM ({self._extractor.delegate.model}, disk-cached)")
                except Exception as e:
                    print(f"WARNING: NIM extractor init failed ({e}); falling back to MockNIMExtractor. "
                          "Mock extraction must never be used in benchmark runs.")
                    self._extractor = MockNIMExtractor()
            else:
                print("WARNING: NVIDIA_API_KEY not set; falling back to MockNIMExtractor. "
                      "Mock extraction must never be used in benchmark runs.")
                self._extractor = MockNIMExtractor()
        return self._extractor
    
    def _init_vector_store(self) -> QdrantVectorStore:
        """Initialize Qdrant with local storage and shared embedder."""
        q_conf = self.config_data.get("qdrant", {})
        col_name = q_conf.get("collection_name", "semantic_memory")
        dim = q_conf.get("vector_size", 384)
        return QdrantVectorStore(
            path=self.qdrant_path,
            collection_name=col_name,
            embedder=self.embedder,
            dimension=dim
        )
    
    def _init_graph_store(self) -> KuzuGraphStore:
        """Initialize Kùzu local graph store."""
        return KuzuGraphStore(db_path=self.kuzu_path)
    
    # =========================================================================
    # Public CRUD Operations
    # =========================================================================
    
    def add(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        entity_ids: Optional[List[str]] = None,
        timestamp: Optional[int] = None,
        valid_from: int = 0,
        valid_until: int = 2**31 - 1,
        importance: float = 1.0,
        memory_id: Optional[str] = None
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
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty.")
            
        ts = int(time.time()) if timestamp is None else timestamp
        mem_id = memory_id or f"mem_{uuid.uuid4().hex[:12]}"
        validate_metadata(metadata)
        meta = metadata.copy() if metadata else {}
        
        # 1. Compute embedding
        embedding = self.embedder.embed_single(content)
        
        # 2. Extract entities and relations
        resolved_entities = []
        resolved_relations = []
        if entity_ids:
            for eid in entity_ids:
                resolved_entities.append({
                    "id": eid,
                    "name": eid.replace("_", " ").title(),
                    "type": "Concept",
                    "description": ""
                })
        else:
            try:
                extraction = self.extractor.extract_entities_and_relations(content)
                resolved_entities = extraction.get("entities", [])
                resolved_relations = extraction.get("relations", [])
                extracted_temporal = extraction.get("temporal", {})
                if valid_from == 0 and "valid_from" in extracted_temporal:
                    valid_from = extracted_temporal["valid_from"]
                if valid_until == 2**31 - 1 and "valid_until" in extracted_temporal:
                    valid_until = extracted_temporal["valid_until"]
                if importance == 1.0 and "importance" in extraction:
                    importance = float(extraction["importance"])
            except Exception:
                # If extraction fails, attach a fallback concept entity
                fallback_id = f"ent_{mem_id}"
                resolved_entities = [{
                    "id": fallback_id,
                    "name": "GeneralMemory",
                    "type": "Concept",
                    "description": "Auto-extracted fallback entity"
                }]
        
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
                timestamp=ts
            )
        
            # 4a. Upsert Entities
            for entity in resolved_entities:
                self.graph_store.upsert_entity(
                    entity_id=entity["id"],
                    name=entity.get("name", entity["id"]),
                    entity_type=entity.get("type", "Concept"),
                    description=entity.get("description", ""),
                    importance=importance,
                    timestamp=ts
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
                    timestamp=ts
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
                        source_memory_id=mem_id
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
                    source_memory_id=mem_id
                )

        return mem_id
    
    def add_batch(
        self,
        contents: Union[List[str], List[Dict[str, Any]]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        timestamps: Optional[List[int]] = None
    ) -> List[str]:
        """
        Batch ingest a collection of memories (e.g. conversation histories).
        Adheres to conservative batch boundaries to prevent memory spikes.
        Supports list of strings or list of item dictionaries.
        """
        if not contents:
            return []
            
        if metadatas is not None and len(metadatas) != len(contents):
            raise ValueError("Batch content and metadata lengths differ.")
        if timestamps is not None and len(timestamps) != len(contents):
            raise ValueError("Batch content and timestamp lengths differ.")
        if metadatas is None:
            metadatas = [None] * len(contents)
        if timestamps is None:
            timestamps = [None] * len(contents)
            
        memory_ids = []
        for item, meta, ts in zip(contents, metadatas, timestamps):
            if isinstance(item, dict):
                text = item.get("content", item.get("text", ""))
                item_meta = meta or item.get("metadata", {
                    k: v for k, v in item.items() if k not in {
                        "content", "text", "timestamp", "entity_ids", "valid_from", "valid_until", "importance", "memory_id"
                    }
                })
                item_ts = ts if ts is not None else item.get("timestamp")
                item_eids = item.get("entity_ids")
                item_vf = item.get("valid_from", 0)
                item_vu = item.get("valid_until", 2**31 - 1)
                item_imp = float(item.get("importance", 1.0))
                item_mem_id = item.get("memory_id")
                
                mem_id = self.add(
                    content=text,
                    metadata=item_meta,
                    entity_ids=item_eids,
                    timestamp=item_ts,
                    valid_from=item_vf,
                    valid_until=item_vu,
                    importance=item_imp,
                    memory_id=item_mem_id
                )
            else:
                mem_id = self.add(content=str(item), metadata=meta, timestamp=ts)
            memory_ids.append(mem_id)
            
        return memory_ids
    
    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """
        Retrieve a memory by stable ID across stores.
        """
        qdrant_point = self.vector_store.get_memory(memory_id)
        if qdrant_point is not None:
            payload = qdrant_point.get("payload", {})
            return MemoryRecord(
                memory_id=memory_id,
                content=payload.get("text", ""),
                metadata={k: v for k, v in payload.items() if k not in {
                    "text", "memory_id", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"
                }},
                entity_ids=payload.get("entity_ids", []),
                valid_from=payload.get("valid_from", 0),
                valid_until=payload.get("valid_until", 2**31 - 1),
                importance=payload.get("importance", 1.0),
                timestamp=payload.get("timestamp", 0),
                vector_stored=True,
                graph_stored=bool(self.graph_store.get_memory_observations(memory_id))
            )
            
        # If missing from Qdrant, check if observation exists in Kùzu
        obs = self.graph_store.get_observation(f"obs_{memory_id}")
        if obs:
            return MemoryRecord(
                memory_id=memory_id,
                content=obs.get("content", ""),
                metadata={"source": obs.get("source", "graph")},
                entity_ids=[obs.get("entity_id", "")],
                valid_from=obs.get("valid_from", 0),
                valid_until=obs.get("valid_until", 2**31 - 1),
                importance=obs.get("importance", 1.0),
                timestamp=obs.get("created_at", 0),
                vector_stored=False,
                graph_stored=bool(self.graph_store.get_memory_observations(memory_id))
            )
            
        return None
    
    def search(
        self,
        query: str,
        k: int = 10,
        temporal_mode: str = "auto",
        query_time: Optional[int] = None,
        retrieval_mode: str = "hybrid"
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
        if not query or not query.strip():
            return []
            
        q_time = int(time.time()) if query_time is None else query_time
        
        mode = retrieval_mode.lower()
        if mode in ("no_memory", "none"):
            # Baseline A: No external memory (returns empty context)
            return []

        if mode == "vector":
            if self._vector_retriever is None:
                self._vector_retriever = VectorRetriever(
                    embedder=self.embedder,
                    vector_store=self.vector_store,
                    use_temporal_filter=(temporal_mode != "auto"),
                    default_top_k=k
                )
            hits = self._vector_retriever.retrieve(
                query=query,
                k=k,
                query_time=q_time,
                temporal_mode=temporal_mode
            )
            results = []
            for hit in hits:
                payload = hit.get("payload", {})
                results.append(MemorySearchResult(
                    memory_id=hit.get("memory_id", ""),
                    content=hit.get("text", payload.get("text", "")),
                    score=float(hit.get("score", 0.0)),
                    metadata={k: v for k, v in payload.items() if k not in {"text", "memory_id", "entity_ids"}},
                    entity_ids=payload.get("entity_ids", []),
                    retrieval_method="vector",
                    timestamp=payload.get("timestamp"),
                    valid_from=payload.get("valid_from"),
                    valid_until=payload.get("valid_until"),
                    importance=payload.get("importance"),
                    is_superseded=bool(hit.get("superseded", False)),
                    retrieval_trace=hit.get("retrieval_trace", {
                        "memory_id": hit.get("memory_id"),
                        "retrieval_method": "vector",
                        "score": float(hit.get("score", 0.0))
                    })
                ))
            return results

        if mode == "mem0":
            from memory.retrieval.competitors import Mem0Retriever
            retriever = Mem0Retriever(self.embedder, self.vector_store, self.graph_store)
            hits = retriever.retrieve(query=query, k=k, query_time=q_time)
            results = []
            for hit in hits:
                payload = hit.get("payload", {})
                results.append(MemorySearchResult(
                    memory_id=hit.get("memory_id", ""),
                    content=hit.get("text", payload.get("text", "")),
                    score=float(hit.get("score", 0.0)),
                    metadata={k: v for k, v in payload.items() if k not in {"text", "memory_id", "entity_ids"}},
                    entity_ids=payload.get("entity_ids", []),
                    retrieval_method="mem0",
                    timestamp=payload.get("timestamp"),
                    valid_from=payload.get("valid_from"),
                    valid_until=payload.get("valid_until"),
                    importance=payload.get("importance"),
                    is_superseded=False,
                    retrieval_trace={"memory_id": hit.get("memory_id"), "retrieval_method": "mem0", "score": float(hit.get("score", 0.0))}
                ))
            return results

        if mode == "zep":
            from memory.retrieval.competitors import ZepRetriever
            retriever = ZepRetriever(self.embedder, self.vector_store)
            hits = retriever.retrieve(query=query, k=k, query_time=q_time)
            results = []
            for hit in hits:
                payload = hit.get("payload", {})
                results.append(MemorySearchResult(
                    memory_id=hit.get("memory_id", ""),
                    content=hit.get("text", payload.get("text", "")),
                    score=float(hit.get("score", 0.0)),
                    metadata={k: v for k, v in payload.items() if k not in {"text", "memory_id", "entity_ids"}},
                    entity_ids=payload.get("entity_ids", []),
                    retrieval_method="zep",
                    timestamp=payload.get("timestamp"),
                    valid_from=payload.get("valid_from"),
                    valid_until=payload.get("valid_until"),
                    importance=payload.get("importance"),
                    is_superseded=False,
                    retrieval_trace={"memory_id": hit.get("memory_id"), "retrieval_method": "zep", "score": float(hit.get("score", 0.0))}
                ))
            return results

        if mode in ("mempalace", "temporal_mempalace"):
            from memory.retrieval.competitors import MemPalaceRetriever
            retriever = MemPalaceRetriever(self.embedder, self.vector_store)
            hits = retriever.retrieve(query=query, k=k, query_time=q_time)
            results = []
            for hit in hits:
                payload = hit.get("payload", {})
                results.append(MemorySearchResult(
                    memory_id=hit.get("memory_id", ""),
                    content=hit.get("text", payload.get("text", "")),
                    score=float(hit.get("score", 0.0)),
                    metadata={k: v for k, v in payload.items() if k not in {"text", "memory_id", "entity_ids"}},
                    entity_ids=payload.get("entity_ids", []),
                    retrieval_method="mempalace",
                    timestamp=payload.get("timestamp"),
                    valid_from=payload.get("valid_from"),
                    valid_until=payload.get("valid_until"),
                    importance=payload.get("importance"),
                    is_superseded=False,
                    retrieval_trace={"memory_id": hit.get("memory_id"), "retrieval_method": "mempalace", "score": float(hit.get("score", 0.0))}
                ))
            return results

        # Determine ablation config
        use_vector = True
        use_graph = True
        use_rerank = True
        use_temporal = (temporal_mode != "auto")

        # Data-driven reranker gate: if the ablation matrix shows the
        # cross-encoder adds no recall over cheap pre-ranking for this
        # deployment, retrieval.reranker_enabled=false kills it everywhere.
        reranker_gate = self.config_data.get("retrieval", {}).get("reranker_enabled", True)
        use_rerank = use_rerank and reranker_gate

        if mode == "graph":
            # Baseline C: Graph-only
            use_vector = False
            use_graph = True
            use_rerank = False
            use_temporal = False
        elif mode == "hybrid_no_rerank":
            # Variant D: Vector + Graph fusion without reranking
            use_rerank = False
        elif mode == "hybrid_no_graph":
            # Vector + Reranking without graph expansion
            use_graph = False
        elif mode == "hybrid_no_temporal":
            # Hybrid without temporal filtering
            use_temporal = False

        retrieval_settings = self.config_data.get("retrieval", {})
        ret_conf = RetrievalConfig(
            final_top_k=k,
            use_vector=use_vector,
            use_temporal_filter=use_temporal,
            default_query_time=q_time,
            use_graph_expansion=use_graph,
            use_reranker=use_rerank,
            use_contrastive=False,
            use_entity_lookup_cache=retrieval_settings.get("entity_lookup_cache", True),
            use_batched_conflict_resolution=retrieval_settings.get("batched_conflict_resolution", True),
        )
        retriever = HybridRetriever(
            embedder=self.embedder,
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            reranker=self.reranker,
            config=ret_conf
        )

        hits = retriever.retrieve(
            query=query,
            k=k,
            query_time=q_time,
            temporal_mode=temporal_mode
        )
        results = []
        for hit in hits:
            payload = hit.get("payload", {})
            results.append(MemorySearchResult(
                memory_id=hit.get("memory_id", ""),
                content=hit.get("text", payload.get("text", "")),
                score=float(hit.get("final_score", hit.get("score", 0.0))),
                metadata={k: v for k, v in payload.items() if k not in {"text", "memory_id", "entity_ids"}},
                entity_ids=payload.get("entity_ids", []),
                retrieval_method=hit.get("retrieval_method", mode),
                timestamp=payload.get("timestamp"),
                valid_from=payload.get("valid_from"),
                valid_until=payload.get("valid_until"),
                importance=payload.get("importance"),
                is_superseded=bool(hit.get("superseded", False)),
                retrieval_trace=hit.get("retrieval_trace", {})
            ))
        return results
    
    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: Optional[float] = None,
        valid_from: Optional[int] = None,
        valid_until: Optional[int] = None
    ) -> bool:
        """
        Update an existing memory across both stores with rollback support.
        """
        old_point = self.vector_store.get_memory(memory_id)
        if old_point is None:
            return False
            
        old_payload = dict(old_point.get("payload", {}))
        old_vector = np.array(old_point["vector"], dtype=np.float32) if old_point.get("vector") is not None else None
        
        # Merge fields
        new_text = content if content is not None else old_payload.get("text", "")
        new_importance = importance if importance is not None else old_payload.get("importance", 1.0)
        new_valid_from = valid_from if valid_from is not None else old_payload.get("valid_from", 0)
        new_valid_until = valid_until if valid_until is not None else old_payload.get("valid_until", 2**31 - 1)
        
        new_meta = {k: v for k, v in old_payload.items() if k not in {
            "text", "memory_id", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"
        }}
        validate_metadata(metadata)
        if metadata:
            new_meta.update(metadata)
            
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
                timestamp=old_payload.get("timestamp", int(time.time()))
            )
        
            entity_ids = old_payload.get("entity_ids", [])
            if entity_ids:
                for eid in entity_ids:
                    obs_id = f"obs_{memory_id}_{eid}"
                    self.graph_store.upsert_observation(
                        obs_id=obs_id,
                        entity_id=eid,
                        content=new_text,
                        embedding=new_embedding.tolist() if new_embedding is not None else None,
                        valid_from=new_valid_from,
                        valid_until=new_valid_until,
                        importance=new_importance,
                        source=new_meta.get("source", "user"),
                        source_memory_id=memory_id,
                        timestamp=old_payload.get("timestamp", int(time.time()))
                    )
            else:
                self.graph_store.upsert_observation(
                    obs_id=f"obs_{memory_id}",
                    entity_id=memory_id,
                    content=new_text,
                    embedding=new_embedding.tolist() if new_embedding is not None else None,
                    valid_from=new_valid_from,
                    valid_until=new_valid_until,
                    importance=new_importance,
                    source=new_meta.get("source", "user"),
                        source_memory_id=memory_id,
                        timestamp=old_payload.get("timestamp", int(time.time()))
                )

        return True
    
    def delete(self, memory_id: str, clean_orphaned_entities: bool = False) -> bool:
        """
        Delete a memory across Qdrant and Kùzu.
        
        Preserves shared graph entities by default (clean_orphaned_entities=False).
        If clean_orphaned_entities=True, entities with zero remaining observations
        are pruned safely.
        """
        with coordinated_write(self.vector_store, self.graph_store, [memory_id]):
            qdrant_deleted = self.vector_store.delete_memory(memory_id)
            kuzu_deleted = self.graph_store.delete_memory(
                memory_id=memory_id,
                clean_orphaned_entities=clean_orphaned_entities
            )
        return bool(qdrant_deleted or kuzu_deleted)
    
    # =========================================================================
    # Maintenance and Reliability Operations (Phase 4)
    # =========================================================================

    def decay_memories(
        self,
        half_life_days: float = 90.0,
        min_importance: float = 0.1,
        batch_size: int = 100,
        current_time: Optional[int] = None,
        dry_run: bool = False
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
            min_importance=min_importance
        )
        return decay_op.apply_decay(
            batch_size=batch_size,
            current_time=current_time,
            dry_run=dry_run
        )

    def deduplicate_memories(
        self,
        eps: float = 0.15,
        min_samples: int = 2,
        limit: int = 1000,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Identify and merge semantically duplicate memories using DBSCAN clustering.
        Safeguards:
        - Prevents merging temporally disjoint facts.
        - Prevents merging contradictory facts.
        Consolidates entity associations onto canonical record and prunes duplicates across stores.
        """
        dedup_op = MemoryDeduplication(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            embedder=self.embedder,
            eps=eps,
            min_samples=min_samples
        )
        return dedup_op.run_deduplication(
            limit=limit,
            dry_run=dry_run
        )

    def consolidate_memories(
        self,
        window_days: int = 30,
        min_episodes: int = 3,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Synthesize recurring procedural patterns and skills from episodic memories.
        Maintains source traceability (provenance) pointing to constituent memory IDs.
        """
        now = int(time.time())
        end = end_time if end_time is not None else (now + 300)
        start = start_time if start_time is not None else (now - window_days * 86400)
        
        consolidation_op = MemoryConsolidation(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            extractor=self.extractor,
            embedder=self.embedder,
            window_days=window_days,
            min_episodes=min_episodes
        )
        return consolidation_op.consolidate_window(
            start_time=start,
            end_time=end,
            dry_run=dry_run
        )

    def run_maintenance(
        self,
        tasks: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run scheduled maintenance pipeline (decay, deduplication, consolidation).
        """
        scheduler = MaintenanceScheduler(
            vector_store=self.vector_store,
            graph_store=self.graph_store,
            embedder=self.embedder,
            extractor=self.extractor
        )
        return scheduler.run_all(tasks=tasks, dry_run=dry_run)

    def get_device_status(self) -> DeviceStatus:
        """
        Inspect runtime execution providers, VRAM usage, and safety headroom.
        """
        return inspect_device_status(
            use_gpu_requested=self.use_gpu,
            embedder=self._embedder,
            reranker=self._reranker
        )
    
    def close(self):
        """Close vector and graph database connections cleanly."""
        try:
            self.vector_store.close()
        except Exception:
            pass
        try:
            self.graph_store.close()
        except Exception:
            pass
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
