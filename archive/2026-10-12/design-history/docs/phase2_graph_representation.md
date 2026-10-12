# Phase 2: Graph Representation — Entity/Relation Extraction → Kuzu Schema

---

## Overview

**Goal**: Add a temporal knowledge graph layer. Every ingested memory produces graph nodes (entities) and edges (relationships) in Kuzu, linked back to vector store entries.

**Scope**: 
- NVIDIA NIM extractor (OpenAI-compatible, hosted)
- Kuzu embedded graph database (Cypher, vector+FTS built-in)
- Graph schema matching memory object from architecture plan
- Extraction pipeline: text → entities + relations + temporal + contradictions

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| NIM Extractor | `memory/ingestion/nim_extractor.py` | OpenAI-compatible client for NVIDIA NIM |
| Kuzu Wrapper | `memory/graph/kuzu_store.py` | Schema, upsert, traversal |
| Graph Models | `memory/graph/models.py` | Pydantic models for entities, relations |
| Ingestion Pipeline | `memory/ingestion/pipeline.py` | End-to-end: text → vector + graph |
| Updated Ingest Script | `scripts/ingest.py` | Now also writes to graph |
| Unit Tests | `tests/test_phase2_graph.py` | Verify extraction, graph upsert, traversal |

---

## Implementation Details

### 1. Graph Models (`memory/graph/models.py`)

```python
"""
Pydantic models matching architecture_plan.md §3 schema.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Literal
import uuid

MemoryType = Literal["fact", "preference", "context", "summary"]
RelationType = Literal[
    "USES", "PREFERS", "LEARNING", "WORKS_ON", "DEPENDS_ON",
    "USED_FOR", "RELATED_TO", "PART_OF", "CONTRADICTS", "SUPERSEDES"
]

class Relation(BaseModel):
    source: str
    relation_type: RelationType
    target: str
    confidence: float = Field(ge=0.0, le=1.0)
    valid_from: datetime
    valid_until: Optional[datetime] = None
    source_memory_id: str

class Memory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_text: str
    normalized_text: str
    embedding: List[float]
    
    entities: List[str] = []
    relationships: List[Relation] = []
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    valid_from: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    source: str
    memory_type: MemoryType
    
    graph_node_id: Optional[str] = None  # Kuzu node ID
```

### 2. NVIDIA NIM Extractor (`memory/ingestion/nim_extractor.py`)

```python
"""
NVIDIA NIM extractor — OpenAI-compatible endpoint.
Single extraction call returns entities, relations, temporal, contradictions.
"""
import os
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pydantic import BaseModel
from memory.graph.models import Memory, Relation, RelationType

EXTRACTION_PROMPT = """
Extract from this input:
1. ENTITIES: named things (people, tools, languages, projects, concepts)
2. RELATIONSHIPS: entity1 -[TYPE]-> entity2, with confidence (0-1)
   Types: USES, PREFERS, LEARNING, WORKS_ON, DEPENDS_ON, USED_FOR, RELATED_TO, PART_OF, CONTRADICTS, SUPERSEDES
3. TEMPORAL: does this state a current fact, a past fact, or a change/transition?
   Output valid_from (ISO8601) and valid_until (ISO8601 or null)
4. CONTRADICTS: does this conflict with a plausible prior memory about the same entity?
   If transition language ("switched to", "instead of", "started using") → SUPERSEDES
   If genuine contradiction → CONTRADICTS

Output JSON only. No prose.
Schema:
{
  "entities": ["entity1", "entity2"],
  "relationships": [
    {"source": "entity1", "relation_type": "USES", "target": "entity2", "confidence": 0.9}
  ],
  "valid_from": "2025-01-15T10:00:00Z",
  "valid_until": null,
  "contradictions": [
    {"source": "entity1", "relation_type": "SUPERSEDES", "target": "old_entity", "confidence": 0.8}
  ]
}
"""

class NIMExtractor:
    def __init__(
        self, 
        model: str = "meta/llama-3.1-70b-instruct",
        api_key: Optional[str] = None,
        base_url: str = "https://integrate.api.nvidia.com/v1"
    ):
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY")
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not set in env or passed explicitly")
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.model = model
    
    def extract(self, text: str, memory_id: str) -> Dict[str, Any]:
        """Single call extraction. Returns structured dict."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.0,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content
        return json.loads(raw)
    
    def extract_batch(self, texts: List[str], memory_ids: List[str]) -> List[Dict]:
        """Batch extraction (sequential for rate limit safety)."""
        return [self.extract(t, mid) for t, mid in zip(texts, memory_ids)]
```

