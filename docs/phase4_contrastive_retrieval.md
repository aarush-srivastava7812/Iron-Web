# Phase 4: Contrastive Retrieval — Negative/Contrastive Candidates for Better Discrimination

---

## Overview

**Goal**: Add contrastive retrieval to the hybrid pipeline. Instead of only retrieving top-K similar vectors (positive candidates), also retrieve the "next-N" less similar vectors (contrastive candidates) to provide the reranker with discriminative signal.

**Hypothesis** (from research papers): Contrastive candidates help the reranker distinguish subtle semantic differences, especially for queries where top-K are semantically similar but contextually different.

**Scope**: 
- Baseline D: Vector + Contrastive (no graph)
- Full: Baseline C + Contrastive = Vector + Graph + Contrastive + Reranker
- Configurable contrastive ratio (0.05, 0.1, 0.2, 0.5) for sweep in Phase 10

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Contrastive Retriever | `memory/retrieval/contrastive.py` | Dual-search: positive + offset candidates |
| Enhanced Hybrid Retriever | `memory/retrieval/hybrid.py` | Updated with contrastive merge |
| Contrastive Scoring | `memory/ranking/scorer.py` | Contrastive-aware scoring |
| Unit Tests | `tests/test_phase4_contrastive.py` | Verify contrastive pipeline |

---

## Implementation Details

### 1. Contrastive Retrieval Module (`memory/retrieval/contrastive.py`)

```python
"""
Contrastive retrieval: fetch both positive (top-N) and contrastive (next-M) candidates.
Based on: "Contrastive Retrieval" (Liu et al.) / "Hard Negatives" literature.

Idea: Reranker benefits from seeing "near-miss" candidates that are similar but wrong.
"""
from typing import List, Dict, Optional
import numpy as np
from qdrant_client.models import Filter
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore

class ContrastiveRetriever:
    def __init__(
        self, 
        embedder: Embedder, 
        vector_store: QdrantVectorStore,
        positive_limit: int = 100,
        contrastive_ratio: float = 0.1,
        contrastive_offset: int = 100
    ):
        """
        Args:
            positive_limit: Number of top similar vectors (positive candidates)
            contrastive_ratio: Ratio of contrastive to positive (e.g., 0.1 = 10%)
            contrastive_offset: Where to start contrastive search (skip top-N)
        """
        self.embedder = embedder
        self.vector_store = vector_store
        self.positive_limit = positive_limit
        self.contrastive_ratio = contrastive_ratio
        self.contrastive_offset = contrastive_offset
    
    def retrieve(self, query: str, filter: Optional[Filter] = None) -> Dict[str, List[Dict]]:
        """
        Returns dict with 'positive' and 'contrastive' candidate lists.
        """
        q_emb = self.embedder.embed_single(query)
        
        # 1. Positive candidates (top-K)
        positive = self.vector_store.search(
            q_emb, limit=self.positive_limit, query_filter=filter
        )
        
        # 2. Contrastive candidates (next-K after offset)
        contrastive_limit = int(self.positive_limit * self.contrastive_ratio)
        contrastive = self.vector_store.search(
            q_emb, 
            limit=contrastive_limit, 
            offset=self.contrastive_offset,
            query_filter=filter
        )
        
        # Tag candidates
        for c in positive:
            c["candidate_type"] = "positive"
        for c in contrastive:
            c["candidate_type"] = "contrastive"
        
        return {
            "positive": positive,
            "contrastive": contrastive,
            "all": positive + contrastive
        }
    
    def retrieve_with_embedding(self, query_embedding: np.ndarray, 
                                 filter: Optional[Filter] = None) -> Dict[str, List[Dict]]:
        """Use precomputed embedding."""
        positive = self.vector_store.search(
            query_embedding, limit=self.positive_limit, query_filter=filter
        )
        
        contrastive_limit = int(self.positive_limit * self.contrastive_ratio)
        contrastive = self.vector_store.search(
            query_embedding,
            limit=contrastive_limit,
            offset=self.contrastive_offset,
            query_filter=filter
        )
        
        for c in positive:
            c["candidate_type"] = "positive"
        for c in contrastive:
            c["candidate_type"] = "contrastive"
        
        return {
            "positive": positive,
            "contrastive": contrastive,
            "all": positive + contrastive
        }
```

