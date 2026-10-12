# Phase 1: Baseline A — Vector-Only Memory
## Embedding → Qdrant Local Mode → Top-K Retrieval

---

## Overview

**Goal**: Reproduce a working end-to-end vector memory system: ingest text → generate embeddings → store in Qdrant (embedded/local mode) → retrieve top-K by cosine similarity.

**Scope**: Single-file prototype first, then modularized. No graph, no contrastive, no reranker, no temporal fields.

---

## Deliverables

| Artifact | Path | Description |
|----------|------|-------------|
| Embedding wrapper | `memory/embeddings/embedder.py` | FastEmbed `bge-small-en-v1.5` wrapper |
| Vector store wrapper | `memory/vector_store/qdrant_store.py` | Qdrant local mode client + upsert/search |
| Ingestion CLI | `scripts/ingest.py` | Read text file → chunk → embed → upsert |
| Retrieval CLI | `scripts/retrieve.py` | Query → embed → search → print results |
| Unit tests | `tests/test_phase1_baseline.py` | Verify embeddings, upsert, search roundtrip |

---

## Implementation Details

### 1. Embedding Module (`memory/embeddings/embedder.py`)

```python
"""
FastEmbed wrapper for bge-small-en-v1.5 (384-dim, CPU/ONNX).
"""
from fastembed import TextEmbedding
from typing import List
import numpy as np

class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", cache_dir: str = "./.fastembed_cache"):
        self.model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        self.dim = 384  # Known for bge-small-en-v1.5
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """Return (n, 384) float32 array."""
        embeddings = list(self.model.embed(texts))
        return np.array(embeddings, dtype=np.float32)
    
    def embed_single(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
```

**Performance**: ~33ms per batch of 32 on CPU (M2 MacBook). No GPU, no PyTorch.

### 2. Vector Store Module (`memory/vector_store/qdrant_store.py`)

```python
"""
Qdrant local embedded mode wrapper.
No Docker/server needed: `QdrantClient(path="./qdrant_data")`
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition,
    MatchValue, SearchRequest, ScalarQuantizationConfig, ScalarQuantizationType,
    HnswConfigDiff
)
from typing import List, Optional, Dict, Any
import numpy as np
import uuid

COLLECTION_NAME = "memories"
VECTOR_SIZE = 384

class QdrantVectorStore:
    def __init__(self, path: str = "./qdrant_data"):
        self.client = QdrantClient(path=path)
        self._ensure_collection()
    
    def _ensure_collection(self):
        if not self.client.collection_exists(COLLECTION_NAME):
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE
                ),
                quantization_config=ScalarQuantizationConfig(
                    type=ScalarQuantizationType.INT8,
                    quantile=0.99,
                    always_ram=True
                ),
                hnsw_config=HnswConfigDiff(m=16, ef_construct=100)
            )
    
    def upsert(self, texts: List[str], embeddings: np.ndarray, 
               payloads: List[Dict[str, Any]]) -> List[str]:
        """Upsert batch. Returns point IDs."""
        points = []
        ids = []
        for text, emb, payload in zip(texts, embeddings, payloads):
            pid = str(uuid.uuid4())
            ids.append(pid)
            points.append(PointStruct(
                id=pid,
                vector=emb.tolist(),
                payload={"text": text, **payload}
            ))
        self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        return ids
    
    def search(self, query_embedding: np.ndarray, limit: int = 10,
               filter: Optional[Filter] = None) -> List[Dict]:
        """Return list of {id, score, payload}."""
        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding.tolist(),
            limit=limit,
            query_filter=filter,
            with_payload=True
        )
        return [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ]
    
    def count(self) -> int:
        return self.client.count(COLLECTION_NAME).count
```

### 3. Ingestion Script (`scripts/ingest.py`)

