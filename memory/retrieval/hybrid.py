"""Bounded hybrid retrieval: gather, filter, resolve conflicts, rerank, then score."""
import re
import time
import unicodedata
import numpy as np
from memory.ranking.scorer import RetrievalConfig, HybridScorer
from memory.temporal.filter import filter_by_time
from memory.vector_store.qdrant_store import create_temporal_filter


class HybridRetriever:
    def __init__(self, embedder, vector_store, graph_store, reranker=None, config=None):
        self.embedder, self.vector_store, self.graph_store, self.reranker = embedder, vector_store, graph_store, reranker
        self.config = config or RetrievalConfig()
        self.scorer = HybridScorer(self.config)

    def retrieve(self, query, k=None, query_time=None, temporal_mode="auto"):
        k = self.config.final_top_k if k is None else k
        if not 1 <= k <= 100 or temporal_mode not in {"auto", "now", "historical"}:
            raise ValueError("Invalid retrieval request.")
        now = int(time.time()) if query_time is None else query_time
        mode = temporal_mode if self.config.use_temporal_filter else "auto"
        start = time.perf_counter()
        entities = self._extract_entities(query) if self.config.use_graph_expansion else []
        query_embedding = self.embedder.embed_single(query) if self.config.use_vector else None
        vector, stage_ms = [], {}
        stage_start = time.perf_counter()
        if self.config.use_vector:
            hits = self.vector_store.search(query_embedding, k=max(k, self.config.vector_candidates),
                filter_condition=create_temporal_filter(now, mode))
            vector = [dict(memory_id=h["payload"]["memory_id"], text=h["payload"]["text"],
                           payload=h["payload"], score=h["score"], retrieval_method="vector") for h in hits]
        stage_ms["vector"] = (time.perf_counter()-stage_start)*1000
        stage_start = time.perf_counter()
        graph = self._graph_expansion(vector, now, entities, query, mode, query_embedding) if self.config.use_graph_expansion else []
        stage_ms["graph"] = (time.perf_counter()-stage_start)*1000
        combined = self._combine_candidates(vector, graph)
        combined = filter_by_time(combined, now, mode)
        stage_start = time.perf_counter()
        if self.config.use_graph_expansion:
            combined = self._resolve_contradictions(combined, now, mode)
        stage_ms["conflicts"] = (time.perf_counter()-stage_start)*1000
        stage_start = time.perf_counter()
        if self.config.use_reranker and combined:
            if self.reranker is None:
                raise ValueError("Reranking was requested without a reranker.")
            # CPU and GPU run the same complete, bounded candidate pool.
            combined = self.reranker.rerank(query, combined, top_k=len(combined))
        stage_ms["rerank"] = (time.perf_counter()-stage_start)*1000
        combined = self.scorer.score_batch(combined, query, entities, now)
        for rank, candidate in enumerate(combined[:k], 1):
            candidate["retrieval_trace"] = dict(memory_id=candidate["memory_id"],
                retrieval_method=candidate["retrieval_method"], vector_score=candidate.get("score", 0),
                rerank_score=candidate.get("rerank_score"), graph_relevance=candidate.get("graph_relevance", 0),
                linked_entities=entities, final_score=candidate["final_score"], selection_rank=rank,
                candidate_count=len(combined), superseded=candidate.get("superseded", False),
                stage_ms=stage_ms, total_retrieval_ms=(time.perf_counter()-start)*1000)
        return combined[:k]

    def _extract_entities(self, query):
        def normalize(text):
            return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
        query = normalize(query)
        if self.config.use_entity_lookup_cache:
            entities = self.graph_store.get_entity_name_index()
        else:
            result = self.graph_store.execute("MATCH (e:Entity) RETURN e.id, e.name")
            entities = []
            while result.has_next():
                entities.append(tuple(result.get_next()))
        matched = []
        for eid, name in entities:
            labels = (normalize(eid.replace("_", " ")), normalize(name or ""))
            if any(label and re.search(r"(?<!\w)"+re.escape(label)+r"(?!\w)", query, re.I) for label in labels):
                matched.append(eid)
        return sorted(set(matched))

    def _graph_expansion(self, vector_results, query_time, query_entities=None, query_text=None,
                         temporal_mode="auto", query_embedding=None):
        seeds = set(query_entities or [])
        for result in vector_results[:self.config.graph_max_nodes]:
            seeds.update(result["payload"].get("entity_ids", []))
        entities, _ = self.graph_store.expand_graph(sorted(seeds)[:self.config.graph_max_nodes],
            hops=self.config.graph_hops, valid_at=query_time, include_relations=False,
            max_nodes=self.config.graph_max_nodes, temporal_mode=temporal_mode)
        results = []
        for entity in entities:
            observations = self.graph_store.get_observations(entity["id"], query_time,
                limit=self.config.graph_max_nodes, temporal_mode=temporal_mode)
            for observation in observations:
                mid = self.graph_store.observation_memory_id(observation)
                point = self.vector_store.get_memory(mid)
                payload = point["payload"] if point else dict(memory_id=mid, text=observation["content"],
                    entity_ids=[entity["id"]], importance=observation["importance"],
                    valid_from=observation["valid_from"], valid_until=observation["valid_until"],
                    timestamp=observation["created_at"], source=observation["source"])
                embedding = point.get("vector") if point else observation.get("embedding")
                score = 0.
                if query_embedding is not None and embedding:
                    emb = np.asarray(embedding)
                    denominator = np.linalg.norm(emb)*np.linalg.norm(query_embedding)
                    if denominator:
                        score = float(np.dot(emb, query_embedding)/denominator)
                results.append(dict(memory_id=mid, text=payload["text"], payload=payload, score=score,
                                    graph_relevance=1., retrieval_method="graph"))
        # Deduplicate before applying the graph candidate ceiling.
        return self._combine_candidates([], results)[:self.config.graph_max_nodes]

    @staticmethod
    def _combine_candidates(vector_results, graph_results, contrastive_results=None):
        combined = {}
        for candidate in vector_results + graph_results + (contrastive_results or []):
            mid = candidate["memory_id"]
            if mid not in combined:
                combined[mid] = dict(candidate)
            else:
                existing = combined[mid]
                methods = sorted(set(existing["retrieval_method"].split("+")) | set(candidate["retrieval_method"].split("+")))
                existing["retrieval_method"] = "+".join(methods)
                existing["graph_relevance"] = max(existing.get("graph_relevance", 0), candidate.get("graph_relevance", 0))
        return list(combined.values())

    def _resolve_contradictions(self, candidates, query_time, temporal_mode="auto"):
        conflicts = self.graph_store.get_relationship_conflicts_batch([c["memory_id"] for c in candidates])
        for candidate in candidates:
            effective = [c for c in conflicts[candidate["memory_id"]] if (c.get("effective_at") or 0) <= query_time]
            contradictions = [c for c in effective if c["relationship_type"] == "CONTRADICTS"]
            supersessions = [c for c in effective if c["relationship_type"] == "SUPERSEDES" and c["direction"] == "outgoing"]
            candidate["contradiction_penalty"] = min(1., .25*len(contradictions))
            candidate["superseded"] = bool(supersessions)
            candidate["supersession_chain"] = supersessions
            if supersessions and temporal_mode == "now":
                candidate["contradiction_penalty"] = max(.7, candidate["contradiction_penalty"])
            if temporal_mode == "historical":
                candidate["historical_relevance"] = 1.
        return candidates