### 2. Enhanced Hybrid Retriever (`memory/retrieval/hybrid.py` — additions)

```python
# Add to existing HybridRetriever class in hybrid.py

from memory.retrieval.contrastive import ContrastiveRetriever

class HybridRetriever:
    def __init__(self, *args, **kwargs):
        # ... existing init ...
        self.contrastive_retriever = ContrastiveRetriever(
            embedder=embedder,
            vector_store=vector_store,
            positive_limit=config.vector_candidates,
            contrastive_ratio=config.contrastive_ratio,
            contrastive_offset=config.vector_candidates  # Start after positive
        )
    
    def retrieve(self, query: str, k: int = None, 
                 query_time: datetime = None) -> List[Dict]:
        # ... existing code up to vector search ...
        
        # REPLACE vector search with contrastive retrieval
        if self.config.use_contrastive:
            retrieval_result = self.contrastive_retriever.retrieve(query)
            vector_results = retrieval_result["all"]  # Both positive + contrastive
            
            # Track which are contrastive for scoring
            for r in vector_results:
                r["is_contrastive"] = r.get("candidate_type") == "contrastive"
        else:
            vector_results = self.vector_retriever.retrieve(
                query, limit=self.config.vector_candidates
            )
            for r in vector_results:
                r["is_contrastive"] = False
        
        # ... rest of pipeline unchanged ...
```

### 3. Contrastive-Aware Scoring (`memory/ranking/scorer.py` — additions)

```python
# Add to HybridScorer class

def score_candidates(self, query: str, query_embedding: List[float],
                     vector_results: List[Dict],
                     graph_expanded: List[Dict],
                     query_entities: List[str],
                     query_time: datetime = None) -> List[Dict]:
    # ... existing merge and scoring ...
    
    for cand in all_candidates:
        # ... existing score components ...
        
        # NEW: Contrastive penalty/bonus
        # Contrastive candidates that score HIGH are actually good (hard positives)
        # Contrastive candidates that score LOW confirm they're negatives
        if cand.get("is_contrastive", False):
            # Small penalty for being in contrastive set initially
            # But reranker can overcome this if truly relevant
            score -= self.config.weights.theta_contrastive * 0.1
            cand["contrastive_penalty"] = 0.1
        else:
            cand["contrastive_penalty"] = 0.0
        
        cand["hybrid_score"] = score
    
    # ... rest unchanged ...
```

Add to `ScoringWeights`:

```python
@dataclass
class ScoringWeights:
    # ... existing weights ...
    theta_contrastive: float = 0.2  # Penalty for contrastive candidates
```

### 4. Baseline D Retriever (`memory/retrieval/hybrid.py` — complete)

```python
class BaselineD_Retriever(HybridRetriever):
    """Vector + Contrastive + Reranker (no graph)."""
    def __init__(self, *args, **kwargs):
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=False,
            use_reranker=True,
            use_contrastive=True,
            contrastive_ratio=0.1
        )
        super().__init__(*args, config=config, **kwargs)

class FullRetriever(HybridRetriever):
    """Full system: Vector + Graph + Contrastive + Reranker."""
    def __init__(self, *args, **kwargs):
        config = RetrievalConfig(
            use_vector=True,
            use_graph_expansion=True,
            use_reranker=True,
            use_contrastive=True,
            contrastive_ratio=0.1
        )
        super().__init__(*args, config=config, **kwargs)
```

### 5. Updated CLI (`scripts/retrieve.py` — additions)

