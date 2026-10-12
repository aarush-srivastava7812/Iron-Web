# Hybrid Long-Term AI Memory Architecture — Plan
Iron Web: Vector Memory + Temporal Knowledge Graph + Contrastive Retrieval + Reranking

Status: Draft v4 (v1: generic tri-store stack; v2: aligned to research design; v3: Qdrant local mode + swappable extractor; v4: Ollama dropped, NIM is the sole extractor, reranker moved to FastEmbed's ONNX cross-encoder — no PyTorch, no local LLM, no GPU dependency in the stack)
Scope: single-machine research prototype, evaluated via baselines + ablations, not a production service.

---

## 1. Research Statement

**Question**: Can a hybrid memory architecture — semantic vector retrieval + contrastive candidate retrieval + temporal knowledge graph + graph-based evidence expansion + reranking — improve long-term contextual retrieval over vector-only memory?

**Hypothesis**: Combining semantic similarity with structural relationships, temporal validity, and contrastive evidence produces more accurate, contextually relevant retrieval than similarity search alone.

**What this plan is not claiming**: that the 1/10 contrastive ratio is optimal, or that graph expansion always helps. Both are experimental variables (see §8).

---

## 2. Core Design Principle

No single retrieval signal is trusted alone. Vector similarity, graph relevance, temporal validity, and contradiction status are combined at rerank time:

```
FinalScore = α·SemanticSimilarity + β·GraphRelevance + γ·Recency
           + δ·Importance + ε·EntityMatch + ζ·RelationshipStrength
           + η·HistoricalRelevance − θ·ContradictionPenalty
```

Weights are fit/tuned experimentally, not hardcoded.

---

## 3. Dual Memory Representation

Every ingested memory produces two artifacts:

```
Memory
  ├── Vector form  → embedding → vector store        (semantic meaning)
  └── Graph form   → entities + relations → graph DB (structural meaning)
```

### Memory object schema

```python
class Memory(BaseModel):
    id: str
    raw_text: str
    normalized_text: str
    embedding: list[float]

    entities: list[str]
    relationships: list[Relation]

    timestamp: datetime
    valid_from: datetime
    valid_until: datetime | None

    confidence: float          # 0-1, extraction confidence
    importance: float          # 0-1, decay resistance (1.0 = no decay)
    source: str
    memory_type: str           # fact | preference | context | summary

    graph_node_id: str | None
```

```python
class Relation(BaseModel):
    source: str
    relation_type: str   # USES, PREFERS, LEARNING, WORKS_ON, DEPENDS_ON,
                          # USED_FOR, RELATED_TO, PART_OF,
                          # CONTRADICTS, SUPERSEDES
    target: str
    confidence: float
    valid_from: datetime
    valid_until: datetime | None
    source_memory_id: str
```

---

## 4. Ingestion Pipeline

```
Raw input
  → preprocessing
  → embedding generation            (fastembed, CPU)
  → entity extraction               (NVIDIA NIM, hosted LLM)
  → relationship extraction         (NVIDIA NIM, hosted LLM)
  → temporal analysis               (valid_from/valid_until assignment)
  → contradiction detection         (compare against existing graph edges)
  → vector store upsert
  → graph store upsert
```

Extraction runs against NVIDIA NIM (OpenAI-compatible endpoint) — no local model:

```python
def get_extractor(model: str = "meta/llama-3.1-70b-instruct"):
    return NIMExtractor(model=model, api_key=os.environ["NVIDIA_API_KEY"])
```

This is the only extractor path — no local LLM. Keep it swappable by `model` name (e.g. drop to a smaller NIM-hosted model) if latency/cost on the free tier becomes an issue during heavy ingestion runs, but the client/base_url stays fixed.

Extraction prompt (single call, structured JSON out):

```
Extract from this input:
1. ENTITIES: named things (people, tools, languages, projects)
2. RELATIONSHIPS: entity1 -[TYPE]-> entity2, with confidence
3. TEMPORAL: does this state a current fact, a past fact, or a change/transition?
4. CONTRADICTS: does this conflict with a plausible prior memory about the same entity?

Output JSON only. No prose.
```

If a new relationship conflicts with an existing edge on the same (source, relation_type) pair:
- If it reads as a state transition ("switched to", "instead of", "started using") → create `SUPERSEDES` edge, set old edge's `valid_until` = now.
- If it reads as a genuine contradiction (no transition language) → create `CONTRADICTS` edge, keep both, let reranking / the LLM surface the tension rather than silently resolving it.

---

## 5. Retrieval Pipeline

```
User query
  → query embedding
  → VECTOR SEARCH
       ├── positive candidates   (top-N by cosine similarity)
       └── contrastive candidates (next N/k by similarity — see §8)
  → candidate pool (positive + contrastive)
  → IRON WEB LAYER
       ├── graph expansion (1-2 hop traversal from matched entities)
       ├── temporal filtering (is this edge valid at query time / "now"?)
       └── contradiction/supersession resolution
  → reranking (§2 formula)
  → top-K context assembly
  → LLM
```

```python
def retrieve(query: str, k: int = 10, contrastive_ratio: float = 0.1) -> list[Memory]:
    q_emb = embed(query)

    positive = vector_store.search(q_emb, limit=100)
    contrastive = vector_store.search(
        q_emb, limit=int(100 * contrastive_ratio), offset=100
    )
    pool = positive + contrastive

    expanded = graph.expand(pool, hops=2)          # Iron Web layer
    resolved = graph.resolve_temporal(expanded)     # drop/flag superseded edges
    ranked = rerank(resolved, query)                # cross-encoder + formula in §2

    return ranked[:k]
```

Context handed to the LLM is structured, not a raw dump:

```
Current: <highest-ranked current-state memory>
Historical: <superseded memory, if relevant to the query>
Relation: "<X> superseded <Y> on <date>"
```

---

## 6. Maintenance (background, not per-query)

```
duplicate detection → stale-memory detection → importance/confidence
adjustment → contradiction re-check → relationship cleanup →
consolidation
```

- **Decay**: `importance = 1.0` → no decay (hard fact). Below that, decay as a function of age, retrieval frequency, and confirmation count — not time alone.
- **Consolidation**: cluster near-duplicate memories (high cosine sim + same entities) into one canonical memory, keep source references, don't delete originals outright.
- **Cadence**: run as a manual/cron script, not a live scheduler — this is a research prototype, not a service.

---

## 7. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Vector store | Qdrant, local embedded mode (`QdrantClient(path="./qdrant_data")`) | No server/Docker (same embedded deployment as Chroma would've been); native payload filtering on `importance`, `valid_from`/`valid_until`, `memory_type`, `entities` fits the schema in §3 better than metadata-filtered Chroma; scalar quantization available if the memory count grows |
| Graph store | Kuzu (`pip install kuzu`) | Embedded, Cypher, vector+FTS built in, no JVM/server. Note: upstream archived Oct 2025 post-acquisition; last release (0.11.3) still installs and is stable for single-user use |
| Embeddings | FastEmbed (ONNX, `bge-small-en-v1.5`) | CPU-only, no GPU dependency anywhere in the stack now |
| Entity/relation extraction | NVIDIA NIM (OpenAI-compatible endpoint, hosted) | No local model — free/dev-tier NIM API key, no Ollama install or VRAM budget to manage |
| Reranker | `bge-reranker-base` via FastEmbed's `TextCrossEncoder` (ONNX, no PyTorch) | Candidate pool is ~110 items; stays on the same CPU/ONNX runtime as the embedder — no extra ML framework added |
| Orchestration | Plain composable Python functions, config-flag per stage | Ablations (§8) need stages toggled by a config bool, not a graph edit |
| Logging/observability | Structured JSON logs + local eval script | No external SaaS dependency for a local research run |

Everything above runs in-process on one laptop except extraction, which is now the one component with a live network dependency — see §12.

---

## 8. Evaluation Methodology

### Baselines (build in this order, keep each runnable)

| ID | Pipeline |
|---|---|
| A | Vector-only: query → vector search → top-K |
| B | Vector + reranker |
| C | Vector + graph expansion (no contrastive) |
| D | Vector + contrastive retrieval (no graph) |
| Full | Vector + contrastive + graph + temporal + reranking |

### Ablations
Remove one component at a time from the full system: graph, contrastive retrieval, temporal reasoning, reranking. Measure delta.

### Contrastive ratio sweep
Test 0%, 5%, 10%, 20%, 50% contrastive candidates. Don't assume 1/10 is correct — this is doc 2's stated open hypothesis, treat it as such.

### Metrics
- Retrieval: Recall@K, Precision@K, MRR, NDCG
- Answer quality: accuracy, context relevance, faithfulness (LLM-as-judge or manual)
- Efficiency: latency, token usage, storage overhead

### Test scenarios (build a small hand-labeled set covering these)
1. Simple retrieval ("what language do I use for DSA")
2. Historical retrieval ("what did I use previously")
3. Current-state retrieval ("what am I using now")
4. Contradiction ("didn't I say I use C++")
5. Multi-hop ("what tech am I using in my current project")
6. Related-memory expansion

---

## 9. Module Layout

```
memory/
    ingestion/          # extraction, embedding calls
    embeddings/          # fastembed wrapper
    vector_store/        # qdrant wrapper (local embedded mode)
    graph/               # kuzu wrapper, schema, traversal
    retrieval/
        vector.py         # baseline A
        hybrid.py         # full pipeline
    ranking/             # reranker + scoring formula
    temporal/            # valid_from/until logic, supersession
    contradiction/       # CONTRADICTS/SUPERSEDES detection
    maintenance/         # decay, dedup, consolidation
    evaluation/          # baselines, ablation runner, metrics
```

---

## 10. Phased Implementation

| Phase | Deliverable |
|---|---|
| 1 | Reproduce baseline A (embedding → Qdrant local mode → top-K) end to end |
| 2 | Add graph representation: entity/relation extraction → Kuzu schema |
| 3 | Hybrid retrieval: vector → graph → reranker (baseline C) |
| 4 | Contrastive retrieval added (baseline D, then full = C+D) |
| 5 | Temporal fields (valid_from/valid_until) |
| 6 | Contradiction/supersession detection and resolution |
| 7 | Maintenance: decay, dedup, consolidation |
| 8 | Evaluation harness: baselines A–D + full, hand-labeled scenario set |
| 9 | Ablation study (remove graph / contrastive / temporal independently) |
| 10 | Contrastive ratio sweep + weight tuning for rerank formula |
| 11 | Write-up: results table, failure case analysis |

---

## 11. Dev Tooling (Forge)

- `forge.yaml`: scope the agent's file/shell access to `memory/` only.
- Register an MCP server exposing "query Kuzu graph" / "query Qdrant collection" as tools, so the agent can inspect live DB state while debugging graph expansion instead of you re-pasting query output.
- Let Forge's built-in workspace semantic search index the repo once `memory/` has real code.
- Keep Aider on hand for isolated single-file refactors where git-native diff review is preferable to agentic edits.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Extraction errors (wrong entity/relation) | Confidence threshold + manual spot-check on eval set |
| Graph growth / traversal cost | Cap hop count at 2; measure latency in eval harness |
| Contradiction vs. context-shift ambiguity | Bias toward SUPERSEDES when transition language present; leave CONTRADICTS otherwise for LLM to reason over |
| Kuzu upstream archived | Pin the version (0.11.3); low risk for single-user, non-concurrent use |
| No local extraction fallback (Ollama dropped) | Every ingestion and eval run now depends on NIM API availability/rate limits; cache raw extraction responses to disk so re-runs of downstream stages (graph build, rerank tuning) don't re-hit the API |