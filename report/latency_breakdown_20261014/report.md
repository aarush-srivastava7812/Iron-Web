# Iron Web latency attribution report

Analysis date: 14 October 2026. All times below are measured wall-clock milliseconds.

## Scope and interpretation

The measured application is the optimized FalkorDB revision used in the previous 20% report. The isolated source comes from commit `2035c7ece628d777aed0a184ffe73865a59acf2e`; its application fingerprint is `52bbfef0133a427a72d1a0f5e1fb6b7433888d4bb69329c90915b6678c15afc6`. Newer uncommitted application changes are outside this analysis.

All 597 retained questions were repeated in vector, default hybrid, and reranked hybrid modes: 1,791 measured retrieval requests. DMR has 100 questions and 500 documents; LoCoMo has 397 questions and 70 documents; LongMemEval has 100 questions and 4,612 documents. Each profile uses three warm-up queries before the timed pass. Twenty additional documents were written to a private copy of each complete corpus, giving 60 write probes. Those probes measure writes to an existing corpus; they do not repeat or replace the earlier full fresh-ingestion measurements.

BAAI/bge-small-en-v1.5 generates embeddings locally on CUDA. BAAI/bge-reranker-base reranks locally on CUDA with batch size 16. Qdrant is embedded in the Python application. FalkorDB runs in Docker on this computer, reached through TCP at the loopback address. Entity extraction is disabled, as in the prior benchmark. These corpora contain observations but no extracted entities or graph edges; graph traversal workload is therefore absent. Model loading and graph import are excluded from request times. External answer generation and remote embedding APIs are also absent.

## Retrieval: where the time goes

The following components are exclusive: a nested database call is subtracted from its parent. Each row sums to the measured request mean. Other time includes validation, merging and scoring, formatting, Python lock management, and measurement overhead. P95 is the time at or below which 95% of this pass's requests completed; it is not a confidence bound.

| Dataset | Mode | Total | Embed | Vector | Rerank | Redis | Other | P95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dmr | vector | 12.50 | 5.48 | 2.45 | 0.00 | 3.50 | 1.07 | 16.69 |
| dmr | default hybrid | 20.85 | 6.11 | 6.34 | 0.00 | 6.21 | 2.19 | 24.02 |
| dmr | reranked hybrid | 2474.98 | 4.67 | 7.52 | 2443.74 | 16.60 | 2.45 | 2566.63 |
| locomo | vector | 14.74 | 6.96 | 2.94 | 0.00 | 3.64 | 1.20 | 19.11 |
| locomo | default hybrid | 20.18 | 8.43 | 3.68 | 0.00 | 6.41 | 1.66 | 24.94 |
| locomo | reranked hybrid | 402.44 | 5.52 | 3.39 | 384.22 | 7.56 | 1.74 | 586.53 |
| longmemeval | vector | 87.71 | 11.40 | 71.69 | 0.00 | 3.44 | 1.18 | 96.58 |
| longmemeval | default hybrid | 93.26 | 11.31 | 74.18 | 0.00 | 5.99 | 1.79 | 100.81 |
| longmemeval | reranked hybrid | 1028.14 | 5.27 | 74.59 | 935.80 | 10.49 | 1.99 | 1118.68 |

Reranking includes preparing and tokenizing candidate texts, neural inference, and sorting the scores. Embedding includes text preparation and neural inference. These measurements do not split GPU kernel execution from CPU preparation. Vector search includes local candidate filtering and result construction.

For dmr, reranking accounts for 98.7% of average request time. The reranker scores 100 to 100 candidates per query.

For locomo, reranking accounts for 95.5% of average request time. The reranker scores 19 to 32 candidates per query.

For longmemeval, reranking accounts for 91.0% of average request time. The reranker scores 38 to 56 candidates per query.

## Network and database commands

The PING measurements below are 100 consecutive warm pooled round trips after ten discarded warm-up calls. They include Python client work, TCP transport through Docker, Redis dispatch and response handling. They are a round-trip reference, not a direct measurement of pure network transmission time. No packet capture or separate client/server clock measurements were used.

| Dataset phase | PING mean | PING P95 |
| --- | --- | --- |
| dmr | 1.102 | 1.413 |
| locomo | 1.082 | 1.291 |
| longmemeval | 1.186 | 1.477 |

