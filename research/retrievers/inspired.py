"""Project-owned mechanism baselines; these do not implement third-party products."""

from collections import defaultdict
import re
from memory.retrieval.hybrid import HybridRetriever
from memory.ranking.scorer import RetrievalConfig, ScoringWeights
from research.retrievers.fusion import reciprocal_rank_fusion


class EntityNeighborhoodRetriever:
    """Dense search with one-hop graph expansion and an entity-evidence bonus."""

    def __init__(self, embedder, vector_store, graph_store):
        self.retriever = HybridRetriever(
            embedder,
            vector_store,
            graph_store,
            config=RetrievalConfig(
                use_reranker=False,
                graph_hops=1,
                weights=ScoringWeights(
                    alpha_semantic=1,
                    beta_graph=0.45,
                    gamma_recency=0,
                    delta_importance=0,
                    epsilon_entity=0,
                    eta_historical=0,
                    theta_contradiction=0,
                ),
            ),
        )

    def retrieve(
        self, query, k=10, query_time=None, temporal_mode="auto", document_ids=None
    ):
        hits = self.retriever.retrieve(
            query, k, query_time, temporal_mode, document_ids
        )
        for hit in hits:
            hit["retrieval_method"] = "entity_neighborhood"
        return hits


class DenseLexicalFusionRetriever:
    """Fuse dense ranks with keyword-overlap ranks inside the same dense shortlist."""

    def __init__(self, embedder, vector_store):
        self.embedder, self.vector_store = embedder, vector_store

    def retrieve(
        self, query, k=10, query_time=None, temporal_mode="auto", document_ids=None
    ):
        from memory.retrieval.vector import VectorRetriever

        dense = VectorRetriever(self.embedder, self.vector_store).retrieve(
            query, max(k * 2, k), query_time, temporal_mode, document_ids
        )
        terms = set(re.findall(r"\w+", query.casefold()))
        lexical = []
        for hit in dense:
            overlap = len(terms & set(re.findall(r"\w+", hit["text"].casefold())))
            if overlap:
                lexical.append(dict(hit, score=overlap))
        lexical.sort(key=lambda hit: (-hit["score"], hit["memory_id"]))
        hits = reciprocal_rank_fusion([dense, lexical], top_k=k)
        for hit in hits:
            hit["score"] = hit["rrf_score"]
            hit["retrieval_method"] = "dense_lexical_fusion"
        return hits


class TemporalRoomRetriever:
    """Group a dense shortlist by UTC day and select the two highest summed-score groups."""

    def __init__(self, embedder, vector_store):
        self.embedder, self.vector_store = embedder, vector_store

    def retrieve(
        self, query, k=10, query_time=None, temporal_mode="auto", document_ids=None
    ):
        from memory.retrieval.vector import VectorRetriever

        hits = VectorRetriever(self.embedder, self.vector_store).retrieve(
            query, k * 4, query_time, temporal_mode, document_ids
        )
        rooms = defaultdict(list)
        for hit in hits:
            rooms[hit["payload"].get("timestamp", 0) // 86400].append(hit)
        best = sorted(
            rooms, key=lambda room: (-sum(h["score"] for h in rooms[room]), room)
        )[:2]
        hits = sorted(
            [h for room in best for h in rooms[room]],
            key=lambda h: (-h["score"], h["memory_id"]),
        )[:k]
        for hit in hits:
            hit["retrieval_method"] = "temporal_room"
        return hits