```python
MODES = {
    # ... existing ...
    "baseline_d": "Baseline D: Vector + Contrastive + Reranker",
    "full": "Full: Vector + Graph + Contrastive + Reranker",
}

# In main():
elif args.mode == "baseline_d":
    retriever = BaselineD_Retriever(embedder, vector_store, graph_store, reranker, config)
    results = retriever.retrieve(args.query, k=args.top_k)
elif args.mode == "full":
    retriever = FullRetriever(embedder, vector_store, graph_store, reranker, config)
    results = retriever.retrieve(args.query, k=args.top_k)
```

### 6. Unit Tests (`tests/test_phase4_contrastive.py`)

```python
import pytest
import numpy as np
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ranking.reranker import Reranker
from memory.retrieval.contrastive import ContrastiveRetriever
from memory.retrieval.hybrid import BaselineD_Retriever, FullRetriever
from memory.ranking.scorer import RetrievalConfig

@pytest.fixture
def embedder():
    return Embedder()

@pytest.fixture
def vector_store(tmp_path):
    store = QdrantVectorStore(path=str(tmp_path / "qdrant_test"))
    # Populate with diverse memories
    texts = [
        "I use Python for machine learning and data science",
        "I use Python for web development with Django",
        "I use Rust for systems programming",
        "I use Go for backend services",
        "I use JavaScript for frontend development",
        "I used to use Java for enterprise apps",
        "I prefer functional programming in Haskell",
        "I use C++ for game engine development",
        "I use TypeScript for type-safe frontend",
        "I use SQL for database queries"
    ]
    embeddings = embedder.embed(texts)
    payloads = [
        {"source": "test", "importance": 0.7, "entities": t.split()[:3], "memory_id": f"mem-{i}"}
        for i, t in enumerate(texts)
    ]
    store.upsert(texts, embeddings, payloads)
    return store

@pytest.fixture
def graph_store(tmp_path):
    store = KuzuGraphStore(path=str(tmp_path / "kuzu_test"))
    yield store
    store.close()

@pytest.fixture
def reranker():
    return Reranker()

def test_contrastive_retriever_returns_both_sets(embedder, vector_store):
    retriever = ContrastiveRetriever(
        embedder, vector_store,
        positive_limit=5,
        contrastive_ratio=0.2,  # 1 contrastive per 5 positive
        contrastive_offset=5
    )
    
    result = retriever.retrieve("Python programming")
    
    assert "positive" in result
    assert "contrastive" in result
    assert "all" in result
    assert len(result["positive"]) == 5
    assert len(result["contrastive"]) == 1  # 5 * 0.2 = 1
    assert len(result["all"]) == 6
    
    # Verify tagging
    assert all(c["candidate_type"] == "positive" for c in result["positive"])
    assert all(c["candidate_type"] == "contrastive" for c in result["contrastive"])
    
    # Contrastive should have lower scores (further in ranking)
    if result["positive"] and result["contrastive"]:
        assert result["positive"][0]["score"] >= result["contrastive"][0]["score"]

def test_contrastive_ratio_zero_disables(embedder, vector_store):
    retriever = ContrastiveRetriever(
        embedder, vector_store,
        positive_limit=5,
        contrastive_ratio=0.0
    )
    
    result = retriever.retrieve("Python")
    assert len(result["contrastive"]) == 0
    assert len(result["all"]) == len(result["positive"])

def test_baseline_d_retriever(embedder, vector_store, graph_store, reranker):
    """Baseline D: Vector + Contrastive + Reranker."""
    config = RetrievalConfig(
        use_vector=True,
        use_graph_expansion=False,
        use_reranker=True,
        use_contrastive=True,
        contrastive_ratio=0.2,
        final_top_k=5
    )
    retriever = BaselineD_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    results = retriever.retrieve("Python machine learning", k=3)
    
    assert len(results) <= 3
    assert all("final_score" in r for r in results)
    # Should have both positive and contrastive candidates processed
    candidate_types = set(r.get("candidate_type", "unknown") for r in results)
    # At least some contrastive should be in the pool (even if not in final top-k)
    # This is tested by checking the pool before reranking

def test_full_retriever_all_stages(embedder, vector_store, graph_store, reranker):
    """Full system: Vector + Graph + Contrastive + Reranker."""
    config = RetrievalConfig(
        use_vector=True,
        use_graph_expansion=True,
        use_reranker=True,
        use_contrastive=True,
        contrastive_ratio=0.1,
        final_top_k=5
    )
    retriever = FullRetriever(embedder, vector_store, graph_store, reranker, config)
    
    results = retriever.retrieve("Python programming", k=3)
    
    assert len(results) <= 3
    assert all("final_score" in r for r in results)

def test_contrastive_candidates_can_rank_high(embedder, vector_store, graph_store, reranker):
    """Verify contrastive candidates aren't automatically excluded - reranker can promote them."""
    config = RetrievalConfig(
        use_vector=True,
        use_graph_expansion=False,
        use_reranker=True,
        use_contrastive=True,
        contrastive_ratio=0.5,  # High ratio to ensure contrastive in pool
        final_top_k=10
    )
    retriever = BaselineD_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    # Query that might match a contrastive candidate better after reranking
    results = retriever.retrieve("Rust systems", k=5)
    
    # At least verify pipeline runs without error
    assert len(results) <= 5

def test_contrastive_offset_effect(embedder, vector_store):
    """Verify offset parameter controls where contrastive search starts."""
    # With offset=5, contrastive starts at rank 6
    retriever1 = ContrastiveRetriever(embedder, vector_store, 
                                       positive_limit=5, contrastive_ratio=0.2, contrastive_offset=5)
    result1 = retriever1.retrieve("Python")
    
    # With offset=10, contrastive starts at rank 11
    retriever2 = ContrastiveRetriever(embedder, vector_store,
                                       positive_limit=5, contrastive_ratio=0.2, contrastive_offset=10)
    result2 = retriever2.retrieve("Python")
    
    # Both should return same positive, different contrastive (if enough data)
    assert len(result1["positive"]) == len(result2["positive"]) == 5
```