### 3. Kuzu Store Wrapper (`memory/graph/kuzu_store.py`)

```python
"""
Kuzu embedded graph database wrapper.
Schema: Entity nodes, Relationship edges, Memory nodes linking to vectors.
"""
import kuzu
from typing import List, Optional, Dict, Any
from datetime import datetime
from memory.graph.models import Memory, Relation, RelationType

class KuzuGraphStore:
    SCHEMA_DDL = """
    -- Entity node table
    CREATE NODE TABLE Entity (
        id STRING,           -- normalized entity name (primary key)
        name STRING,         -- display name
        entity_type STRING,  -- PERSON, TOOL, LANGUAGE, PROJECT, CONCEPT
        first_seen TIMESTAMP,
        last_seen TIMESTAMP,
        mention_count INT64,
        PRIMARY KEY (id)
    );
    
    -- Memory node table (links to vector store)
    CREATE NODE TABLE Memory (
        id STRING,           -- memory UUID (primary key)
        vector_id STRING,    -- Qdrant point ID
        raw_text STRING,
        normalized_text STRING,
        timestamp TIMESTAMP,
        valid_from TIMESTAMP,
        valid_until TIMESTAMP,
        confidence DOUBLE,
        importance DOUBLE,
        source STRING,
        memory_type STRING,
        PRIMARY KEY (id)
    );
    
    -- Relationship edge table (temporal, with validity)
    CREATE REL TABLE Relationship (
        FROM Entity TO Entity,
        relation_type STRING,  -- USES, PREFERS, etc.
        confidence DOUBLE,
        valid_from TIMESTAMP,
        valid_until TIMESTAMP,
        source_memory_id STRING,
        supersedes_edge_id STRING  -- ID of edge this supersedes
    );
    
    -- CONTRADICTS edge (separate for querying)
    CREATE REL TABLE Contradicts (
        FROM Entity TO Entity,
        confidence DOUBLE,
        valid_from TIMESTAMP,
        source_memory_id STRING
    );
    
    -- MENTIONS edge: Memory -> Entity
    CREATE REL TABLE Mentions (
        FROM Memory TO Entity
    );
    """
    
    def __init__(self, path: str = "./kuzu_data"):
        self.db = kuzu.Database(path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()
    
    def _init_schema(self):
        """Create tables if not exist."""
        for stmt in self.SCHEMA_DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    self.conn.execute(stmt)
                except Exception as e:
                    # Table may already exist
                    pass
    
    # === Entity Operations ===
    
    def upsert_entity(self, name: str, entity_type: str = "CONCEPT") -> str:
        """Upsert entity, return normalized ID."""
        eid = name.lower().replace(" ", "_")
        self.conn.execute(f"""
            MERGE (e:Entity {{id: '{eid}'}})
            ON CREATE SET e.name = '{name}', e.entity_type = '{entity_type}',
                          e.first_seen = TIMESTAMP(), e.last_seen = TIMESTAMP(),
                          e.mention_count = 1
            ON MATCH SET e.last_seen = TIMESTAMP(), e.mention_count = e.mention_count + 1
        """)
        return eid
    
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        result = self.conn.execute(f"MATCH (e:Entity {{id: '{entity_id}'}}) RETURN e")
        return result.get_as_df().to_dict("records")[0] if result.has_next() else None
    
    # === Memory Operations ===
    
    def upsert_memory(self, memory: Memory, vector_id: str) -> str:
        """Create Memory node and link to entities."""
        mid = memory.id
        self.conn.execute(f"""
            CREATE (m:Memory {{
                id: '{mid}',
                vector_id: '{vector_id}',
                raw_text: '{memory.raw_text.replace("'", "''")}',
                normalized_text: '{memory.normalized_text.replace("'", "''")}',
                timestamp: TIMESTAMP('{memory.timestamp.isoformat()}'),
                valid_from: TIMESTAMP('{memory.valid_from.isoformat()}'),
                valid_until: {'NULL' if memory.valid_until is None else f"TIMESTAMP('{memory.valid_until.isoformat()}')"},
                confidence: {memory.confidence},
                importance: {memory.importance},
                source: '{memory.source}',
                memory_type: '{memory.memory_type}'
            }})
        """)
        
        # Link to entities
        for entity in memory.entities:
            eid = self.upsert_entity(entity)
            self.conn.execute(f"""
                MATCH (m:Memory {{id: '{mid}'}}), (e:Entity {{id: '{eid}'}})
                CREATE (m)-[:Mentions]->(e)
            """)
        
        return mid
    
    # === Relationship Operations ===
    
    def upsert_relationship(self, rel: Relation, source_entity_id: str, target_entity_id: str):
        """Create temporal relationship edge."""
        self.conn.execute(f"""
            MATCH (s:Entity {{id: '{source_entity_id}'}}), (t:Entity {{id: '{target_entity_id}'}})
            CREATE (s)-[:Relationship {{
                relation_type: '{rel.relation_type}',
                confidence: {rel.confidence},
                valid_from: TIMESTAMP('{rel.valid_from.isoformat()}'),
                valid_until: {'NULL' if rel.valid_until is None else f"TIMESTAMP('{rel.valid_until.isoformat()}')"},
                source_memory_id: '{rel.source_memory_id}'
            }}]->(t)
        """)
    
    def supersede_edge(self, old_edge_id: str, new_rel: Relation, 
                       source_eid: str, target_eid: str):
        """Mark old edge as superseded, create new SUPERSEDES edge."""
        # Update old edge valid_until
        self.conn.execute(f"""
            MATCH ()-[r:Relationship]->() WHERE ID(r) = {old_edge_id}
            SET r.valid_until = TIMESTAMP('{new_rel.valid_from.isoformat()}')
        """)
        # Create new edge with supersedes reference
        self.conn.execute(f"""
            MATCH (s:Entity {{id: '{source_eid}'}}), (t:Entity {{id: '{target_eid}'}})
            CREATE (s)-[:Relationship {{
                relation_type: '{new_rel.relation_type}',
                confidence: {new_rel.confidence},
                valid_from: TIMESTAMP('{new_rel.valid_from.isoformat()}'),
                valid_until: {'NULL' if new_rel.valid_until is None else f"TIMESTAMP('{new_rel.valid_until.isoformat()}')"},
                source_memory_id: '{new_rel.source_memory_id}',
                supersedes_edge_id: '{old_edge_id}'
            }}]->(t)
        """)
    
    def add_contradiction(self, source_eid: str, target_eid: str, 
                          confidence: float, memory_id: str):
        """Add CONTRADICTS edge."""
        self.conn.execute(f"""
            MATCH (s:Entity {{id: '{source_eid}'}}), (t:Entity {{id: '{target_eid}'}})
            CREATE (s)-[:Contradicts {{
                confidence: {confidence},
                valid_from: TIMESTAMP(),
                source_memory_id: '{memory_id}'
            }}]->(t)
        """)
    
    # === Graph Traversal (Iron Web Layer) ===
    
    def expand_from_entities(self, entity_ids: List[str], hops: int = 2) -> List[Dict]:
        """1-2 hop traversal from matched entities. Returns subgraph."""
        if not entity_ids:
            return []
        
        id_list = "', '".join(entity_ids)
        query = f"""
            MATCH (start:Entity) WHERE start.id IN ['{id_list}']
            CALL {{
                WITH start
                MATCH (start)-[r:Relationship*1..{hops}]-(connected:Entity)
                WHERE r.valid_until IS NULL OR r.valid_until > TIMESTAMP()
                RETURN connected, r
            }}
            RETURN DISTINCT connected, r
        """
        result = self.conn.execute(query)
        return result.get_as_df().to_dict("records")
    
    def get_current_relationships(self, entity_id: str) -> List[Dict]:
        """Get all currently valid relationships for an entity."""
        query = f"""
            MATCH (e:Entity {{id: '{entity_id}'}})-[r:Relationship]->(other:Entity)
            WHERE r.valid_until IS NULL OR r.valid_until > TIMESTAMP()
            RETURN r, other
        """
        result = self.conn.execute(query)
        return result.get_as_df().to_dict("records")
    
    def get_contradictions(self, entity_id: str) -> List[Dict]:
        """Get all CONTRADICTS edges for an entity."""
        query = f"""
            MATCH (e:Entity {{id: '{entity_id}'}})-[c:Contradicts]->(other:Entity)
            RETURN c, other
        """
        result = self.conn.execute(query)
        return result.get_as_df().to_dict("records")
    
    def resolve_temporal(self, edges: List[Dict], query_time: datetime) -> List[Dict]:
        """Filter edges valid at query_time. Mark superseded."""
        # This is done in Python for flexibility, but could be Cypher
        valid = []
        for edge in edges:
            valid_from = edge.get("valid_from")
            valid_until = edge.get("valid_until")
            if valid_from and valid_from <= query_time:
                if valid_until is None or valid_until > query_time:
                    valid.append(edge)
        return valid
    
    def close(self):
        self.conn.close()
        self.db.close()
```

