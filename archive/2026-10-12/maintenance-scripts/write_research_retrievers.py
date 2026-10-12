from pathlib import Path
root=Path(__file__).resolve().parents[1]
(root/'research/retrievers/inspired.py').write_text('''"""Project-owned mechanism baselines; these do not implement third-party products."""
from collections import defaultdict
import re
from memory.retrieval.hybrid import HybridRetriever
from memory.ranking.scorer import RetrievalConfig, ScoringWeights
from research.retrievers.fusion import reciprocal_rank_fusion


class EntityNeighborhoodRetriever:
    """Dense search with one-hop graph expansion and an entity-evidence bonus."""
    def __init__(self, embedder, vector_store, graph_store):
        self.retriever = HybridRetriever(embedder, vector_store, graph_store, config=RetrievalConfig(
            use_reranker=False, graph_hops=1, weights=ScoringWeights(alpha_semantic=1, beta_graph=.45,
                gamma_recency=0, delta_importance=0, epsilon_entity=0, eta_historical=0, theta_contradiction=0)))

    def retrieve(self, query, k=10, query_time=None, temporal_mode="auto", document_ids=None):
        hits = self.retriever.retrieve(query, k, query_time, temporal_mode, document_ids)
        for hit in hits:
            hit["retrieval_method"] = "entity_neighborhood"
        return hits


class DenseLexicalFusionRetriever:
    """Fuse dense ranks with keyword-overlap ranks inside the same dense shortlist."""
    def __init__(self, embedder, vector_store):
        self.embedder, self.vector_store = embedder, vector_store

    def retrieve(self, query, k=10, query_time=None, temporal_mode="auto", document_ids=None):
        from memory.retrieval.vector import VectorRetriever
        dense = VectorRetriever(self.embedder, self.vector_store).retrieve(query, max(k*2, k), query_time, temporal_mode, document_ids)
        terms = set(re.findall(r"\\w+", query.casefold()))
        lexical = []
        for hit in dense:
            overlap = len(terms & set(re.findall(r"\\w+", hit["text"].casefold())))
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

    def retrieve(self, query, k=10, query_time=None, temporal_mode="auto", document_ids=None):
        from memory.retrieval.vector import VectorRetriever
        hits = VectorRetriever(self.embedder, self.vector_store).retrieve(query, k*4, query_time, temporal_mode, document_ids)
        rooms = defaultdict(list)
        for hit in hits:
            rooms[hit["payload"].get("timestamp", 0)//86400].append(hit)
        best = sorted(rooms, key=lambda room: (-sum(h["score"] for h in rooms[room]), room))[:2]
        hits = sorted([h for room in best for h in rooms[room]], key=lambda h: (-h["score"], h["memory_id"]))[:k]
        for hit in hits:
            hit["retrieval_method"] = "temporal_room"
        return hits
''',encoding='utf-8')
p=root/'research/retrievers/contrastive.py'
s=p.read_text(encoding='utf-8').replace('from memory.ranking.scorer import RetrievalConfig','from dataclasses import dataclass\nfrom memory.ranking.scorer import RetrievalConfig\n\n\n@dataclass\nclass ContrastiveConfig(RetrievalConfig):\n    contrastive_ratio: float = .1\n    contrastive_offset: int = 100\n\n    def __post_init__(self):\n        super().__post_init__()\n        if not 0 <= self.contrastive_ratio <= 1 or self.contrastive_offset < self.vector_candidates:\n            raise ValueError("Negative sampling must begin after the positive shortlist.")')
s=s.replace('config: RetrievalConfig','config: ContrastiveConfig')
s=s.replace('which learns to discriminate','to compare relevance; this retrieval operation does not train a model')
s=s.replace('config.use_reranker:', 'config.use_reranker:')
s=s.replace('        total_k = positive_k + self.contrastive_offset + contrastive_k', '        total_k = self.contrastive_offset + contrastive_k')
s=s.replace('        max_cont_sim = 0','        max_cont_sim = -1.0')
s=s.replace('        combined = positive + contrastive', '        combined = list({c["memory_id"]: c for c in positive + contrastive}.values())')
s=s.replace('top_k=min(len(combined), 50)', 'top_k=len(combined)')
p.write_text(s,encoding='utf-8')
(root/'research/engine.py').write_text('''"""Explicit research modes over the normal engine; names describe mechanisms."""
import time
from memory.engine import MemoryEngine, serialized
from research.retrievers.inspired import EntityNeighborhoodRetriever, DenseLexicalFusionRetriever, TemporalRoomRetriever


class ResearchEngine(MemoryEngine):
    retrieval_modes = MemoryEngine.retrieval_modes | {"entity_neighborhood", "dense_lexical_fusion", "temporal_room"}

    @serialized
    def search(self, query, k=10, temporal_mode="auto", query_time=None, retrieval_mode="hybrid", document_ids=None):
        if retrieval_mode in MemoryEngine.retrieval_modes:
            return super().search(query, k, temporal_mode, query_time, retrieval_mode, document_ids)
        if retrieval_mode not in self.retrieval_modes or not isinstance(query, str) or not 1 <= k <= 100:
            raise ValueError("Invalid research retrieval request.")
        retrievers = {"entity_neighborhood": lambda: EntityNeighborhoodRetriever(self.embedder, self.vector_store, self.graph_store),
                      "dense_lexical_fusion": lambda: DenseLexicalFusionRetriever(self.embedder, self.vector_store),
                      "temporal_room": lambda: TemporalRoomRetriever(self.embedder, self.vector_store)}
        hits = retrievers[retrieval_mode]().retrieve(query, k, query_time, temporal_mode, document_ids)
        return [self._search_result(hit, retrieval_mode) for hit in hits]
''',encoding='utf-8')
p=root/'tests/test_ablations.py'
s=p.read_text(encoding='utf-8')
a=s.index('def test_competitor_retrieval_modes(')
s=s[:a]+'''def test_third_party_brand_names_are_not_application_modes(tmp_path):
    with MemoryEngine(config={}, qdrant_path=str(tmp_path/"vectors"), kuzu_path=str(tmp_path/"graph.db")) as engine:
        for mode in ("mem0", "zep", "mempalace"):
            with pytest.raises(ValueError, match="Unknown retrieval mode"):
                engine.search("fact", retrieval_mode=mode)
'''
p.write_text(s,encoding='utf-8')