Warm vector requests issue two Redis commands: SET to acquire the lease and EVALSHA to release it. Warm default and reranked hybrid requests issue four: those two plus two GET calls for cache revisions. The full warm passes issue no GRAPH.QUERY commands because the empty entity lookup and conflict lookup are cached. Thus the Redis column in the retrieval table mainly represents lock/cache round trips, not graph traversal.

The graph SDK reports internal server execution time for GRAPH.QUERY. The table below uses queries observed during write probes. Client command wall time minus server execution includes transport, dispatch/queueing outside the reported interval, argument encoding, Redis protocol parsing and client scheduling. It must not be labeled pure network latency. Graph SDK result decoding after the Redis response is separately included in Other.

| Dataset | Queries/write | Client/query | Server/query | Remaining/query |
| --- | --- | --- | --- | --- |
| dmr | 6.0 | 2.536 | 0.815 | 1.722 |
| locomo | 6.0 | 2.161 | 0.662 | 1.499 |
| longmemeval | 6.0 | 5.763 | 2.808 | 2.955 |

## Writes: copying the graph

Every coordinated write starts by copying the complete graph to a private staging graph, applies graph changes and the vector update, then publishes the graph using a Redis script and removes the recovery copy. The copy column is the entire GRAPH.COPY command wait; server copy work and transport are not separated. The complete command time is counted once. Transaction/retry time covers staging/publication bookkeeping and retry waits, excluding the command waits already shown. Other includes recovery-copy deletion, vector snapshot reads, SDK decoding, serialization and Python execution.

| Dataset | Total | Embed | Vector write | Graph copy | Graph queries | Redis | Txn/retry | Other |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dmr | 200.68 | 17.46 | 14.37 | 121.31 | 15.14 | 24.79 | 2.90 | 4.71 |
| locomo | 96.45 | 10.16 | 8.81 | 41.41 | 12.90 | 19.12 | 0.33 | 3.72 |
| longmemeval | 1743.61 | 28.55 | 16.65 | 1342.62 | 34.49 | 48.80 | 268.09 | 4.41 |

For dmr, graph copy accounts for 60.5% of average write time. There were 1 additional copy command attempts across 20 successful writes.

For locomo, graph copy accounts for 42.9% of average write time. There were 0 additional copy command attempts across 20 successful writes.

For longmemeval, graph copy accounts for 77.0% of average write time. There were 106 additional copy command attempts across 20 successful writes.

LongMemEval had 106 recovered GRAPH.COPY failures across 20 writes. The retry path requests a 50 ms pause per failed attempt: 5.30 seconds in total, or 265 ms per write, derived from the attempt count. The complete measured transaction/retry component is 268.09 ms per write. This waiting is separate from the 1,342.62 ms spent inside successful and failed copy commands.

| Dataset | Successful copy time/write | Failed copy time/write | Recovered failures |
| --- | --- | --- | --- |
| dmr | 118.52 | 2.82 | 1 |
| locomo | 41.43 | 0.00 | 0 |
| longmemeval | 1052.10 | 290.67 | 106 |

All 60 write probes succeeded and their stored text was read back exactly. Original benchmark input files and canonical graph files retained their SHA-256 hashes. Only this run's graph namespaces were removed after measurement.

## Concurrent prompts and waiting

The engine serializes operations through one graph lease and a local mutex. Multiple submitted requests therefore wait for earlier requests, including their embedding and reranking work. The measurements below use the whole DMR or LongMemEval question cohort in default hybrid mode with four or eight workers sharing one engine. Local lock wait is measured separately and is already included in total latency. This is client-side waiting, not a server network round trip.

| Dataset | Workers | Mean total | Mean local wait | P95 total | Requests/s |
| --- | --- | --- | --- | --- | --- |
| dmr | 4 | 77.38 | 57.76 | 87.96 | 50.69 |
| dmr | 8 | 183.67 | 159.85 | 212.42 | 41.77 |
| longmemeval | 4 | 380.09 | 283.71 | 404.54 | 10.36 |
| longmemeval | 8 | 713.61 | 621.29 | 757.37 | 10.82 |

## Cold caches

Ten queries per dataset were run after invalidating both graph lookup caches. These are measured separately and do not enter the warm-cohort means. Cache refresh scans observation ownership and conflict relationships; this matters after writes or cache invalidation.

| Dataset | Warm hybrid mean | Cold hybrid mean | Cold graph command time |
| --- | --- | --- | --- |
| dmr | 20.85 | 44.18 | 16.46 |
| locomo | 20.18 | 27.92 | 7.83 |
| longmemeval | 93.26 | 214.06 | 94.08 |