### 4. Ingestion Pipeline (`memory/ingestion/pipeline.py`)

```python
"""
End-to-end ingestion: text → embedding → vector store → extraction → graph store.
"""
from typing import List, Dict, Any
import uuid
from datetime import datetime
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.ingestion.nim_extractor import NIMExtractor
from memory.graph.kuzu_store import KuzuGraphStore
from memory.graph.models import Memory, Relation, RelationType

class IngestionPipeline:
    def __init__(
        self,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        extractor: NIMExtractor,
        graph_store: KuzuGraphStore
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.extractor = extractor
        self.graph_store = graph_store
    
    def process(self, text: str, source: str = "ingestion", 
                memory_type: str = "fact") -> Memory:
        """Process single text through full pipeline."""
        memory_id = str(uuid.uuid4())
        
        # 1. Embedding
        embedding = self.embedder.embed_single(text)
        
        # 2. Vector store upsert
        vector_ids = self.vector_store.upsert(
            [text], embedding.reshape(1, -1), 
            [{"source": source, "memory_id": memory_id}]
        )
        vector_id = vector_ids[0]
        
        # 3. NIM Extraction
        extraction = self.extractor.extract(text, memory_id)
        
        # 4. Build Memory object
        entities = extraction.get("entities", [])
        relationships = []
        for r in extraction.get("relationships", []):
            relationships.append(Relation(
                source=r["source"],
                relation_type=r["relation_type"],
                target=r["target"],
                confidence=r["confidence"],
                valid_from=datetime.fromisoformat(r.get("valid_from", datetime.utcnow().isoformat())),
                valid_until=datetime.fromisoformat(r["valid_until"]) if r.get("valid_until") else None,
                source_memory_id=memory_id
            ))
        
        valid_from = datetime.fromisoformat(extraction.get("valid_from", datetime.utcnow().isoformat()))
        valid_until = datetime.fromisoformat(extraction["valid_until"]) if extraction.get("valid_until") else None
        
        memory = Memory(
            id=memory_id,
            raw_text=text,
            normalized_text=text.strip(),  # Could add normalization
            embedding=embedding.tolist(),
            entities=entities,
            relationships=relationships,
            timestamp=datetime.utcnow(),
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=0.9,  # Default, could come from extractor
            importance=0.5,
            source=source,
            memory_type=memory_type
        )
        
        # 5. Graph store upsert
        self.graph_store.upsert_memory(memory, vector_id)
        
        # 6. Upsert relationships
        for rel in relationships:
            source_eid = self.graph_store.upsert_entity(rel.source)
            target_eid = self.graph_store.upsert_entity(rel.target)
            self.graph_store.upsert_relationship(rel, source_eid, target_eid)
        
        # 7. Handle contradictions/supersessions from extraction
        for contra in extraction.get("contradictions", []):
            source_eid = self.graph_store.upsert_entity(contra["source"])
            target_eid = self.graph_store.upsert_entity(contra["target"])
            if contra["relation_type"] == "SUPERSEDES":
                # Find existing edge to supersede
                existing = self.graph_store.get_current_relationships(source_eid)
                for e in existing:
                    if e["other"]["id"] == target_eid and e["r"]["relation_type"] == contra["relation_type"]:
                        self.graph_store.supersede_edge(e["r"]["id"], rel, source_eid, target_eid)
                        break
            elif contra["relation_type"] == "CONTRADICTS":
                self.graph_store.add_contradiction(source_eid, target_eid, 
                                                   contra["confidence"], memory_id)
        
        return memory
    
    def process_batch(self, texts: List[str], source: str = "batch") -> List[Memory]:
        """Process multiple texts."""
        return [self.process(t, source) for t in texts]
```

