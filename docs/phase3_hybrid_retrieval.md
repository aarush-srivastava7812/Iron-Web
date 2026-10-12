# Phase 3: Hybrid Retrieval — Vector Search + Graph Expansion + Reranker

---

## Overview

**Goal**: Combine vector similarity search with graph-based evidence expansion and cross-encoder reranking to produce contextually richer retrieval than vector-only baseline.

**Scope**: 
- Baseline C from architecture plan: Vector + Graph Expansion (no contrastive yet)
- FastEmbed's `TextCrossEncoder` for `bge-reranker-base` (ONNX, no PyTorch)
- Configurable weights for the scoring formula from architecture §2
- Ablation-ready: each stage togglable via config flags

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Reranker Module | `memory/ranking/reranker.py` | FastEmbed cross-encoder wrapper |
| Scoring Formula | `memory/ranking/scorer.py` | Weighted combination per §2 |
| Vector Retrieval | `memory/retrieval/vector.py` | Baseline A (reusable) |
| Hybrid Retrieval | `memory/retrieval/hybrid.py` | Full pipeline: vector → graph → rerank |
| Retrieval CLI | `scripts/retrieve.py` | Updated with hybrid mode |
| Unit Tests | `tests/test_phase3_hybrid.py` | Verify each stage + end-to-end |

---

## Implementation Details

### 1. Reranker Module (`memory/ranking/reranker.py`)

```python
"""
FastEmbed cross-encoder reranker — ONNX Runtime, CPU, no PyTorch.
Model: BAAI/bge-reranker-base (same embedding space as bge-small-en-v1.5)
"""
from fastembed.rerank.cross_encoder import TextCrossEncoder
from typing import List, Tuple
import numpy as np

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base", 
                 cache_dir: str = "./.fastembed_cache"):
        self.model = TextCrossEncoder(model_name=model_name, cache_dir=cache_dir)
        # Cross-encoder processes (query, passage) pairs
    
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 10) -> List[Dict]:
        """
        Rerank candidates using cross-encoder scores.
        candidates: list of dicts with 'text' or 'payload.text' field
        Returns candidates with added 'rerank_score' field, sorted descending.
        """
        if not candidates:
            return []
        
        # Prepare pairs: (query, passage_text)
        passages = []
        for c in candidates:
            text = c.get("text") or c.get("payload", {}).get("text", "")
            passages.append(text)
        
        pairs = [(query, p) for p in passages]
        
        # FastEmbed cross_encoder returns scores directly
        scores = list(self.model.rerank(query, passages))  # Returns list of scores
        
        # Attach scores and sort
        for c, score in zip(candidates, scores):
            c["rerank_score"] = float(score)
        
        # Sort by rerank score descending
        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]
    
    def score_pairs(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Lower-level: score (query, passage) pairs directly."""
        return list(self.model.rerank_batch(pairs))
```

### 2. Scoring Formula (`memory/ranking/scorer.py`)

