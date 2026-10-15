# FalkorDB Versus Qdrant: Vector Latency and Output Quality

Labels: wayfinder:task
Type: task
Status: resolved
Assignee: Codex
Parent: [Shared Agent Memory: Hackathon, Research and Reuse](../map.md)
Blocked by: 01, 12

## Question

Produce a controlled comparison of the existing FalkorDB graph plus Qdrant vectors against the same graph with FalkorDB's native indexed vector search. What does each deliver on latency and output quality, using the user's 5% condition?

This is the first memory-core experiment. Its results unblock [Vector Placement Within the Existing Architecture](07-reusable-core-and-storage-boundary.md); later graph additions follow that choice. It does not change the production backend or adopt another memory framework.

Use [Vector Comparison Plan](../vector-comparison-plan.md) for the matched inputs, workloads, scoring, measurement boundaries and required evidence. Preserve the existing implementation as the baseline. The task resolves only when the comparison and its limitations are recorded; adding this ticket does not run the experiment.

## Comments

### 2026-10-13 — Meaning of 5% awaiting clarification

The user specified “both latency and output metrics at 5%” without defining whether this means a tolerance, statistical significance, or a data sample. A clarification has been requested. The experiment plan currently proposes a **5% relative tolerance against Qdrant**, clearly marked provisional. It does not silently treat this as an agreed significance level, five percentage points, or permission to test only 5% of the data.

## Completion evidence

- Versions/settings, identical memory and question sets, reference answers, workload sizes and reproducible run instructions.
- Vector-search and complete-retrieval latency, including typical and slower responses under single-agent and concurrent read/write workloads.
- Retrieval completeness, relevance and ranking; current-versus-obsolete evidence; unavailable-answer behavior. Report final-answer correctness separately when an answer-producing flow exists.
- Measured ingestion-to-search visibility and failures under the mixed workload, without conflating a saved event with searchable interpreted memory.
- Results table with the agreed 5% rule applied to every predeclared primary metric, uncertainty and limitations. No winner claimed from an inconclusive result.
- Isolated test data only; the current graph, vector data, running service and other work remain intact.

## Execution log

### 2026-10-13 — Applying the plan

The user instructed “start applying the plan.” Claimed this first core task before implementation. Build and run an isolated native-FalkorDB-vector versus current-Qdrant comparison. The 5% interpretation remains provisional; gather measurements without selecting a backend from an unconfirmed threshold. Production memory placement is unchanged until the placement decision.

## Answer

The first vector-placement experiment is implemented and run. The current MemoryEngine was tested with its local Qdrant store and an isolated native-FalkorDB-vector adapter, using the retained **5% slices** of DMR, LoCoMo and LongMemEval. There are 149 distinct questions, 147 with reference-evidence labels, and 1,357 stored memories across the three separate cohorts. Each scored run has five rounds per backend and per retrieval path. A second run pairs each question's two backend calls and alternates their order to reduce temporal drift.

In the paired confirmation, both placements returned the same ordered evidence on all 149 questions. Evidence recall/relevance/ranking scores were unchanged. Typical complete retrieval took Qdrant/FalkorDB respectively **40.06/48.97 ms** for DMR, **31.90/39.17 ms** for LoCoMo, and **49.04/83.34 ms** for LongMemEval. Both typical and slow-response native results exceeded the proposed 5% latency allowance in these cohorts. The tolerance interpretation remains unconfirmed; this is an illustrative gate, not a user-approved storage decision. The data itself uses the actual existing 5% evaluation slices.

All 24 mixed-workload writes were found in their first post-commit visibility check, and concurrent read/write traces recorded no errors. Those workloads are descriptive, not a statistically repeated concurrency gate. The engine's ingestion remains synchronous; this experiment does not create a background receipt/interpretation service.

Six real-database contract tests passed, including score conversion, filter completeness, payload/vector parity and rollback through the existing ingestion facade. Ten hand-authored graph controls preserved current/historical filtering, explicit conflict/change edges, scoped retrieval and both budget versions. These controls build real graph relationships, unlike the retained default-extraction corpora, whose entity counts are zero. A missing-phone-number control returned related notes in both variants; it establishes the need for a later answerability check, not a hallucinated generated answer.

Keep the current production placement intact. The results do not justify moving vectors in this tested configuration; [Vector Placement Within the Existing Architecture](07-reusable-core-and-storage-boundary.md) now has the measured evidence for its decision. A final placement policy, larger untouched quality set, representative multi-process/user loads, memory/storage costs and comparable crash durability remain outside this first experiment's claims.

### Evidence

- [Confirmed paired report](../../../report/vector_placement_20261013_p5_paired/REPORT.md)
- [Measured comparison and intervals](../../../report/vector_placement_20261013_p5_paired/comparison.json)
- [Frozen raw timings and retrieved IDs](../../../report/vector_placement_20261013_p5_paired/raw.json)
- [Versions, source fingerprints and execution settings](../../../report/vector_placement_20261013_p5_paired/manifest.json)
- [Graph-rich control results](../../../report/vector_placement_20261013_controls/results.json)
- [First grouped run](../../../report/vector_placement_20261013_p5/comparison.json)
- [Benchmark runner](../../../scripts/benchmark_vector_placement.py), [experiment-only adapter](../../../scripts/vector_placement/falkor_vector.py), and [real-database contract checks](../../../tests/test_vector_placement_experiment.py)

Raw measurements and original analyses are retained. Derived analysis was corrected to distinguish absent reference annotations from absent answers; failed queries remain zero-score observations, and intervals wholly outside the provisional tolerance are labelled failures. See the [analysis revision](../../../report/vector_placement_20261013_p5_paired/analysis_revision.json). Original evaluation stores and application source/configuration remained unchanged during both runs. All graphs created by these benchmark/control runs were removed; local copied runtime stores are ignored by Git.