```python
#!/usr/bin/env python3
"""
Ingest text file into vector memory.
Usage: python scripts/ingest.py --file data/sample.txt --chunk-size 500 --overlap 50
"""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Simple sliding window chunking."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to text file")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--source", default="manual_ingest")
    args = parser.parse_args()
    
    text = Path(args.file).read_text(encoding="utf-8")
    chunks = chunk_text(text, args.chunk_size, args.overlap)
    print(f"Created {len(chunks)} chunks")
    
    embedder = Embedder()
    store = QdrantVectorStore()
    
    embeddings = embedder.embed(chunks)
    payloads = [{"source": args.source, "chunk_index": i} for i in range(len(chunks))]
    ids = store.upsert(chunks, embeddings, payloads)
    
    print(f"Upserted {len(ids)} vectors. Total in store: {store.count()}")

if __name__ == "__main__":
    main()
```

### 4. Retrieval Script (`scripts/retrieve.py`)

```python
#!/usr/bin/env python3
"""
Query vector memory.
Usage: python scripts/retrieve.py --query "what language do I use" --top-k 5
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()
    
    embedder = Embedder()
    store = QdrantVectorStore()
    
    q_emb = embedder.embed_single(args.query)
    results = store.search(q_emb, limit=args.top_k)
    
    print(f"\nQuery: {args.query}\n")
    for i, r in enumerate(results, 1):
        text = r["payload"].get("text", "")[:200]
        print(f"{i}. [score={r['score']:.4f}] {text}...")

if __name__ == "__main__":
    main()
```

### 5. Unit Tests (`tests/test_phase1_baseline.py`)

```python
import pytest
import numpy as np
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore

@pytest.fixture
def embedder():
    return Embedder()

@pytest.fixture
def store(tmp_path):
    return QdrantVectorStore(path=str(tmp_path / "qdrant_test"))

def test_embedding_dimension(embedder):
    emb = embedder.embed_single("test")
    assert emb.shape == (384,)
    assert emb.dtype == np.float32

def test_upsert_and_search(embedder, store):
    texts = ["I use Python for data science", "I prefer Rust for systems"]
    embeddings = embedder.embed(texts)
    payloads = [{"source": "test", "i": i} for i in range(len(texts))]
    
    ids = store.upsert(texts, embeddings, payloads)
    assert len(ids) == 2
    
    # Search for first text
    q_emb = embedder.embed_single("Python data science")
    results = store.search(q_emb, limit=2)
    
    assert len(results) == 2
    assert results[0]["score"] > results[1]["score"]  # First should match better
    assert "Python" in results[0]["payload"]["text"]

def test_filter_by_payload(embedder, store):
    texts = ["Project A uses Python", "Project B uses Go"]
    embeddings = embedder.embed(texts)
    payloads = [{"project": "A"}, {"project": "B"}]
    store.upsert(texts, embeddings, payloads)
    
    q_emb = embedder.embed_single("Python")
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    results = store.search(q_emb, limit=5, filter=Filter(
        must=[FieldCondition(key="project", match=MatchValue(value="A"))]
    ))
    assert all(r["payload"]["project"] == "A" for r in results)
```

---

## Expected Outcomes

| Metric | Target |
|--------|--------|
| Embedding latency (batch 32) | < 50ms |
| Upsert latency (batch 20) | < 30ms |
| Search latency (top-10) | < 15ms |
| Storage per 100K vectors | ~15 MB (INT8 quantized) |
| Recall@10 on test queries | > 0.85 |

---

## Verification Checklist

- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python scripts/ingest.py --file data/sample.txt` runs without error
- [ ] `python scripts/retrieve.py --query "test query"` returns results
- [ ] `pytest tests/test_phase1_baseline.py -v` all pass
- [ ] Qdrant data persisted to `./qdrant_data/`
- [ ] No Docker/server processes running (pure embedded mode)

---

## Next Phase Dependency

Phase 2 requires: Working vector store with payloads containing `source` and chunk metadata. The graph extractor will read from these payloads.