```python
"""
Weighted scoring formula from architecture_plan.md §2:
FinalScore = α·SemanticSimilarity + β·GraphRelevance + γ·Recency
           + δ·Importance + ε·EntityMatch + ζ·RelationshipStrength
           + η·HistoricalRelevance − θ·ContradictionPenalty

Weights are config-driven for ablation studies.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import math

@dataclass
class ScoringWeights:
    """All weights tunable for ablation."""
    alpha_semantic: float = 1.0      # Vector cosine similarity
    beta_graph: float = 0.5          # Graph relevance score
    gamma_recency: float = 0.3       # Recency boost
    delta_importance: float = 0.2    # Importance weight
    epsilon_entity: float = 0.4      # Entity overlap with query
    zeta_relationship: float = 0.3   # Relationship strength
    eta_historical: float = 0.2      # Historical/superseded relevance
    theta_contradiction: float = 0.5 # Penalty for contradicted memories
    
    def as_dict(self) -> Dict[str, float]:
        return {
            "alpha_semantic": self.alpha_semantic,
            "beta_graph": self.beta_graph,
            "gamma_recency": self.gamma_recency,
            "delta_importance": self.delta_importance,
            "epsilon_entity": self.epsilon_entity,
            "zeta_relationship": self.zeta_relationship,
            "eta_historical": self.eta_historical,
            "theta_contradiction": self.theta_contradiction,
        }

@dataclass 
class RetrievalConfig:
    """Toggleable stages for ablation."""
    use_vector: bool = True
    use_graph_expansion: bool = True
    use_reranker: bool = True
    use_temporal_filter: bool = True
    use_contrastive: bool = False  # Phase 4
    contrastive_ratio: float = 0.1
    
    # Retrieval params
    vector_candidates: int = 100
    graph_hops: int = 2
    final_top_k: int = 10
    
    weights: ScoringWeights = field(default_factory=ScoringWeights)

class HybridScorer:
    def __init__(self, config: RetrievalConfig, graph_store=None):
        self.config = config
        self.graph_store = graph_store
    
    def score_candidates(self, query: str, query_embedding: List[float],
                         vector_results: List[Dict],
                         graph_expanded: List[Dict],
                         query_entities: List[str],
                         query_time: datetime = None) -> List[Dict]:
        """Apply full scoring formula to merged candidate pool."""
        query_time = query_time or datetime.utcnow()
        
        # Merge candidates (dedup by vector_id or memory_id)
        all_candidates = self._merge_candidates(vector_results, graph_expanded)
        
        for cand in all_candidates:
            score = 0.0
            w = self.config.weights
            
            # 1. Semantic similarity (already in vector_results as 'score')
            if self.config.use_vector:
                semantic_score = cand.get("score", 0.0)  # cosine similarity 0-1
                score += w.alpha_semantic * semantic_score
            
            # 2. Graph relevance (from expansion)
            if self.config.use_graph_expansion:
                graph_score = cand.get("graph_relevance", 0.0)
                score += w.beta_graph * graph_score
            
            # 3. Recency (exponential decay from valid_from)
            if self.config.use_temporal_filter:
                recency_score = self._compute_recency(cand, query_time)
                score += w.gamma_recency * recency_score
            
            # 4. Importance (stored in payload)
            importance = cand.get("payload", {}).get("importance", 0.5)
            score += w.delta_importance * importance
            
            # 5. Entity match with query entities
            entity_score = self._compute_entity_match(cand, query_entities)
            score += w.epsilon_entity * entity_score
            
            # 6. Relationship strength (for graph-expanded candidates)
            rel_strength = cand.get("relationship_strength", 0.0)
            score += w.zeta_relationship * rel_strength
            
            # 7. Historical relevance (superseded but relevant)
            hist_score = cand.get("historical_relevance", 0.0)
            score += w.eta_historical * hist_score
            
            # 8. Contradiction penalty
            contra_penalty = cand.get("contradiction_penalty", 0.0)
            score -= w.theta_contradiction * contra_penalty
            
            cand["hybrid_score"] = score
        
        # Sort by hybrid score
        ranked = sorted(all_candidates, key=lambda x: x["hybrid_score"], reverse=True)
        return ranked[:self.config.final_top_k]
    
    def _merge_candidates(self, vector_results: List[Dict], 
                          graph_expanded: List[Dict]) -> List[Dict]:
        """Deduplicate and merge vector + graph candidates."""
        seen = set()
        merged = []
        
        for cand in vector_results:
            key = cand.get("id") or cand.get("payload", {}).get("memory_id")
            if key and key not in seen:
                seen.add(key)
                cand["source"] = "vector"
                merged.append(cand)
        
        for cand in graph_expanded:
            key = cand.get("memory_id") or cand.get("vector_id")
            if key and key not in seen:
                seen.add(key)
                cand["source"] = "graph"
                merged.append(cand)
            elif key in seen:
                # Boost graph relevance for already-seen items
                for m in merged:
                    if (m.get("id") == key or 
                        m.get("payload", {}).get("memory_id") == key):
                        m["graph_relevance"] = max(
                            m.get("graph_relevance", 0.0),
                            cand.get("graph_relevance", 0.0)
                        )
                        m["source"] = "hybrid"
                        break
        
        return merged
    
    def _compute_recency(self, candidate: Dict, query_time: datetime) -> float:
        """Exponential decay based on valid_from. More recent = higher score."""
        payload = candidate.get("payload", {})
        valid_from_str = payload.get("valid_from")
        if not valid_from_str:
            return 0.5  # Neutral if no timestamp
        
        try:
            valid_from = datetime.fromisoformat(valid_from_str.replace("Z", "+00:00"))
        except:
            return 0.5
        
        days_diff = (query_time - valid_from).days
        # Half-life of 30 days: score = 0.5^(days/30)
        return math.exp(-days_diff / 30.0 * math.log(2))
    
    def _compute_entity_match(self, candidate: Dict, query_entities: List[str]) -> float:
        """Jaccard similarity between candidate entities and query entities."""
        if not query_entities:
            return 0.0
        
        payload = candidate.get("payload", {})
        cand_entities = payload.get("entities", [])
        if isinstance(cand_entities, str):
            cand_entities = [e.strip() for e in cand_entities.split(",")]
        
        if not cand_entities:
            return 0.0
        
        q_set = set(e.lower() for e in query_entities)
        c_set = set(e.lower() for e in cand_entities)
        
        intersection = len(q_set & c_set)
        union = len(q_set | c_set)
        return intersection / union if union > 0 else 0.0
```

