# FalkorDB retrieval and latency assessment

Date: 13 October 2026. Application revision: `a0769cae47ab8262184c94b97dc50a61dbaf06e5`.

## Comparison

The retained DMR 5% cohort contains 25 questions and 125 documents. The saved graph was imported into an isolated FalkorDB namespace with exact property verification. Kùzu used its implementation from commit `6d10601` on a copied file. Both backends used the same copied Qdrant store, current retrieval code, warmed real BGE embedding model, CUDA provider and query settings within one process. Five measured rounds followed a discarded warm-up round. Backend order rotated between rounds. Model loading, import, ingestion and generation were outside the retrieval timing.

| Measurement | Kùzu | FalkorDB |
| --- | ---: | ---: |
| Recall@10 | 16% | 16% |
| Mean search latency | 26.72 ms | 35.88 ms |
| Median search latency | 26.14 ms | 34.72 ms |
| 95th percentile search latency | 32.14 ms | 42.93 ms |
| Timed searches | 125 | 125 |

All returned IDs and their ordering matched each other and the saved historical results. Results remained identical in every measured round. FalkorDB averaged 34.3% more latency in this confirmation run. A separate initial run measured 27.68 ms for Kùzu and 34.37 ms for FalkorDB, also with identical rankings.

This is one small, warm, single-client cohort. The graph has 125 observations but no entities or relationship edges because extraction was disabled. It tests service overhead and conflict checks, not the quality or latency of substantial graph expansion. It does not establish results for other datasets, concurrent use, writes, cold startup or larger graphs.

## Observed calls

An untimed command-count pass found nine Redis commands per FalkorDB search: one lock acquisition, four GET operations, three graph queries and one lease-release script. Three graph queries include the complete observation ownership inventory and two conflict-edge queries. The current engine already holds one graph lease across the whole search. Adding another surrounding lease retained the same command count and changed mean latency by less than 1%; it is not a useful optimization.

The application already reuses its FalkorDB client connection pool and has native identifier indexes. Reintroducing connections or merely adding another index is not supported as a solution by this profile.

## Prioritized efficiency changes

1. **Read several entities together.** Graph expansion currently calls `get_entity` once for each seed. On an isolated exact copy of the active graph, ten individual entity reads averaged 32.42 ms, while one equivalent bounded query averaged 6.65 ms: 79.5% lower latency for this lookup step. All seven returned properties matched exactly. Fifty randomized-order measurements per strategy used the same full-operation lease. This is an experimental measurement; the production traversal has not been changed. Preserve input order, node limits, missing-ID behavior and temporal traversal when implementing it.
2. **Avoid rereading the whole ownership inventory for every search.** Cache ownership/conflict data against the existing shared graph revision, or query only candidate-owned observations using the existing ID and source-memory indexes. A valid cache must refresh after any cooperating-client mutation, publication or rollback, and retain legacy ownership matching and conflict direction/time. For graphs with no conflict edges, a revision-aware empty-conflict shortcut could avoid the three repeated reads. This benefit has not been measured end to end.
3. **Batch independent service calls.** Evaluate pipelining independent read requests and lease checks to reduce round trips. Preserve lease-loss rejection and snapshot consistency; dependent traversal queries cannot simply be submitted together. Use explicit `GRAPH.RO_QUERY` for read operations where appropriate. It prevents accidental writes and supports replica routing, but it is not evidence of a single-client latency improvement by itself.
4. **Measure coordinated write cost separately.** Each coordinated write copies the graph for rollback protection. This is proportional to graph size and was not timed by this retrieval comparison. Replacing that mechanism requires a separate recovery design and failure tests; removing it solely for speed would change the current guarantee.

No production storage or retrieval code was modified during this assessment. Only the isolated comparison script and evidence were added. Temporary FalkorDB benchmark graphs were removed, original graph files remained unchanged, and the active application graph was not used for writes.

## Reproduction and evidence

Run `python scripts/compare_graph_latency.py --report report/my_graph_latency --rounds 5` with FalkorDB running, the optional legacy migration dependency installed, the retained evaluation stores present, and the recorded CUDA runtime available. The script uses randomized temporary namespaces and copied local stores. It intentionally loads the legacy module only for the comparison.

- [Confirmed metrics, command counts and lookup experiment](../falkordb_latency_20261013_confirm/comparison.json)
- [Confirmed returned IDs](../falkordb_latency_20261013_confirm/retrieved_ids.json)
- [Confirmed model/runtime checks](../falkordb_latency_20261013_confirm/preflight.json)
- [Initial comparison](comparison.json)
- [Comparison script](../../scripts/compare_graph_latency.py)

Official references: [Redis pipelining](https://redis.io/docs/latest/develop/using-commands/pipelining/), [FalkorDB read-only queries](https://docs.falkordb.com/commands/graph.ro-query), and [FalkorDB profiling](https://docs.falkordb.com/commands/graph.profile).
