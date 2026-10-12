# Phase 5: Temporal Fields — valid_from / valid_until Filtering & Time-Aware Retrieval

---

## Overview

**Goal**: Formalize temporal validity in both vector and graph stores. Enable time-aware retrieval: "what did I believe in 2023?" vs "what do I believe now?"

**Scope**: 
- Vector store payload filtering on `valid_from` / `valid_until`
- Graph store temporal edge validity (already in schema)
- Query-time temporal context (default: "now", overrideable)
- Temporal filtering in retrieval pipeline
- Recency scoring already in Phase 3 scorer

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Temporal Filter Module | `memory/temporal/filter.py` | Qdrant filter builders, time parsing |
| Temporal Retrieval | `memory/retrieval/temporal.py` | Time-aware search variants |
| Updated Vector Store | `memory/vector_store/qdrant_store.py` | Payload schema with temporal fields |
| Updated Graph Store | `memory/graph/kuzu_store.py` | Temporal query helpers (already have) |
| Unit Tests | `tests/test_phase5_temporal.py` | Verify temporal filtering |

---

## Implementation Details

### 1. Temporal Filter Module (`memory/temporal/filter.py`)

```python
"""
Temporal filtering utilities for Qdrant and Kuzu.
Handles: valid_from, valid_until, query_time, relative time ranges.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from qdrant_client.models import Filter, FieldCondition, Range, DatetimeRange

class TemporalFilter:
    """Build Qdrant filters for temporal validity."""
    
    @staticmethod
    def current_validity(query_time: datetime = None) -> Filter:
        """Filter for memories valid at query_time (default: now)."""
        query_time = query_time or datetime.utcnow()
        ts = query_time.isoformat() + "Z"
        
        return Filter(
            must=[
                # valid_from <= query_time
                FieldCondition(
                    key="valid_from",
                    range=Range(lte=ts)
                ),
                # valid_until is NULL OR valid_until > query_time
                FieldCondition(
                    key="valid_until",
                    range=Range(gt=ts)
                )
            ]
        )
    
    @staticmethod
    def validity_at(query_time: datetime) -> Filter:
        """Explicit time point filter."""
        return TemporalFilter.current_validity(query_time)
    
    @staticmethod
    def historical_only(query_time: datetime = None) -> Filter:
        """Filter for memories NO LONGER valid (superseded/expired)."""
        query_time = query_time or datetime.utcnow()
        ts = query_time.isoformat() + "Z"
        
        return Filter(
            must=[
                FieldCondition(key="valid_from", range=Range(lte=ts)),
                FieldCondition(key="valid_until", range=Range(lte=ts))
            ]
        )
    
    @staticmethod
    def time_range(start: datetime, end: datetime) -> Filter:
        """Memories whose validity window overlaps [start, end]."""
        return Filter(
            must=[
                FieldCondition(key="valid_from", range=Range(lte=end.isoformat() + "Z")),
                # valid_until is NULL OR >= start
                FieldCondition(key="valid_until", range=Range(gte=start.isoformat() + "Z"))
            ]
        )
    
    @staticmethod
    def relative_range(days_back: int, query_time: datetime = None) -> Filter:
        """Memories valid within last N days."""
        query_time = query_time or datetime.utcnow()
        start = query_time - timedelta(days=days_back)
        return TemporalFilter.time_range(start, query_time)
    
    @staticmethod
    def combine_with(base_filter: Filter, temporal_filter: Filter) -> Filter:
        """Combine base filter (e.g., user_id) with temporal filter."""
        if not base_filter or not base_filter.must:
            return temporal_filter
        
        combined_must = list(base_filter.must) + list(temporal_filter.must)
        return Filter(must=combined_must)


class TimeParser:
    """Parse natural language time expressions for queries."""
    
    @staticmethod
    def parse_query_time(query: str, default: datetime = None) -> Tuple[datetime, str]:
        """
        Extract temporal intent from query.
        Returns (query_time, temporal_mode) where mode in: 'now', 'historical', 'specific', 'range'
        """
        query_lower = query.lower()
        now = default or datetime.utcnow()
        
        # Current state queries
        if any(kw in query_lower for kw in ["now", "currently", "at present", "what do i", "what am i"]):
            return now, "now"
        
        # Historical queries
        if any(kw in query_lower for kw in ["before", "previously", "used to", "past", "historical", "earlier"]):
            return now, "historical"
        
        # Specific time references (simplified)
        # Could be extended with dateparser library
        if "in " in query_lower and any(year in query_lower for year in ["2023", "2024", "2025"]):
            return now, "specific"
        
        # Range queries
        if any(kw in query_lower for kw in ["last week", "last month", "recent", "past month"]):
            return now, "range"
        
        return now, "now"  # Default to current
    
    @staticmethod
    def get_filter_for_mode(mode: str, query_time: datetime = None) -> Filter:
        """Get appropriate filter for temporal mode."""
        if mode == "historical":
            return TemporalFilter.historical_only(query_time)
        elif mode == "range":
            return TemporalFilter.relative_range(30, query_time)  # Last 30 days
        elif mode == "specific":
            # Would need parsed date - fallback to current
            return TemporalFilter.current_validity(query_time)
        else:  # "now" default
            return TemporalFilter.current_validity(query_time)
```