### 3. Vector Retrieval Module (`memory/retrieval/vector.py`)

```python
"""
Baseline A: Pure vector search. Reusable by hybrid pipeline.
"""
from typing import List, Dict, Optional
import numpy as np
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from qdrant_client.models import Filter

class VectorRetriever:
    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore):
        self.embedder = embedder
        self.vector_store = vector_store
    
    def retrieve(self, query: str, limit: int = 100, 
                 filter: Optional[Filter] = None) -> List[Dict]:
        """Return top-N vector search results with scores."""
        q_emb = self.embedder.embed_single(query)
        results = self.vector_store.search(q_emb, limit=limit, filter=filter)
        return results
    
    def retrieve_with_embedding(self, query_embedding: np.ndarray, 
                                 limit: int = 100,
                                 filter: Optional[Filter] = None) -> List[Dict]:
        """Use precomputed embedding (for contrastive retrieval)."""
        results = self.vector_store.search(query_embedding, limit=limit, query_filter=filter)
        return results
```

### 4. Hybrid Retrieval Pipeline (`memory/retrieval/hybrid.py`)

```python
"""
Full hybrid retrieval: Vector → Graph Expansion → Rerank → Score → Top-K.
Implements Baseline C (vector + graph + rerank, no contrastive).
"""
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ranking.reranker import Reranker
from memory.ranking.scorer import HybridScorer, RetrievalConfig
from memory.retrieval.vector import VectorRetriever

class HybridRetriever:
    def __init__(
        self,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        graph_store: KuzuGraphStore,
        reranker: Reranker,
        config: RetrievalConfig = None
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.reranker = reranker
        self.config = config or RetrievalConfig()
        self.vector_retriever = VectorRetriever(embedder, vector_store)
        self.scorer = HybridScorer(self.config, graph_store)
    
    def retrieve(self, query: str, k: int = None, 
                 query_time: datetime = None) -> List[Dict]:
        """
        Main retrieval entry point.
        Returns top-K memories with scores and provenance.
        """
        k = k or self.config.final_top_k
        query_time = query_time or datetime.utcnow()
        
        # 1. Query embedding
        q_emb = self.embedder.embed_single(query)
        
        # 2. Vector search (positive candidates)
        vector_results = self.vector_retriever.retrieve(
            query, limit=self.config.vector_candidates
        )
        
        # 3. Extract entities from query for graph expansion
        query_entities = self._extract_query_entities(query)
        
        # 4. Graph expansion (Iron Web layer)
        graph_expanded = []
        if self.config.use_graph_expansion and query_entities:
            graph_expanded = self._expand_graph(query_entities, query_time)
        
        # 5. Score all candidates with hybrid formula
        scored = self.scorer.score_candidates(
            query=query,
            query_embedding=q_emb,
            vector_results=vector_results,
            graph_expanded=graph_expanded,
            query_entities=query_entities,
            query_time=query_time
        )
        
        # 6. Rerank top candidates with cross-encoder
        if self.config.use_reranker and scored:
            # Take more candidates for reranking to allow reordering
            rerank_pool = scored[:min(50, len(scored))]
            reranked = self.reranker.rerank(query, rerank_pool, top_k=k)
            
            # Merge rerank scores with hybrid scores
            for r in reranked:
                r["final_score"] = r.get("hybrid_score", 0) * 0.5 + r.get("rerank_score", 0) * 0.5
            
            reranked.sort(key=lambda x: x["final_score"], reverse=True)
            return reranked[:k]
        
        return scored[:k]
    
    def _extract_query_entities(self, query: str) -> List[str]:
        """Simple entity extraction from query. Could use NIM or NER."""
        # For now, simple keyword matching against known entities
        # In production, use NIM extractor or spaCy NER
        # This is a placeholder - Phase 6 adds proper query-time extraction
        return []
    
    def _expand_graph(self, entity_ids: List[str], query_time: datetime) -> List[Dict]:
        """1-2 hop graph traversal from matched entities."""
        # Normalize entity IDs
        normalized = [e.lower().replace(" ", "_") for e in entity_ids]
        
        # Traverse graph
        expanded = self.graph_store.expand_from_entities(normalized, hops=self.config.graph_hops)
        
        # Resolve temporal validity
        if self.config.use_temporal_filter:
            expanded = self.graph_store.resolve_temporal(expanded, query_time)
        
        # Convert to candidate format
        candidates = []
        for item in expanded:
            entity = item.get("connected", {})
            rel = item.get("r", {})
            
            # Get memories mentioning this entity
            memories = self._get_memories_for_entity(entity.get("id", ""))
            for mem in memories:
                candidates.append({
                    "memory_id": mem.get("m.id"),
                    "vector_id": mem.get("m.vector_id"),
                    "text": mem.get("m.raw_text"),
                    "payload": {
                        "text": mem.get("m.raw_text"),
                        "importance": mem.get("m.importance"),
                        "valid_from": mem.get("m.valid_from"),
                        "entities": [entity.get("id")],
                        "memory_id": mem.get("m.id")
                    },
                    "source": "graph",
                    "graph_relevance": rel.get("confidence", 0.5),
                    "relationship_strength": rel.get("confidence", 0.5),
                    "historical_relevance": 0.0  # Will be set if superseded
                })
        
        return candidates
    
    def _get_memories_for_entity(self, entity_id: str) -> List[Dict]:
        """Query Kuzu for memories mentioning this entity."""
        query = f"""
            MATCH (m:Memory)-[:Mentions]->(e:Entity {{id: '{entity_id}'}})
            RETURN m.id, m.vector_id, m.raw_text, m.importance, m.valid_from
        """
        result = self.graph_store.conn.execute(query)
        return result.get_as_df().to_dict("records")


# === Ablation Variants (easy switching) ===

class BaselineA_Retriever(VectorRetriever):
    """Pure vector search - no graph, no rerank."""
    pass

class BaselineB_Retriever(HybridRetriever):
    """Vector + reranker only."""
    def __init__(self, *args, **kwargs):
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=False,
            use_reranker=True
        )
        super().__init__(*args, config=config, **kwargs)

class BaselineC_Retriever(HybridRetriever):
    """Vector + graph expansion + reranker (no contrastive)."""
    def __init__(self, *args, **kwargs):
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=True,
            use_reranker=True
        )
        super().__init__(*args, config=config, **kwargs)

class BaselineD_Retriever(HybridRetriever):
    """Vector + contrastive (no graph)."""
    def __init__(self, *args, **kwargs):
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=False,
            use_reranker=True,
            use_contrastive=True
        )
        super().__init__(*args, config=config, **kwargs)
```

