# System Diagnostic & Required Architecture Updates: Hybrid Retrieval Engine

**Document Status:** Actionable Implementation Plan & Technical Review  
**Date:** October 2026  
**Context:** Post-Benchmark Profiling (LoCoMo 400-query, LongMemEval 100-query, DMR runs)  
**Primary Finding:** Conceptual architecture is validated (dominating LoCoMo temporal and multi-hop retrieval), but fails operationally due to unconditional pipeline execution, unindexed $O(N)$ graph/payload scans, unpruned cross-encoder candidate pools, and baseline misconfiguration.

---

## Executive Summary & Diagnostic Verdict

Empirical profiling on real benchmark databases (`kuzu.db_locomo_hybrid.db`, `kuzu.db_longmemeval_hybrid.db`) reveals two stark truths:

1. **The Conceptual Architecture Delivers Major Accuracy Wins:**
   - **LoCoMo Recall@10:** **85.55%** (Hybrid) vs **66.48%** (Vector) and **72.95%** (Zep).
   - **LoCoMo Recall@1:** **55.14%** (Hybrid) vs **24.32%** (Vector) — *more than 2.2× higher precision*.
   - **LoCoMo MRR:** **0.6824** (Hybrid) vs **0.3908** (Vector) and **0.4620** (Zep).
   - **LoCoMo Temporal Recall:** **94.4%** vs **75.0%** (Vector).
   - **LoCoMo Multi-Hop Recall:** **63.9%** vs **46.8%** (Vector).
   - **LongMemEval Multi-Session Recall:** **38.89%** vs **32.00%** (Zep).

2. **The Operational Pipeline Fails from Unconditional Execution & $O(N)$ Implementation Bottlenecks:**
   - **Latency Explosion:** Competitors execute in **3.8 ms – 15.6 ms**, while Hybrid takes **3,117 ms** (LoCoMo), **12,748 ms** (LongMemEval), and **75,242 ms** (DMR).
   - **DMR Degradation:** While DMR Recall@10 increased, MRR dropped from 0.079 to 0.068 because unconditional graph expansion and contrastive retrieval inject irrelevant semantic distractors.
   - **LongMemEval Single-Session Loss:** Hybrid loses to Zep on single-session recall (0.2857 vs 0.4000) because vector search alone suffices; graph expansion adds noise.
   - **Baseline Validity Issue:** In several runs, `Mem0`, `MemPalace`, and `Vector` produced identical scores, indicating competitor fallback modes were active in the evaluation harness.

---

## Empirical Latency Breakdown (The 12.7s Problem)

Profiling on `data/benchmark_runs_competitors/kuzu.db_longmemeval_hybrid.db` identified the exact breakdown of a single query:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ HYBRID PIPELINE STAGE                       MEASURED TIME     BOTTLENECK    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Entity Linking / Matching                 15.06 ms         In-memory     │
│ 2. Qdrant Temporal Vector Search (100)      380.44 ms         Unindexed scan│
│ 3. Graph Expansion Fallback               7,170.82 ms (!!!)   8x Kùzu scans │
│ 4. Contrastive Offset Search (210)            7.02 ms         Vector ANN    │
│ 5. Contradiction & Supersession Checks      727.88 ms         300+ Cypher Qs│
│ 6. Cross-Encoder Rerank (50 candidates)     502.72 ms         Neural model  │
├─────────────────────────────────────────────────────────────────────────────┤
│ TOTAL LATENCY                              8,803.94 ms – 12,748.77 ms       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Action Items & Technical Updates Required

### Phase 1: Immediate Latency & Engine Hotfixes (Target: < 250 ms)