### 5. Updated Ingest Script (`scripts/ingest.py`)

```python
#!/usr/bin/env python3
"""
Updated ingest: text → vector + graph.
Usage: python scripts/ingest.py --file data/sample.txt
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.ingestion.nim_extractor import NIMExtractor
from memory.graph.kuzu_store import KuzuGraphStore
from memory.ingestion.pipeline import IngestionPipeline

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--source", default="manual_ingest")
    args = parser.parse_args()
    
    text = Path(args.file).read_text(encoding="utf-8")
    chunks = chunk_text(text, args.chunk_size, args.overlap)
    print(f"Created {len(chunks)} chunks")
    
    embedder = Embedder()
    vector_store = QdrantVectorStore()
    extractor = NIMExtractor()  # Requires NVIDIA_API_KEY
    graph_store = KuzuGraphStore()
    
    pipeline = IngestionPipeline(embedder, vector_store, extractor, graph_store)
    
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}...")
        memory = pipeline.process(chunk, source=args.source)
        print(f"  Entities: {memory.entities}")
        print(f"  Relations: {len(memory.relationships)}")
    
    print(f"\nVector store count: {vector_store.count()}")
    graph_store.close()

if __name__ == "__main__":
    main()
```

### 6. Unit Tests (`tests/test_phase2_graph.py`)