### 5. Updated Retrieval CLI (`scripts/retrieve.py`)

```python
#!/usr/bin/env python3
"""
Hybrid retrieval CLI with mode selection.
Usage: 
  python scripts/retrieve.py --query "what language" --mode hybrid
  python scripts/retrieve.py --query "what language" --mode vector
  python scripts/retrieve.py --query "what language" --mode baseline_c
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ranking.reranker import Reranker
from memory.retrieval.vector import VectorRetriever
from memory.retrieval.hybrid import (
    HybridRetriever, BaselineA_Retriever, BaselineB_Retriever, 
    BaselineC_Retriever, BaselineD_Retriever
)
from memory.ranking.scorer import RetrievalConfig

MODES = {
    "vector": "Baseline A: Vector only",
    "baseline_a": "Baseline A: Vector only",
    "baseline_b": "Baseline B: Vector + Reranker",
    "baseline_c": "Baseline C: Vector + Graph + Reranker",
    "baseline_d": "Baseline D: Vector + Contrastive + Reranker",
    "hybrid": "Full Hybrid (same as baseline_c for now)",
    "full": "Full Hybrid (same as baseline_c for now)"
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--mode", choices=list(MODES.keys()), default="hybrid")
    parser.add_argument("--vector-candidates", type=int, default=100)
    parser.add_argument("--graph-hops", type=int, default=2)
    args = parser.parse_args()
    
    print(f"Mode: {MODES[args.mode]}")
    print(f"Query: {args.query}\n")
    
    embedder = Embedder()
    vector_store = QdrantVectorStore()
    graph_store = KuzuGraphStore()
    reranker = Reranker()
    
    config = RetrievalConfig(
        vector_candidates=args.vector_candidates,
        graph_hops=args.graph_hops,
        final_top_k=args.top_k
    )
    
    # Select retriever based on mode
    if args.mode in ("vector", "baseline_a"):
        retriever = BaselineA_Retriever(embedder, vector_store)
        results = retriever.retrieve(args.query, limit=args.top_k)
    elif args.mode == "baseline_b":
        retriever = BaselineB_Retriever(embedder, vector_store, graph_store, reranker, config)
        results = retriever.retrieve(args.query, k=args.top_k)
    elif args.mode in ("baseline_c", "hybrid", "full"):
        retriever = BaselineC_Retriever(embedder, vector_store, graph_store, reranker, config)
        results = retriever.retrieve(args.query, k=args.top_k)
    elif args.mode == "baseline_d":
        retriever = BaselineD_Retriever(embedder, vector_store, graph_store, reranker, config)
        results = retriever.retrieve(args.query, k=args.top_k)
    
    # Print results
    for i, r in enumerate(results, 1):
        text = r.get("text") or r.get("payload", {}).get("text", "")[:200]
        score = r.get("final_score") or r.get("hybrid_score") or r.get("rerank_score") or r.get("score", 0)
        source = r.get("source", "unknown")
        print(f"{i}. [score={score:.4f} | {source}] {text}...")
    
    graph_store.close()

if __name__ == "__main__":
    main()
```