### 2. Updated Vector Store Payload Schema (`memory/vector_store/qdrant_store.py` — additions)

```python
# Add to QdrantVectorStore class

def upsert_with_temporal(self, texts: List[str], embeddings: np.ndarray, 
                          payloads: List[Dict], 
                          valid_from: List[datetime] = None,
                          valid_until: List[datetime] = None) -> List[str]:
    """Upsert with explicit temporal fields."""
    points = []
    ids = []
    now = datetime.utcnow()
    
    for i, (text, emb, payload) in enumerate(zip(texts, embeddings, payloads)):
        pid = str(uuid.uuid4())
        ids.append(pid)
        
        # Add temporal fields to payload
        vf = valid_from[i] if valid_from else now
        vu = valid_until[i] if valid_until else None
        
        full_payload = {
            "text": text,
            **payload,
            "valid_from": vf.isoformat() + "Z",
            "valid_until": vu.isoformat() + "Z" if vu else None
        }
        
        points.append(PointStruct(id=pid, vector=emb.tolist(), payload=full_payload))
    
    self.client.upsert(collection_name=COLLECTION_NAME, points=points)
    return ids

def search_temporal(self, query_embedding: np.ndarray, limit: int = 10,
                    query_time: datetime = None,
                    mode: str = "now") -> List[Dict]:
    """Search with temporal filtering."""
    from memory.temporal.filter import TimeParser, TemporalFilter
    
    if mode == "auto":
        # Would need query text - placeholder
        mode = "now"
    
    temporal_filter = TimeParser.get_filter_for_mode(mode, query_time)
    return self.search(query_embedding, limit=limit, query_filter=temporal_filter)
```

### 3. Temporal Retrieval Module (`memory/retrieval/temporal.py`)

