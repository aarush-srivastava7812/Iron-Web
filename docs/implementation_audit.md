# Conditional Hybrid Retrieval Audit

Date: 2026-10-10

## Implemented latency changes

- Removed Kuzu observation-content token scanning when no graph seed exists.
- Runs embedded-Qdrant searches without payload range filters; temporal intervals are filtered in memory.
- Added deterministic routing: simple, temporal, multi-hop, and contradiction.
- Limits graph traversal to routed requests, at most 10 seed entities, 10 expanded entities, and 30 observations.
- Pre-ranks candidates and caps cross-encoder work at 15 candidates, 256 words each, batch size 16.
- Resolves contradictions/supersessions only for finalists with two constant-size batched Kuzu queries.
- When no accelerator provider is available, skips the cross-encoder and retains deterministic pre-ranking. GPU-enabled runs retain cross-encoder inference.

## Measured retrieval-only profile

All measurements use the existing 272-document LoCoMo Hybrid store and CPU ONNX runtime. First-query model/database warm-up is excluded from steady-state assessment.

| Route | Warm query latency | Notes |
|---|---:|---|
| Simple factual | 97.9-108.0 ms | Graph, contrastive, conflict, and CPU reranker bypassed. |
| Temporal | 209.6-230.7 ms | Bounded graph expansion plus batched conflict check. |
| Associative router path | 178.2 ms | Vector 81.8 ms + graph 96.4 ms, no CPU reranker. |

These historical CPU measurements meet the immediate `<250 ms` target for the measured simple and temporal routes by bypassing the unavailable CPU cross-encoder. They are retained as a fallback reference; the verified GPU results below are the active quality-first configuration.

## Verified RTX 4050 execution

The workstation's RTX 4050 (6,141 MB VRAM) is now the default neural-inference path. The clean Python environment contains `fastembed-gpu`, `onnxruntime-gpu 1.19.2`, CUDA 12 runtime, cuDNN 9, and cuFFT. The Windows DLL loader retains the required DLL directory handles for the process lifetime, including the CUDA runtime and cuFFT directories.

An actual FastEmbed ONNX session reported `CUDAExecutionProvider` and GPU memory rose from 1,025 MB to 1,041 MB during a 512-text embedding workload. This is execution evidence, rather than merely detecting a CUDA-capable runtime. The device-status API now inspects the live ONNX session provider rather than the requested provider list.

| Route | GPU warm query latency | Main staged work |
|---|---:|---|
| Simple factual | 204.5-215.4 ms | Vector ~5 ms, GPU cross-encoder ~199 ms. |
| Temporal | 265.6-287.0 ms | Vector ~5 ms, graph ~43 ms, GPU cross-encoder ~197 ms, conflict lookup ~41 ms. |

The GPU reranker restores cross-encoder quality while removing the former ~10.57 s CPU reranking cost. It is deliberately slower than the CPU *bypass* profile because that profile skipped cross-encoder reranking altogether; it should not be presented as a like-for-like quality comparison. Model/database first-use warm-up remains about 3.3-3.5 s and is excluded from steady-state latency.

After removing a discarded Kuzu traversal and avoiding unused relation materialization for Hybrid retrieval, the temporal query retained the same top result and measured **232.3-236.9 ms warm**. Its graph stage fell from approximately 43 ms to 9.5 ms. The GPU cross-encoder remains the dominant steady-state cost (~192 ms).

Two additional reversible optimizations are enabled by default:

- `entity_lookup_cache`: Kuzu retains the entity id/name index in-process and invalidates it on entity upsert, entity deletion, and orphan cleanup. This removes repeated full entity-table scans without returning stale names after normal writes.
- `batched_conflict_resolution`: Kuzu resolves all candidate observation IDs in one query before issuing the two relationship queries. The original per-ID resolver remains available when this setting is `false`, and is automatically used if the batched query fails.

On the same temporal query, batched conflict resolution reduced the conflict stage from roughly 22.7 ms to **1.9 ms**, and the best warmed total was **219.5 ms**. The top result and score remained unchanged. Set either switch to `false` under `retrieval` in `config.yaml` to roll back independently.

## TensorRT trial

The reranker requests providers in TensorRT → CUDA → CPU order and records the **live** ONNX session providers, so an unavailable TensorRT runtime cannot be misreported as enabled and automatically continues on the verified CUDA path.

The direct TensorRT runtime packages (`tensorrt-cu12-libs` and `tensorrt-cu12-bindings` 10.2.0.post1) are installed. Windows DLL registration includes the wheel's `tensorrt_libs` directory, and a live reranker session reports `TensorrtExecutionProvider`.

| Route | CUDA warm baseline | TensorRT warm | Change |
|---|---:|---:|---:|
| Simple factual | 204.5-215.4 ms | **163.3 ms** | ~20-24% lower |
| Temporal | 219.5 ms | **166.7 ms** | ~24% lower |

The 15-document reranker stage is 152-159 ms in the integrated workload (CUDA: ~192-199 ms). A controlled 15-document ranking check produced identical document order under CUDA and TensorRT; score values vary slightly due to the optimized execution plan.

TensorRT engine and timing caching is enabled at `data/tensorrt_cache`. The initial build produced a device-specific 1.11 GB engine; new processes load the cached engine but still take roughly 12 seconds to initialize it. Keep the `MemoryEngine` process warm for normal service latency. Delete this cache before changing the reranker model, ONNX Runtime/TensorRT version, or GPU. Set `reranker.prefer_tensorrt: false` to roll back instantly to CUDA.

## Baseline integrity audit

No competitor implementation was changed. A read-only execution audit confirmed Vector, Zep, Mem0, MemPalace, and Hybrid dispatch through separate retrievers. Zep returned a different order. Mem0 and MemPalace returned the same top-10 IDs as Vector for the audited LoCoMo query. This is a baseline-validity limitation: the current 272-document LoCoMo Qdrant store has `timestamp = 0` for every document, so MemPalace collapses all documents into its fallback temporal room; Mem0's graph additions did not alter the top 10 for that query. These are internal architecture-inspired retrievers sharing the same Qdrant corpus, not installed upstream Mem0, Zep, or MemPalace products. Do not claim their metrics demonstrate distinct behavior until benchmark timestamp mapping and broader trace auditing are addressed.

## Verification

- `pytest tests/test_kuzu_counts.py tests/test_benchmark_harness.py -q`: 7 passed.
- Direct two-observation probe confirmed `get_relationship_conflicts_batch()` returns a real `CONTRADICTS` edge.
- Existing `test_kuzu_counts.py` protects directed edge counts from the earlier double-count regression.