### 6. Unit Tests (`tests/test_phase3_hybrid.py`)

```python
import pytest
import numpy as np
from datetime import datetime, timedelta
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ranking.reranker import Reranker
from memory.ranking.scorer import HybridScorer, RetrievalConfig, ScoringWeights
from memory.retrieval.vector import VectorRetriever
from memory.retrieval.hybrid import HybridRetriever, BaselineC_Retriever

@pytest.fixture
def embedder():
    return Embedder()

@pytest.fixture
def vector_store(tmp_path):
    return QdrantVectorStore(path=str(tmp_path / "qdrant_test"))

@pytest.fixture
def graph_store(tmp_path):
    store = KuzuGraphStore(path=str(tmp_path / "kuzu_test"))
    yield store
    store.close()

@pytest.fixture
def reranker():
    return Reranker()

@pytest.fixture
def populated_stores(embedder, vector_store, graph_store):
    """Insert test data: current + historical memories."""
    now = datetime.utcnow()
    past = now - timedelta(days=5)
    
    # Memory 1: Current preference
    text1 = "I currently use Python for data science and machine learning"
    emb1 = embedder.embed_single(text1)
    vector_store.upsert([text1], emb1.reshape(1, -1), [
        {"source": "test", "importance": 0.8, "valid_from": now.isoformat(), 
         "entities": "Python,data science,machine learning", "memory_id": "mem-1"}
    ])
    
    # Memory 2: Past preference (superseded)
    text2 = "I used to use R for statistics"
    emb2 = embedder.embed_single(text2)
    vector_store.upsert([text2], emb2.reshape(1, -1), [
        {"source": "test", "importance": 0.6, "valid_from": past.isoformat(),
         "valid_until": now.isoformat(), "entities": "R,statistics", "memory_id": "mem-2"}
    ])
    
    # Graph: entities and relationships
    graph_store.upsert_entity("Python", "LANGUAGE")
    graph_store.upsert_entity("data_science", "FIELD")
    graph_store.upsert_entity("R", "LANGUAGE")
    
    from memory.graph.models import Relation
    rel1 = Relation(source="I", relation_type="USES", target="Python",
                    confidence=0.9, valid_from=now, source_memory_id="mem-1")
    rel2 = Relation(source="Python", relation_type="USED_FOR", target="data_science",
                    confidence=0.85, valid_from=now, source_memory_id="mem-1")
    rel3 = Relation(source="I", relation_type="USES", target="R",
                    confidence=0.8, valid_from=past, valid_until=now, source_memory_id="mem-2")
    
    graph_store.upsert_memory(
        type('obj', (object,), {
            'id': 'mem-1', 'raw_text': text1, 'normalized_text': text1,
            'embedding': emb1.tolist(), 'entities': ['Python', 'data science'],
            'relationships': [rel1, rel2], 'timestamp': now, 'valid_from': now,
            'valid_until': None, 'confidence': 0.9, 'importance': 0.8,
            'source': 'test', 'memory_type': 'fact'
        })(), "vec-1"
    )
    graph_store.upsert_relationship(rel1, "i", "python")
    graph_store.upsert_relationship(rel2, "python", "data_science")
    
    return vector_store, graph_store

def test_vector_retrieval_baseline(embedder, vector_store, populated_stores):
    retriever = VectorRetriever(embedder, vector_store)
    results = retriever.retrieve("Python data science", limit=5)
    
    assert len(results) == 2
    # First should be Python (more relevant)
    assert "Python" in results[0]["payload"]["text"]
    assert results[0]["score"] > results[1]["score"]

def test_reranker_basic(reranker, populated_stores):
    vector_store, _ = populated_stores
    candidates = [
        {"text": "I use Python for data science", "payload": {"text": "I use Python for data science"}},
        {"text": "I used R for statistics", "payload": {"text": "I used R for statistics"}}
    ]
    ranked = reranker.rerank("Python machine learning", candidates, top_k=2)
    
    assert len(ranked) == 2
    assert "rerank_score" in ranked[0]
    # Python should rank higher for this query
    assert "Python" in ranked[0]["text"]

def test_scorer_recency(embedder, vector_store, graph_store, populated_stores):
    config = RetrievalConfig(use_temporal_filter=True)
    scorer = HybridScorer(config, graph_store)
    
    now = datetime.utcnow()
    past = now - timedelta(days=5)
    
    cand_recent = {"payload": {"valid_from": now.isoformat(), "importance": 0.5}}
    cand_old = {"payload": {"valid_from": past.isoformat(), "importance": 0.5}}
    
    recent_score = scorer._compute_recency(cand_recent, now)
    old_score = scorer._compute_recency(cand_old, now)
    
    assert recent_score > old_score
    assert 0 <= recent_score <= 1
    assert 0 <= old_score <= 1

def test_scorer_entity_match(embedder, vector_store, graph_store, populated_stores):
    config = RetrievalConfig()
    scorer = HybridScorer(config, graph_store)
    
    cand = {"payload": {"entities": "Python,data science,machine learning"}}
    query_entities = ["Python", "machine learning"]
    
    score = scorer._compute_entity_match(cand, query_entities)
    # 2/4 = 0.5 Jaccard (Python, ML in both; data science only in cand)
    assert abs(score - 0.5) < 0.1

def test_hybrid_retrieval_end_to_end(embedder, vector_store, graph_store, reranker, populated_stores):
    """Full hybrid pipeline test."""
    config = RetrievalConfig(
        use_vector=True,
        use_graph_expansion=True,
        use_reranker=True,
        final_top_k=5
    )
    retriever = HybridRetriever(embedder, vector_store, graph_store, reranker, config)
    
    results = retriever.retrieve("Python data science", k=3)
    
    assert len(results) <= 3
    assert all("final_score" in r or "hybrid_score" in r for r in results)
    # Should prefer current Python memory over old R memory
    top_texts = [r.get("text") or r.get("payload", {}).get("text", "") for r in results]
    assert any("Python" in t for t in top_texts)

def test_baseline_c_retriever(embedder, vector_store, graph_store, reranker, populated_stores):
    """Baseline C: Vector + Graph + Reranker."""
    config = RetrievalConfig(
        use_vector=True,
        use_graph_expansion=True,
        use_reranker=True,
        final_top_k=5
    )
    retriever = BaselineC_Retriever(embedder, vector_store, graph_store, reranker, config)
    results = retriever.retrieve("Python data science", k=3)
    
    assert len(results) <= 3
    assert all("final_score" in r for r in results)

def test_ablation_toggles(embedder, vector_store, graph_store, reranker, populated_stores):
    """Verify config flags disable stages correctly."""
    # No graph expansion
    config_no_graph = RetrievalConfig(use_graph_expansion=False, use_reranker=False)
    scorer_no_graph = HybridScorer(config_no_graph, graph_store)
    
    # No reranker
    config_no_rerank = RetrievalConfig(use_reranker=False)
    retriever_no_rerank = HybridRetriever(embedder, vector_store, graph_store, reranker, config_no_rerank)
    
    results = retriever_no_rerank.retrieve("Python", k=3)
    # Should still work, just no rerank_score
    assert all("rerank_score" not in r for r in results)
```

---

## Expected Outcomes

| Metric | Baseline A (Vector) | Baseline C (Hybrid) |
|--------|---------------------|---------------------|
| Recall@10 | ~0.85 | > 0.90 (graph adds relevant) |
| Precision@5 | ~0.70 | > 0.75 (reranker filters) |
| Latency (p99) | < 15ms | < 50ms (graph + rerank) |
| NDCG@10 | baseline | +5-15% over vector-only |

---

## Verification Checklist

- [ ] `pytest tests/test_phase3_hybrid.py -v` all pass
- [ ] `python scripts/retrieve.py --query "test" --mode vector` works
- [ ] `python scripts/retrieve.py --query "test" --mode baseline_c` works
- [ ] Graph expansion returns relevant connected memories
- [ ] Reranker reorders vector results meaningfully
- [ ] Scoring formula applies all weight components
- [ ] Ablation toggles disable stages correctly
- [ ] No PyTorch imported anywhere (pure ONNX)

---

## Next Phase Dependency

Phase 4 requires: Working hybrid retriever with configurable stages. Contrastive retrieval adds a second vector search pass (offset candidates) and merges them before graph expansion.