```python
"""
Time-aware retrieval variants for different query intents.
"""
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.temporal.filter import TemporalFilter, TimeParser

class TemporalRetriever:
    """Retrieval with explicit temporal control."""
    
    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore, 
                 graph_store: KuzuGraphStore = None):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
    
    def retrieve_current(self, query: str, limit: int = 10) -> List[Dict]:
        """Current beliefs only (valid now)."""
        q_emb = self.embedder.embed_single(query)
        return self.vector_store.search_temporal(q_emb, limit=limit, mode="now")
    
    def retrieve_historical(self, query: str, limit: int = 10) -> List[Dict]:
        """Superseded/expired beliefs only."""
        q_emb = self.embedder.embed_single(query)
        return self.vector_store.search_temporal(q_emb, limit=limit, mode="historical")
    
    def retrieve_at_time(self, query: str, at_time: datetime, limit: int = 10) -> List[Dict]:
        """Beliefs valid at specific timestamp."""
        q_emb = self.embedder.embed_single(query)
        return self.vector_store.search_temporal(
            q_emb, limit=limit, query_time=at_time, mode="now"  # Uses explicit time
        )
    
    def retrieve_range(self, query: str, start: datetime, end: datetime, limit: int = 10) -> List[Dict]:
        """Beliefs overlapping time range."""
        q_emb = self.embedder.embed_single(query)
        temporal_filter = TemporalFilter.time_range(start, end)
        return self.vector_store.search(q_emb, limit=limit, query_filter=temporal_filter)
    
    def retrieve_auto(self, query: str, limit: int = 10) -> List[Dict]:
        """Auto-detect temporal intent from query."""
        q_emb = self.embedder.embed_single(query)
        query_time, mode = TimeParser.parse_query_time(query)
        temporal_filter = TimeParser.get_filter_for_mode(mode, query_time)
        return self.vector_store.search(q_emb, limit=limit, query_filter=temporal_filter)


class TemporalGraphRetriever:
    """Graph-side temporal queries."""
    
    def __init__(self, graph_store: KuzuGraphStore):
        self.graph_store = graph_store
    
    def get_current_state(self, entity_id: str) -> List[Dict]:
        """Currently valid relationships for entity."""
        return self.graph_store.get_current_relationships(entity_id)
    
    def get_history(self, entity_id: str) -> List[Dict]:
        """All relationships (including superseded) for entity."""
        query = f"""
            MATCH (e:Entity {{id: '{entity_id}'}})-[r:Relationship]->(other:Entity)
            RETURN r, other
            ORDER BY r.valid_from
        """
        result = self.graph_store.conn.execute(query)
        return result.get_as_df().to_dict("records")
    
    def get_timeline(self, entity_id: str) -> List[Dict]:
        """Full timeline: current + superseded with transition markers."""
        query = f"""
            MATCH (e:Entity {{id: '{entity_id}'}})-[r:Relationship]->(other:Entity)
            RETURN r, other, r.valid_from, r.valid_until, r.supersedes_edge_id
            ORDER BY r.valid_from
        """
        result = self.graph_store.conn.execute(query)
        return result.get_as_df().to_dict("records")
    
    def get_contradictions(self, entity_id: str) -> List[Dict]:
        """All CONTRADICTS edges for entity."""
        return self.graph_store.get_contradictions(entity_id)
```

### 4. Enhanced Hybrid Retriever with Temporal (`memory/retrieval/hybrid.py` — additions)

```python
# Add to HybridRetriever class

from memory.retrieval.temporal import TemporalRetriever
from memory.temporal.filter import TimeParser

class HybridRetriever:
    def __init__(self, *args, **kwargs):
        # ... existing init ...
        self.temporal_retriever = TemporalRetriever(embedder, vector_store, graph_store)
    
    def retrieve(self, query: str, k: int = None, 
                 query_time: datetime = None,
                 temporal_mode: str = "auto") -> List[Dict]:
        """
        Enhanced retrieve with temporal control.
        
        temporal_mode: "auto" (detect from query), "now", "historical", "specific", "range"
        """
        k = k or self.config.final_top_k
        query_time = query_time or datetime.utcnow()
        
        # Auto-detect temporal mode if needed
        if temporal_mode == "auto":
            _, temporal_mode = TimeParser.parse_query_time(query, query_time)
        
        # ... rest of pipeline with temporal filtering ...
        
        # Vector search with temporal filter
        if self.config.use_vector:
            if temporal_mode != "now":
                temporal_filter = TimeParser.get_filter_for_mode(temporal_mode, query_time)
            else:
                temporal_filter = TemporalFilter.current_validity(query_time)
            
            vector_results = self.vector_retriever.retrieve(
                query, limit=self.config.vector_candidates, filter=temporal_filter
            )
        else:
            vector_results = []
        
        # Graph expansion with temporal filtering
        if self.config.use_graph_expansion and query_entities:
            graph_expanded = self._expand_graph_temporal(query_entities, query_time, temporal_mode)
        else:
            graph_expanded = []
        
        # ... scoring and reranking unchanged ...
```

### 5. Unit Tests (`tests/test_phase5_temporal.py`)