#### 1. Kill the Unindexed Kùzu Token-Scan Fallback
* **Location:** [`memory/retrieval/hybrid.py:L204-L240`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/hybrid.py#L204-L240)
* **Problem:** If a query contains no matched entity seeds, the code extracts 8 tokens and runs:
  ```cypher
  MATCH (o:Observation) WHERE lower(o.content) CONTAINS '$token' RETURN ...
  ```
  In Kùzu, this triggers 8 serial full-table substring scans across all observation rows (over 7,500 nodes in LongMemEval), consuming **7.1+ seconds**.
* **Action:**
  - Delete the 8-token `CONTAINS` fallback completely.
  - If `seed_entities` is empty, immediately return `[]` from `_graph_expansion()`.
  - Rely on vector candidates to provide candidate entity IDs.

#### 2. Batch Contradiction & Supersession Resolution
* **Location:** [`memory/retrieval/hybrid.py:L346-L375`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/hybrid.py#L346-L375) and [`memory/graph/kuzu_store.py:L760-L772`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/graph/kuzu_store.py#L760-L772)
* **Problem:** Hybrid loops over all 100+ candidates and executes two Cypher queries per candidate (`get_contradictions` and `get_supersessions`). Due to ID formatting mismatches (`obs_{mem_id}_{entity_id}` vs `{mem_id}`), `_resolve_obs_id()` falls back to `WHERE o.id CONTAINS $id`, issuing **over 200 full scans per search**.
* **Action:**
  - Fix observation ID assignment at ingestion: ensure a direct 1:1 mapping between `memory_id` and observation ID, or maintain an in-memory dictionary.
  - **Do not run contradiction checks on all 100 candidates.** Run contradiction and supersession checks **only on the top 10–15 finalists** after reranking.
  - Replace the per-candidate loop with a single batched Cypher query:
    ```cypher
    MATCH (o:Observation)-[r:CONTRADICTS|SUPERSEDES]-(other:Observation)
    WHERE o.id IN $top_candidate_ids
    RETURN o.id, type(r), other.id, r.confidence
    ```

#### 3. In-Memory Temporal Post-Filtering (Bypass Local Qdrant Scan)
* **Location:** [`memory/retrieval/hybrid.py:L161-L177`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/hybrid.py#L161-L177)
* **Problem:** Embedded local Qdrant ignores payload indexes (`UserWarning: Payload indexes have no effect in the local Qdrant`). Passing `valid_from <= t <= valid_until` range filters forces a brute-force payload filter across all collection points (**380–1,060 ms**).
* **Action:**
  - Execute Qdrant vector search **without** range filters using pure HNSW vector ANN (~3–5 ms).
  - Apply the temporal interval filter `valid_from <= query_time <= valid_until` directly in Python RAM on the returned candidate payloads (< 0.05 ms).

#### 4. Prune and Batch the Neural Cross-Encoder
* **Location:** [`memory/retrieval/hybrid.py:L94-L96`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/hybrid.py#L94-L96) and [`memory/ranking/reranker.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/ranking/reranker.py)
* **Problem:** Feeding 50 long conversational candidates (each 500–1,000 tokens) into `BAAI/bge-reranker-base` takes **500–700 ms** and pushes the RTX 4050 GPU near its 6.1 GB VRAM limit (5.8 GB active), inducing CUDA paging risks.
* **Action:**
  - Compute a lightweight pre-ranking score in Python (vector cosine similarity + recency decay + importance bonus + graph overlap).
  - Truncate the cross-encoder candidate pool from 50 down to **top 12–15**.
  - Truncate text pairs to a maximum of 256 tokens before inference.
  - Enforce cross-encoder batching (`batch_size=16`).

---

### Phase 2: Architectural Evolution — Adaptive Query Router

**Core Research Insight:**  
The hybrid engine should not be an unconditional monolithic pipeline. LoCoMo proves the graph and temporal layers excel at multi-hop and temporal state changes; DMR and LongMemEval prove they add noise to simple factual lookups and distractor-heavy tasks.

#### Implement Query Intent Routing
Create an explicit, low-latency heuristic/intent classifier at the retrieval entrance ([`memory/retrieval/hybrid.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/hybrid.py)):

```
                               ┌─► Simple Factual: Vector (k=20) ─► Rerank Top 10 (<20 ms)
                               │
Query ──► Adaptive Intent Router ─► Temporal (Current/Past): Vector + In-Memory Time Filter + Graph 1-Hop
                               │
                               ├─► Multi-Hop: Vector (k=50) + Graph 2-Hop + RRF Fusion
                               │
                               └─► Contradiction: Vector + Contrastive (Offset) + Contradiction Edges
```

* **Routing Rules:**
  1. **Simple Factual** (no temporal adverbs, single entity, high vector confidence):
     - Bypass graph expansion and contrastive retrieval completely.
     - Expected latency: **< 20 ms**.
  2. **Temporal Query** (`currently`, `now`, `before`, `used to`, explicit dates):
     - Apply point-in-time in-memory filter.
     - Perform 1-hop graph expansion for state updates.
  3. **Multi-Hop / Associative** (`connected to`, `project dependencies`, multiple query entities):
     - Perform bounded 2-hop graph expansion (cap neighbors at top 10 by edge confidence).
  4. **Distraction-Heavy / Noisy Context** (DMR style):
     - Set contrastive ratio to 0.0 (prevents injecting intentional hard negatives into already noisy environments).

---

### Phase 3: Evaluation Harness & Baseline Integrity

#### 1. Baseline Orthogonality Audit
* **Location:** [`memory/retrieval/competitors.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/competitors.py) and [`scripts/run_competitor_benchmarks.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/scripts/run_competitor_benchmarks.py)
* **Problem:** In several benchmark runs, `Mem0`, `MemPalace`, and `Vector` produced identical metrics.
* **Action:**
  - Verify that each competitor class is instantiated with separate state and that its specific retrieval logic (e.g., Mem0 graph joins, MemPalace room clustering) is actively participating in ranking rather than defaulting to vector order.
  - If an architecture lacks distinct implementation on a benchmark, explicitly document it or isolate it.

#### 2. Metric Rectification: Retrieval vs. Generation
* **Problem:** Answer generation evaluation reported Token F1 $\approx 0.01$ and Exact Match $= 0.0$ across all architectures, offering no discriminative signal for paper claims.
* **Action:**
  - Focus claims strictly on **Formal Information Retrieval Metrics**: Recall@k, Precision@k, MRR, and NDCG@k.
  - For generative evaluation, decouple retrieval benchmarking from downstream generation, and use an LLM-as-judge protocol (e.g., NIM Llama-3-70B judging correctness on gold answer keys).

---

## Latency Target Budget (Post-Optimization)

| Mode / Scenario | Current Latency | Target Latency | Key Reason for Improvement |
| :--- | :---: | :---: | :--- |
| **Simple Routed Query** | 3,117 ms | **< 20 ms** | Pure HNSW vector + 10-candidate rerank (0 DB scans) |
| **Temporal Query** | 3,500 ms | **35 – 50 ms** | In-memory time filter + 1-hop primary key graph join |
| **Multi-Hop Complex (LoCoMo)** | 5,720 ms | **60 – 110 ms** | Bounded 2-hop graph + pre-ranked cross-encoder |
| **Distraction Benchmark (DMR)** | 75,240 ms | **< 25 ms** | Elimination of 8x `CONTAINS` scans & zero contrastive noise |

---

## File Modification Checklist

- [ ] [`memory/retrieval/hybrid.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/retrieval/hybrid.py):
  - Remove observation token substring scan in `_graph_expansion()`.
  - Shift temporal filtering from Qdrant query to Python in-memory post-filtering.
  - Move contradiction / supersession checks to top-10 finalists only.
  - Implement `AdaptiveQueryRouter` with intent classification.
- [ ] [`memory/graph/kuzu_store.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/graph/kuzu_store.py):
  - Optimize `_resolve_obs_id` to remove `CONTAINS` scans.
  - Add batched `get_contradictions_batch(ids)` and `get_supersessions_batch(ids)`.
- [ ] [`memory/ranking/reranker.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/memory/ranking/reranker.py):
  - Cap candidates to 15 max.
  - Enforce text truncation to 256 tokens and batch size 16.
- [ ] [`scripts/run_competitor_benchmarks.py`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/scripts/run_competitor_benchmarks.py):
  - Validate competitor execution paths and log per-stage latency telemetry (`retrieval_trace`).
- [ ] [`docs/implementation_audit.md`](file:///c:/Users/vvars/OneDrive/Desktop/reserchpaper/docs/implementation_audit.md):
  - Update architecture documentation to reflect Conditional Hybrid Retrieval.