```python
import pytest
import os
from datetime import datetime
from memory.graph.kuzu_store import KuzuGraphStore
from memory.graph.models import Memory, Relation
from memory.ingestion.nim_extractor import NIMExtractor

@pytest.fixture
def graph_store(tmp_path):
    store = KuzuGraphStore(path=str(tmp_path / "kuzu_test"))
    yield store
    store.close()

@pytest.fixture
def sample_memory():
    return Memory(
        id="test-mem-1",
        raw_text="I use Python for data science",
        normalized_text="I use Python for data science",
        embedding=[0.1] * 384,
        entities=["Python", "data science"],
        relationships=[
            Relation(
                source="I",
                relation_type="USES",
                target="Python",
                confidence=0.9,
                valid_from=datetime.utcnow(),
                source_memory_id="test-mem-1"
            ),
            Relation(
                source="Python",
                relation_type="USED_FOR",
                target="data science",
                confidence=0.85,
                valid_from=datetime.utcnow(),
                source_memory_id="test-mem-1"
            )
        ],
        timestamp=datetime.utcnow(),
        valid_from=datetime.utcnow(),
        confidence=0.9,
        importance=0.7,
        source="test",
        memory_type="fact"
    )

def test_entity_upsert(graph_store):
    eid = graph_store.upsert_entity("Python", "LANGUAGE")
    assert eid == "python"
    
    entity = graph_store.get_entity(eid)
    assert entity is not None
    assert entity["e"]["name"] == "Python"
    assert entity["e"]["entity_type"] == "LANGUAGE"
    assert entity["e"]["mention_count"] == 1
    
    # Second mention increments count
    graph_store.upsert_entity("Python", "LANGUAGE")
    entity = graph_store.get_entity(eid)
    assert entity["e"]["mention_count"] == 2

def test_memory_upsert(graph_store, sample_memory):
    mid = graph_store.upsert_memory(sample_memory, "vector-123")
    assert mid == sample_memory.id
    
    # Verify mentions created
    result = graph_store.conn.execute(f"""
        MATCH (m:Memory {{id: '{mid}'}})-[:Mentions]->(e:Entity)
        RETURN e.id
    """)
    entities = [row[0] for row in result.get_as_df().values.tolist()]
    assert "python" in entities
    assert "data_science" in entities

def test_relationship_upsert(graph_store, sample_memory):
    graph_store.upsert_memory(sample_memory, "vector-123")
    
    for rel in sample_memory.relationships:
        source_eid = graph_store.upsert_entity(rel.source)
        target_eid = graph_store.upsert_entity(rel.target)
        graph_store.upsert_relationship(rel, source_eid, target_eid)
    
    # Query relationships
    result = graph_store.conn.execute("""
        MATCH (s:Entity)-[r:Relationship]->(t:Entity)
        RETURN s.id, r.relation_type, t.id, r.confidence
    """)
    rows = result.get_as_df().values.tolist()
    assert len(rows) == 2
    assert ("i", "USES", "python", 0.9) in [(r[0], r[1], r[2], r[3]) for r in rows]

def test_temporal_validity(graph_store):
    """Test valid_from/valid_until filtering."""
    from datetime import timedelta
    now = datetime.utcnow()
    past = now - timedelta(days=10)
    future = now + timedelta(days=10)
    
    # Insert edge valid in past
    graph_store.upsert_entity("old_tool")
    graph_store.upsert_entity("new_tool")
    graph_store.conn.execute(f"""
        MATCH (s:Entity {{id: 'old_tool'}}), (t:Entity {{id: 'new_tool'}})
        CREATE (s)-[:Relationship {{
            relation_type: 'USES',
            confidence: 0.9,
            valid_from: TIMESTAMP('{past.isoformat()}'),
            valid_until: TIMESTAMP('{now.isoformat()}'),
            source_memory_id: 'mem-1'
        }}]->(t)
    """)
    
    # Insert current edge
    graph_store.conn.execute(f"""
        MATCH (s:Entity {{id: 'old_tool'}}), (t:Entity {{id: 'new_tool'}})
        CREATE (s)-[:Relationship {{
            relation_type: 'USES',
            confidence: 0.95,
            valid_from: TIMESTAMP('{now.isoformat()}'),
            valid_until: NULL,
            source_memory_id: 'mem-2'
        }}]->(t)
    """)
    
    # Query at current time - should only get current edge
    current = graph_store.get_current_relationships("old_tool")
    assert len(current) == 1
    assert current[0]["r"]["confidence"] == 0.95

@pytest.mark.skipif(not os.environ.get("NVIDIA_API_KEY"), reason="NIM API key not set")
def test_nim_extraction():
    extractor = NIMExtractor()
    result = extractor.extract("I switched from Python to Rust for systems programming", "test-1")
    
    assert "entities" in result
    assert "relationships" in result
    assert "Python" in result["entities"] or "Rust" in result["entities"]
    # Should detect SUPERSEDES
    rel_types = [r["relation_type"] for r in result.get("relationships", [])]
    assert "SUPERSEDES" in rel_types or "USES" in rel_types
```

---

## Expected Outcomes

| Metric | Target |
|--------|--------|
| Extraction latency (NIM) | < 2s per call (network bound) |
| Graph upsert (10 entities, 5 rels) | < 50ms |
| 2-hop traversal (100 nodes) | < 20ms |
| Schema creation | < 100ms |
| Storage per 10K entities | ~5 MB |

---

## Verification Checklist

- [ ] `NVIDIA_API_KEY` set in environment
- [ ] `pip install -r requirements.txt` includes kuzu==0.11.3
- [ ] `python scripts/ingest.py --file data/sample.txt` creates both vector and graph entries
- [ ] Kuzu DB persisted to `./kuzu_data/`
- [ ] `pytest tests/test_phase2_graph.py -v` all pass
- [ ] Graph traversal returns expected entities/relations
- [ ] Temporal filtering works (valid_until respected)
- [ ] SUPERSEDES/CONTRADICTS edges created correctly

---

## Next Phase Dependency

Phase 3 requires: Working graph store with entity/relation data, and vector store with linked memory IDs. The hybrid retrieval will combine vector search results with graph expansion.