```python
import pytest
from datetime import datetime, timedelta
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.temporal.filter import TemporalFilter, TimeParser
from memory.retrieval.temporal import TemporalRetriever, TemporalGraphRetriever

@pytest.fixture
def embedder():
    return Embedder()

@pytest.fixture
def vector_store(tmp_path):
    store = QdrantVectorStore(path=str(tmp_path / "qdrant_test"))
    now = datetime.utcnow()
    past = now - timedelta(days=10)
    future = now + timedelta(days=10)
    
    texts = [
        "Current: I use Python for ML",           # valid now
        "Past: I used R for stats",               # expired
        "Future: I will learn Rust",              # not yet valid
        "Always: I like clean code"               # no end date
    ]
    
    embeddings = embedder.embed(texts)
    payloads = [
        {"source": "test", "valid_from": now.isoformat(), "valid_until": None, "memory_id": "m1"},
        {"source": "test", "valid_from": past.isoformat(), "valid_until": now.isoformat(), "memory_id": "m2"},
        {"source": "test", "valid_from": future.isoformat(), "valid_until": None, "memory_id": "m3"},
        {"source": "test", "valid_from": past.isoformat(), "valid_until": None, "memory_id": "m4"},
    ]
    store.upsert(texts, embeddings, payloads)
    return store

@pytest.fixture
def graph_store(tmp_path):
    store = KuzuGraphStore(path=str(tmp_path / "kuzu_test"))
    now = datetime.utcnow()
    past = now - timedelta(days=10)
    
    # Current edge
    store.upsert_entity("Python", "LANGUAGE")
    store.upsert_entity("ML", "FIELD")
    store.conn.execute(f"""
        MATCH (s:Entity {{id: 'python'}}), (t:Entity {{id: 'ml'}})
        CREATE (s)-[:Relationship {{
            relation_type: 'USED_FOR', confidence: 0.9,
            valid_from: TIMESTAMP('{now.isoformat()}'), valid_until: NULL,
            source_memory_id: 'm1'
        }}]->(t)
    """)
    
    # Superseded edge
    store.upsert_entity("R", "LANGUAGE")
    store.upsert_entity("stats", "FIELD")
    store.conn.execute(f"""
        MATCH (s:Entity {{id: 'r'}}), (t:Entity {{id: 'stats'}})
        CREATE (s)-[:Relationship {{
            relation_type: 'USED_FOR', confidence: 0.8,
            valid_from: TIMESTAMP('{past.isoformat()}'), valid_until: TIMESTAMP('{now.isoformat()}'),
            source_memory_id: 'm2'
        }}]->(t)
    """)
    
    yield store
    store.close()

def test_temporal_filter_current(embedder, vector_store):
    """Current validity filter returns only currently valid."""
    q_emb = embedder.embed_single("Python")
    filter = TemporalFilter.current_validity()
    results = vector_store.search(q_emb, limit=10, query_filter=filter)
    
    # Should get m1 (current) and m4 (always), NOT m2 (expired) or m3 (future)
    memory_ids = [r["payload"].get("memory_id") for r in results]
    assert "m1" in memory_ids
    assert "m4" in memory_ids
    assert "m2" not in memory_ids
    assert "m3" not in memory_ids

def test_temporal_filter_historical(embedder, vector_store):
    """Historical filter returns only expired/superseded."""
    q_emb = embedder.embed_single("R")
    filter = TemporalFilter.historical_only()
    results = vector_store.search(q_emb, limit=10, query_filter=filter)
    
    memory_ids = [r["payload"].get("memory_id") for r in results]
    assert "m2" in memory_ids  # Expired
    assert "m1" not in memory_ids  # Still valid
    assert "m4" not in memory_ids  # Still valid

def test_temporal_filter_time_range(embedder, vector_store):
    """Time range filter for overlapping validity."""
    now = datetime.utcnow()
    past = now - timedelta(days=10)
    future = now + timedelta(days=10)
    
    # Range covering past to now
    filter = TemporalFilter.time_range(past, now)
    q_emb = embedder.embed_single("code")
    results = vector_store.search(q_emb, limit=10, query_filter=filter)
    
    memory_ids = [r["payload"].get("memory_id") for r in results]
    # m1 (now), m2 (past), m4 (always) should match
    # m3 (future only) should NOT match
    assert "m3" not in memory_ids

def test_time_parser_current_mode():
    """Auto-detect current state queries."""
    parser = TimeParser()
    now = datetime(2025, 1, 15, 12, 0, 0)
    
    time, mode = parser.parse_query_time("what do I currently use", now)
    assert mode == "now"
    
    time, mode = parser.parse_query_time("what am I using now", now)
    assert mode == "now"

def test_time_parser_historical_mode():
    """Auto-detect historical queries."""
    parser = TimeParser()
    now = datetime(2025, 1, 15, 12, 0, 0)
    
    time, mode = parser.parse_query_time("what did I use previously", now)
    assert mode == "historical"
    
    time, mode = parser.parse_query_time("what did I use before", now)
    assert mode == "historical"

def test_temporal_retriever_current(embedder, vector_store, graph_store):
    """TemporalRetriever.current returns current beliefs."""
    retriever = TemporalRetriever(embedder, vector_store, graph_store)
    results = retriever.retrieve_current("Python", limit=5)
    
    memory_ids = [r["payload"].get("memory_id") for r in results]
    assert "m1" in memory_ids
    assert "m2" not in memory_ids

def test_temporal_retriever_historical(embedder, vector_store, graph_store):
    """TemporalRetriever.historical returns superseded beliefs."""
    retriever = TemporalRetriever(embedder, vector_store, graph_store)
    results = retriever.retrieve_historical("R", limit=5)
    
    memory_ids = [r["payload"].get("memory_id") for r in results]
    assert "m2" in memory_ids

def test_temporal_graph_retriever_current(graph_store):
    """Graph retriever gets current relationships."""
    retriever = TemporalGraphRetriever(graph_store)
    current = retriever.get_current_state("python")
    
    assert len(current) == 1
    assert current[0]["r"]["relation_type"] == "USED_FOR"

def test_temporal_graph_retriever_history(graph_store):
    """Graph retriever gets full history including superseded."""
    retriever = TemporalGraphRetriever(graph_store)
    history = retriever.get_history("r")
    
    assert len(history) == 1
    assert history[0]["r"]["relation_type"] == "USED_FOR"
    assert history[0]["r"]["valid_until"] is not None  # Has end date

def test_temporal_graph_retriever_timeline(graph_store):
    """Timeline shows transitions with supersession info."""
    retriever = TemporalGraphRetriever(graph_store)
    timeline = retriever.get_timeline("python")
    
    assert len(timeline) >= 1
    # Check for supersedes_edge_id field
    for item in timeline:
        assert "supersedes_edge_id" in item["r"]

def test_combined_filter_user_and_temporal(embedder, vector_store):
    """Combine user filter with temporal filter."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    now = datetime.utcnow()
    user_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value="user1"))])
    temporal_filter = TemporalFilter.current_validity(now)
    combined = TemporalFilter.combine_with(user_filter, temporal_filter)
    
    assert combined is not None
    assert len(combined.must) == 3  # user_id + valid_from + valid_until
```

---

## Expected Outcomes

| Query Type | Filter Applied | Expected Results |
|------------|----------------|------------------|
| "what do I use now" | `valid_from <= now AND (valid_until IS NULL OR valid_until > now)` | Current beliefs only |
| "what did I use before" | `valid_from <= now AND valid_until <= now` | Superseded/expired beliefs |
| "what was I using in June 2024" | `valid_from <= June 2024 AND valid_until >= June 2024` | Point-in-time beliefs |
| "recent changes" | `valid_from >= 30 days ago` | Recent transitions |

---

## Verification Checklist

- [ ] `pytest tests/test_phase5_temporal.py -v` all pass
- [ ] Vector store temporal filtering works (current/historical/range)
- [ ] Graph store temporal queries work (current/history/timeline)
- [ ] Time parser correctly classifies query intent
- [ ] Hybrid retriever respects temporal_mode parameter
- [ ] Combined filters (user + temporal) work correctly
- [ ] No regression in non-temporal retrieval

---

## Next Phase Dependency

Phase 6 (Contradiction/Supersession Detection) builds on the temporal infrastructure. It uses `valid_until` to mark superseded edges and adds `CONTRADICTS` edges for genuine conflicts. The graph store already has the schema; this phase implements the detection logic during ingestion.