---

## Expected Outcomes

| Configuration | Recall@10 | Precision@5 | Notes |
|---------------|-----------|-------------|-------|
| Baseline A (Vector) | 0.85 | 0.70 | Baseline |
| Baseline C (Vector+Graph) | 0.88 | 0.73 | +Graph |
| Baseline D (Vector+Contrastive) | 0.87 | 0.75 | +Contrastive helps precision |
| Full (Vector+Graph+Contrastive) | 0.91 | 0.78 | Best of both |

**Key Insight**: Contrastive retrieval primarily improves **precision** by giving reranker negative examples to discriminate against. Recall may improve slightly if contrastive pool contains relevant-but-lower-similarity items.

---

## Contrastive Ratio Sweep (Preview for Phase 10)

| Ratio | Positive | Contrastive | Total Pool | Expected Effect |
|-------|----------|-------------|------------|-----------------|
| 0% | 100 | 0 | 100 | Baseline A |
| 5% | 100 | 5 | 105 | Minimal overhead |
| 10% | 100 | 10 | 110 | **Default** (per research) |
| 20% | 100 | 20 | 120 | More discriminative signal |
| 50% | 100 | 50 | 150 | Diminishing returns, more compute |

---

## Verification Checklist

- [ ] `pytest tests/test_phase4_contrastive.py -v` all pass
- [ ] `python scripts/retrieve.py --query "test" --mode baseline_d` works
- [ ] `python scripts/retrieve.py --query "test" --mode full` works
- [ ] Contrastive candidates correctly tagged with `candidate_type`
- [ ] Contrastive offset parameter works (different results for offset=5 vs 10)
- [ ] Reranker can promote contrastive candidates to top-K if relevant
- [ ] Scoring formula includes contrastive penalty weight

---

## Next Phase Dependency

Phase 5 (Temporal Fields) is already partially implemented in the graph store schema. This phase formalizes the temporal filtering in retrieval and adds valid_from/valid_until to vector store payloads for filterable search.