"""
Hybrid retrieval combining vector search, graph expansion, and cross-encoder reranking.
Implements Baselines B, C, D, and Full system.
"""
from typing import List, Dict, Any, Optional, Set
import re
import numpy as np
import time

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore, create_temporal_filter
from memory.graph import KuzuGraphStore, RelationType, GraphStore
from memory.ranking.reranker import Reranker
from memory.ranking.scorer import RetrievalConfig, HybridScorer, reciprocal_rank_fusion
from memory.retrieval.vector import VectorRetriever
from memory.retrieval.contrastive import ContrastiveRetriever


class AdaptiveQueryRouter:
    """Cheap, deterministic routing to avoid executing every retrieval stage."""

    TEMPORAL = re.compile(r"\b(currently|current|now|today|before|previously|used to|formerly|past|when)\b", re.I)
    CONTRADICTION = re.compile(r"\b(not|instead|rather than|contradict|conflict|switched|changed)\b", re.I)
    MULTI_HOP = re.compile(r"\b(connected|related|depend|dependency|dependencies|project|stack|using with|works with)\b", re.I)

    def route(self, query: str, entity_count: int, temporal_mode: str) -> str:
        if self.CONTRADICTION.search(query):
            return "contradiction"
        if temporal_mode != "auto" or self.TEMPORAL.search(query):
            return "temporal"
        if entity_count > 1 or self.MULTI_HOP.search(query):
            return "multi_hop"
        return "simple"