## Accuracy and comparison with previous timings

Every returned ID and its order, every predicted answer, and all 17 local quality metrics matched the previous optimized FalkorDB result for the same dataset and profile. The 153 dataset/profile/metric rows are saved in accuracy.csv. Metrics include recall, precision and nDCG at 1/3/5/10, MRR, average precision at 10, exact match, substring match and token F1. LoCoMo has 395 retrieval-scored and 328 answer-scored examples. Answer scoring uses the same first-context-line generator, not an external language model.

This run adds instrumentation; it does not apply an optimization. Differences between its total timings and the previous report are fresh measurement differences, not a measured improvement caused by a code change. GPU clocks/temperature, CPU scheduling, Docker load and persistence activity were not controlled.

| Dataset | Mode | Previous mean | This mean |
| --- | --- | --- | --- |
| dmr | vector | 14.59 | 12.50 |
| dmr | default hybrid | 27.95 | 20.85 |
| dmr | reranked hybrid | 2356.74 | 2474.98 |
| locomo | vector | 14.87 | 14.74 |
| locomo | default hybrid | 20.72 | 20.18 |
| locomo | reranked hybrid | 415.73 | 402.44 |
| longmemeval | vector | 114.71 | 87.71 |
| longmemeval | default hybrid | 121.90 | 93.26 |
| longmemeval | reranked hybrid | 2212.27 | 1028.14 |

## Measurement sensitivity

Twenty default-hybrid queries per dataset were each repeated with active timers and disabled timers, alternating their order. Instrumentation wrappers remain installed in both cases. The paired mean difference describes timer sensitivity under changing runtime conditions; it is not an exact estimate of all instrumentation overhead.

## Observed interruption

The initial LoCoMo reranked pass recorded 393 successful requests before a Redis socket read timed out during EVALSHA, the lease-release command. The configured socket timeout is 10 seconds; the complete failed request duration was not saved. The partial pass is retained in locomo_reranked_hybrid.partial_attempt_1.jsonl and is excluded from the completed-pass averages. The full LoCoMo reranked cohort was subsequently repeated with the same application settings. Already completed cohorts were reused.

Redis responded to PING after the interruption and the container reported healthy. Persistence logs showed a completed background save, but available timing evidence does not establish it as the cause of the timeout. No service configuration was changed or service restarted. One observed failure does not establish a general failure rate. The completed-pass P95 values do not include this failed attempt; they cannot describe the full failure tail.

| Dataset | Active timers mean | Disabled timers mean | Paired mean difference |
| --- | --- | --- | --- |
| dmr | 20.266 | 19.911 | 0.355 |
| locomo | 14.380 | 15.144 | -0.764 |
| longmemeval | 85.536 | 85.344 | 0.192 |

## Priorities supported by the measurements

1. For ingestion, reduce the need to copy the entire graph for each document. This would require a change to the coordinated-write design while preserving its rollback behavior; it has not been applied or validated here.

2. For reranked retrieval, investigate scoring fewer candidate documents or batching model work. Candidate reduction can change answer quality and requires the same quality checks.

3. For large-corpus retrieval, investigate the embedded vector search cost. A server-backed indexed vector store could change that cost, but its latency and quality have not been measured in this report.

4. For simultaneous prompts, investigate read concurrency while maintaining consistency. The current lock covers the whole request, so extra callers mainly accumulate waiting time.

5. Reduce sequential Redis lock/cache checks where equivalent ownership and freshness checks can be preserved. Fewer round trips could help short requests; the measured network reference does not establish the improvement of any untested change.

## Reproduction and evidence

Run `.venv/Scripts/python.exe scripts/profile_latency_breakdown.py --run-id NEW_RUN_ID --writes 20`, then `.venv/Scripts/python.exe scripts/build_latency_breakdown_report.py report/NEW_RUN_ID`. Use a new run ID: completed probe stores have additional documents, and their temporary graphs are cleaned up. The retained canonical stores, the pinned Git commit, model caches, optional Kuzu dependency and running FalkorDB service are required.

Evidence: state.json contains configuration and aggregates; the nine retrieval JSONL files contain exclusive timings and command counts for every request. The three write JSONL files contain all 60 probe timings. Cold-cache and concurrent JSON files contain their individual samples. components.csv, latency.csv, commands.csv and accuracy.csv provide tabular exports. preflight.json verifies actual CUDA model providers.