class HybridRetriever:
    """
    Full hybrid retrieval pipeline:
    1. Vector search (Qdrant)
    2. Graph expansion (Kuzu or Neo4j) 
    3. Contrastive candidate retrieval (optional)
    4. Temporal filtering
    5. Contradiction/supersession resolution
    6. Cross-encoder reranking
    7. Hybrid scoring
    """
    
    def __init__(
        self,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        graph_store: GraphStore,
        reranker: Reranker,
        config: RetrievalConfig
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.reranker = reranker
        self.config = config
        self.scorer = HybridScorer(config)
        self.router = AdaptiveQueryRouter()
        
        # Sub-components
        self.vector_retriever = VectorRetriever(embedder, vector_store, config.use_temporal_filter)
        self.contrastive_retriever = ContrastiveRetriever(embedder, vector_store, config) if config.use_contrastive else None
    
    def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        query_time: Optional[int] = None,
        temporal_mode: str = "auto"
    ) -> List[Dict[str, Any]]:
        """
        Main retrieval entry point.
        """
        if k is None:
            k = self.config.final_top_k
        if query_time is None:
            query_time = self.config.default_query_time or int(time.time())
        
        stage_started = time.perf_counter()
        # Step 1: Extract and link query entities from graph
        query_entities = self._extract_entities(query)
        
        route = self.router.route(query, len(query_entities), temporal_mode)
        stage_ms: Dict[str, float] = {}

        # Step 2: Vector search.  Qdrant local mode ignores payload indexes;
        # interval filtering is deliberately performed in RAM below.
        vector_results = []
        if self.config.use_vector:
            vector_results = self._vector_search(query, query_time, temporal_mode, route)
        stage_ms["vector"] = (time.perf_counter() - stage_started) * 1000
        
        # Step 3: Graph expansion.  Vector-backed routes expand from the
        # shortlisted finalists AFTER cheap scoring + rerank (post-filter):
        # graph evidence joins the final ranking instead of shaping the
        # candidate pool.  Graph-only mode keeps the legacy pre-expansion,
        # since it has no vector candidates to shortlist from.
        graph_results = []
        graph_started = time.perf_counter()
        use_graph = self.config.use_graph_expansion and route in {"temporal", "multi_hop", "contradiction"}
        vector_backed = bool(self.config.use_vector and vector_results)
        if use_graph and not vector_backed:
            graph_results = self._graph_expansion(vector_results, query_time, query_entities=query_entities, query_text=query)
        stage_ms["graph"] = (time.perf_counter() - graph_started) * 1000
        
        # Step 4: Contrastive candidates
        contrastive_results = []
        contrastive_info = {}
        contrastive_started = time.perf_counter()
        # DMR-like noisy factual requests do not benefit from injected negatives.
        if self.config.use_contrastive and self.contrastive_retriever and route == "contradiction":
            contrastive_results, contrastive_info = self._contrastive_retrieval(query, query_time, temporal_mode)
        stage_ms["contrastive"] = (time.perf_counter() - contrastive_started) * 1000
        
        # Step 5: Combine and deduplicate
        all_candidates = self._combine_candidates(vector_results, graph_results, contrastive_results)
        
        # Step 6: Temporal filtering
        if self.config.use_temporal_filter:
            all_candidates = self._temporal_filter(all_candidates, query_time, temporal_mode)
        
        # Pre-rank cheaply before neural reranking; this caps the expensive
        # cross-encoder to 15 candidates regardless of the source pool size.
        all_candidates = self.scorer.score_batch(
            all_candidates, query, query_entities, query_time,
            graph_context={"entities": query_entities}, contrastive_info=contrastive_info
        )
        rerank_started = time.perf_counter()
        if self.config.use_reranker and all_candidates and self.reranker.accelerated:
            all_candidates = self.reranker.rerank(query, all_candidates[:15], top_k=min(len(all_candidates), 15))
        elif self.config.use_reranker and all_candidates:
            # CPU cross-encoder inference is orders of magnitude slower than
            # retrieval.  The pre-ranking above remains deterministic and
            # preserves a useful CPU fallback without violating latency SLOs.
            for candidate in all_candidates[:15]:
                candidate["reranker_skipped"] = "no_accelerated_provider"
        stage_ms["rerank"] = (time.perf_counter() - rerank_started) * 1000

        # Step 8b: POST-FILTER graph expansion from the shortlisted finalists.
        # Expansion seeds come from reranked candidates' linked entities, so
        # the expensive graph traversal only runs on evidence that survived
        # cheap scoring, and its results compete for the final top-k directly.
        if use_graph and vector_backed:
            graph_post_started = time.perf_counter()
            post_graph = self._graph_expansion(all_candidates[:15], query_time, query_entities=query_entities, query_text=query)
            all_candidates = self._combine_candidates(all_candidates, post_graph, [])
            graph_results = post_graph
            stage_ms["graph"] += (time.perf_counter() - graph_post_started) * 1000

        # Only finalists can affect the final answer, so graph conflict work is
        # batched and deferred until after the shortlist/rerank stage.
        resolve_started = time.perf_counter()
        if route in {"temporal", "contradiction"}:
            all_candidates = self._resolve_contradictions(all_candidates[:15], query_time, temporal_mode=temporal_mode)
        stage_ms["conflicts"] = (time.perf_counter() - resolve_started) * 1000
        
        # Step 9: final score after neural and conflict signals are available.
        all_candidates = self.scorer.score_batch(
            all_candidates, query, query_entities, query_time, 
            graph_context={"entities": query_entities}, contrastive_info=contrastive_info
        )

        # Step 10: RRF fusion score integration & retrieval tracing
        stream_lists = []
        if vector_results:
            stream_lists.append(vector_results)
        if graph_results:
            stream_lists.append(graph_results)
        if contrastive_results:
            stream_lists.append(contrastive_results)
            
        rrf_map = {}
        if len(stream_lists) > 1:
            fused_rrf = reciprocal_rank_fusion(stream_lists, k=60, top_k=len(all_candidates))
            for item in fused_rrf:
                mid = item.get("memory_id")
                if mid:
                    rrf_map[mid] = item.get("rrf_score", 0.0)

        # Build retrieval trace for transparent inspection
        for rank, cand in enumerate(all_candidates):
            payload = cand.get("payload", {})
            cand["rrf_score"] = rrf_map.get(cand.get("memory_id"), 0.0)
            cand["retrieval_trace"] = {
                "memory_id": cand.get("memory_id"),
                "retrieval_method": cand.get("retrieval_method", "hybrid"),
                "vector_score": float(cand.get("score", 0.0)),
                "rerank_score": cand.get("rerank_score"),
                "graph_relevance": float(cand.get("graph_relevance", 0.0)),
                "entity_overlap": len(set(query_entities) & set(payload.get("entity_ids", []))),
                "linked_entities": query_entities,
                "importance": float(payload.get("importance", 1.0)),
                "contradiction_penalty": float(cand.get("contradiction_penalty", 0.0)),
                "superseded": bool(cand.get("superseded", False)),
                "final_score": float(cand.get("final_score", 0.0)),
                "rrf_score": float(cand.get("rrf_score", 0.0)),
                "selection_rank": rank + 1
            }
            cand["retrieval_trace"]["route"] = route
            cand["retrieval_trace"]["stage_ms"] = stage_ms
            cand["retrieval_trace"]["total_retrieval_ms"] = (time.perf_counter() - stage_started) * 1000
        
        # Step 11: Return top-k
        return all_candidates[:k]
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract and link entities mentioned in the query text."""
        if not query or not query.strip():
            return []
        query_lower = query.lower()
        matched = []
        try:
            if self.config.use_entity_lookup_cache and hasattr(self.graph_store, "get_entity_name_index"):
                entities = self.graph_store.get_entity_name_index()
            else:
                res = self.graph_store.execute("MATCH (e:Entity) RETURN e.id, e.name")
                entities = []
                while res.has_next():
                    row = res.get_next()
                    entities.append((str(row[0]).strip(), str(row[1]).strip()))
            for eid, ename in entities:
                if eid.lower() in query_lower or (ename and ename.lower() in query_lower):
                    matched.append(eid)
        except Exception:
            pass
        return list(set(matched))
    
    def _vector_search(
        self, 
        query: str, 
        query_time: int, 
        temporal_mode: str,
        route: str = "simple"
    ) -> List[Dict[str, Any]]:
        """Vector similarity search."""
        query_embedding = self.embedder.embed_single(query)
        candidate_count = 20 if route == "simple" else (50 if route in {"temporal", "multi_hop"} else self.config.vector_candidates)
        results = self.vector_store.search(
            query_embedding=query_embedding,
            k=candidate_count,
            filter_condition=None
        )
        
        # Format
        formatted = []
        for r in results:
            formatted.append({
                "memory_id": r["payload"].get("memory_id", r["id"]),
                "score": r["score"],
                "text": r["payload"].get("text", ""),
                "payload": r["payload"],
                "retrieval_method": "vector"
            })
        return formatted
    
    def _graph_expansion(
        self, 
        vector_results: List[Dict[str, Any]], 
        query_time: int,
        query_entities: Optional[List[str]] = None,
        query_text: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Expand from vector results and linked query entities via bounded graph traversal."""
        seed_entities = set(query_entities or [])
        for r in vector_results:
            entity_ids = r["payload"].get("entity_ids", [])
            seed_entities.update(entity_ids)
        
        if not seed_entities:
            return []
        
        # Bound graph traversal depth and seed set
        hops = min(max(self.config.graph_hops, 1), 2)
        try:
            entities, _ = self.graph_store.expand_graph(
                list(seed_entities)[:20], 
                hops=hops,
                valid_at=query_time,
                include_relations=False,
            )
        except Exception:
            return []
        
        # Get observations for expanded entities, bounded to 50 max
        graph_results = []
        for entity in entities[:10]:
            try:
                obs_list = self.graph_store.get_observations(entity["id"], valid_at=query_time, limit=3)
                for obs in obs_list:
                    graph_results.append({
                        "memory_id": obs["id"],
                        "score": 0.0,
                        "text": obs["content"],
                        "payload": {
                            "memory_id": obs["id"],
                            "text": obs["content"],
                            "entity_ids": [entity["id"]],
                            "importance": obs.get("importance", 1.0),
                            "valid_from": obs.get("valid_from", 0),
                            "valid_until": obs.get("valid_until", 2**31 - 1),
                        },
                        "graph_relevance": 1.0,
                        "retrieval_method": "graph"
                    })
            except Exception:
                continue
            if len(graph_results) >= 30:
                break
        
        return graph_results

    
    def _contrastive_retrieval(
        self, 
        query: str, 
        query_time: int, 
        temporal_mode: str
    ) -> tuple:
        """Get contrastive candidates."""
        return self.contrastive_retriever.retrieve_contrastive(query, query_time, temporal_mode)
    
    def _combine_candidates(
        self, 
        vector_results: List[Dict], 
        graph_results: List[Dict], 
        contrastive_results: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Combine and deduplicate candidates from all sources."""
        # Use memory_id as deduplication key
        seen = set()
        combined = []
        
        # Priority order: vector > graph > contrastive (for deduplication)
        for results in [vector_results, graph_results, contrastive_results]:
            for r in results:
                mem_id = r.get("memory_id")
                if mem_id and mem_id not in seen:
                    seen.add(mem_id)
                    combined.append(r)
                elif mem_id and mem_id in seen:
                    # Merge retrieval methods and propagate graph corroboration
                    for existing in combined:
                        if existing.get("memory_id") == mem_id:
                            existing_methods = existing.get("retrieval_method", "")
                            new_method = r.get("retrieval_method", "")
                            if new_method not in existing_methods:
                                existing["retrieval_method"] = f"{existing_methods}+{new_method}"
                            if r.get("graph_relevance", 0) > existing.get("graph_relevance", 0):
                                existing["graph_relevance"] = r.get("graph_relevance", 0)
                            break
        
        return combined
    
    def _temporal_filter(
        self, 
        candidates: List[Dict], 
        query_time: int, 
        temporal_mode: str
    ) -> List[Dict]:
        """Apply temporal filtering to candidates."""
        if temporal_mode == "auto":
            return candidates
        
        filtered = []
        for cand in candidates:
            payload = cand.get("payload", {})
            vf = payload.get("valid_from", 0)
            vu = payload.get("valid_until", 2**31 - 1)
            
            if temporal_mode == "now":
                if vf <= query_time <= vu:
                    filtered.append(cand)
            elif temporal_mode == "historical":
                if vu < query_time:
                    filtered.append(cand)
        
        return filtered
    
    def _resolve_contradictions(
        self, 
        candidates: List[Dict], 
        query_time: int,
        temporal_mode: str = "auto"
    ) -> List[Dict]:
        """Resolve graph conflicts for finalists with one bounded graph query."""
        try:
            conflicts = self.graph_store.get_relationship_conflicts_batch(
                [cand.get("memory_id", "") for cand in candidates],
                use_batched_resolution=self.config.use_batched_conflict_resolution,
            )
        except (AttributeError, Exception):
            return candidates
        for cand in candidates:
            items = conflicts.get(cand.get("memory_id", ""), [])
            if not items:
                continue
            contradictions = [item for item in items if item["relationship_type"] == "CONTRADICTS"]
            supersessions = [item for item in items if item["relationship_type"] == "SUPERSEDES"]
            if contradictions:
                cand["contradiction_penalty"] = min(len(contradictions) * 0.25, 1.0)
                cand["has_contradiction"] = True
            if supersessions:
                cand["supersession_chain"] = supersessions
                cand["superseded"] = True
                if temporal_mode == "now":
                    cand["contradiction_penalty"] = max(cand.get("contradiction_penalty", 0.0), 0.7)
                elif temporal_mode == "historical":
                    cand["historical_relevance"] = 1.0
        
        return candidates


# === Baseline Variants ===

class BaselineB_Retriever(HybridRetriever):
    """Baseline B: Vector + Rerank (no graph, no contrastive)."""
    
    def __init__(self, embedder, vector_store, graph_store, reranker, config):
        # Disable graph and contrastive
        config = RetrievalConfig(
            **{**config.__dict__, 
               "use_graph_expansion": False, 
               "use_contrastive": False}
        )
        super().__init__(embedder, vector_store, graph_store, reranker, config)


class BaselineC_Retriever(HybridRetriever):
    """Baseline C: Vector + Graph + Rerank (no contrastive)."""
    
    def __init__(self, embedder, vector_store, graph_store, reranker, config):
        config = RetrievalConfig(
            **{**config.__dict__, "use_contrastive": False}
        )
        super().__init__(embedder, vector_store, graph_store, reranker, config)


class BaselineD_Retriever(HybridRetriever):
    """Baseline D: Vector + Contrastive + Rerank (no graph)."""
    
    def __init__(self, embedder, vector_store, graph_store, reranker, config):
        config = RetrievalConfig(
            **{**config.__dict__, "use_graph_expansion": False}
        )
        super().__init__(embedder, vector_store, graph_store, reranker, config)


class FullRetriever(HybridRetriever):
    """Full system: Vector + Graph + Contrastive + Rerank + Temporal."""
    
    def __init__(self, embedder, vector_store, graph_store, reranker, config):
        # All components enabled by default
        super().__init__(embedder, vector_store, graph_store, reranker, config)
