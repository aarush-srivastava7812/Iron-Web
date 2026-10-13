# Twenty percent graph storage analysis

This report compares the embedded Kùzu graph backend, the initial FalkorDB migration, and optimized FalkorDB on retained 20% question cohorts. It measures fresh ingestion through the public memory API and retrieval from identical complete corpora. The comparisons isolate the graph backend while keeping retrieval code, vectors, models and scoring settings consistent.

## Measured findings

The full matrix contains 5,373 measured queries across 27 dataset/profile/backend combinations. Returned rankings, predictions, and all 17 local retrieval/answer metrics matched across graph backends for each profile.

| Dataset | Kùzu ingestion seconds | Optimized ingestion seconds | Ingestion time ratio | Hybrid latency change |
| --- | --- | --- | --- | --- |
| DMR | 26.84 | 85.67 | 3.19 times | -29.82% |
| LoCoMo | 4.52 | 9.43 | 2.09 times | -24.66% |
| LongMemEval | 340.41 | 4,868.14 | 14.30 times | -31.40% |

Optimized warm hybrid retrieval had lower mean latency than the Kùzu reference in all three cohorts. Vector-only and reranked retrieval were not universally faster. Fresh ingestion took longer, and the alternating write/search workload also took longer with the current FalkorDB graph-copy design. These results support different conclusions for stable-corpus retrieval and frequent memory updates.

The initial migration failed fresh-ingestion tests during Redis background persistence. The bounded copy-startup retry allowed optimized ingestion to complete every cohort. These are integration-version results; the same cache/batching changes were not applied to the Kùzu reference.

## Scope and method

| Dataset | Questions | Complete history documents | Text characters |
| --- | --- | --- | --- |
| DMR | 100 | 500 | 734,473 |
| LoCoMo | 397 | 70 | 202,711 |
| LongMemEval | 100 | 4,612 | 47,155,239 |

Twenty percent refers to the retained question cohort. Each selected question retains its complete history; the number of documents is not restricted to 20% of sessions. Missing document/query timestamps use one recorded run timestamp. Source-supplied timestamps are preserved.

Application revision: `8fe090b0b9202aee84967e8aeefe5767fade05fe`. Embedded graph implementation: `6d10601`. Initial FalkorDB implementation: `a0769ca`. Source fingerprint: `52bbfef0133a427a72d1a0f5e1fb6b7433888d4bb69329c90915b6678c15afc6`.

The measured retrieval profiles are vector search, hybrid search without reranking, and hybrid search with reranking. Retrieval returns at most ten memories; the vector candidate ceiling is 100, graph expansion uses two hops and at most 50 nodes, and hosted entity extraction is disabled. Dataset graphs therefore contain observations without extracted entities or relationship edges. A separate synthetic graph experiment covers nonempty graph expansion and relationship conflicts.

Both neural models are real models using the recorded CUDA provider: BAAI/bge-small-en-v1.5 for 384-dimensional embeddings and BAAI/bge-reranker-base for reranking. Model load/check time is separate from ingestion and query timings. The answer generator returns the first context line; no hosted answer model or official upstream LLM judge is used. Answer scores describe this local generator.

Fresh ingestion uses batches of 20 with per-record storage commits. Successful `add` latency includes embedding and coordinated vector/graph writes within the batch. Full ingestion time also includes existence checks and batch preparation. A failed ingestion does not have a full-corpus throughput or completion time. Retrieval corpora are populated from a canonical full graph/vector snapshot, separately from measured fresh-ingestion success or failure.

## Fresh ingestion time and throughput

| Dataset | Backend | Result | Completed | Total time seconds | Documents per second |
| --- | --- | --- | --- | --- | --- |
| DMR | Kùzu | complete | 500/500 | 26.84 | 18.63 |
| DMR | FalkorDB before optimization | failed | 218/500 | Partial 27.29 | Not available |
| DMR | FalkorDB optimized | complete | 500/500 | 85.67 | 5.84 |
| LoCoMo | Kùzu | complete | 70/70 | 4.52 | 15.50 |
| LoCoMo | FalkorDB before optimization | failed | 60/70 | Partial 7.04 | Not available |
| LoCoMo | FalkorDB optimized | complete | 70/70 | 9.43 | 7.42 |
| LongMemEval | Kùzu | complete | 4612/4612 | 340.41 | 13.55 |
| LongMemEval | FalkorDB before optimization | failed | 56/4612 | Partial 11.16 | Not available |
| LongMemEval | FalkorDB optimized | complete | 4612/4612 | 4,868.14 | 0.95 |

For a failed run, the reported partial elapsed time is the time until the error. It is not comparable to the successful completion time. Only successful additions are included in the partial add-latency distribution below.

| Dataset | Backend | Mean add ms | Median add ms | P95 add ms | P99 add ms |
| --- | --- | --- | --- | --- | --- |
| DMR | Kùzu | 51.05 | 51.75 | 60.07 | 65.37 |
| DMR | FalkorDB before optimization | 116.43 | 102.54 | 203.96 | Not available |
| DMR | FalkorDB optimized | 163.21 | 195.53 | 212.80 | 350.65 |
| LoCoMo | Kùzu | 59.63 | 59.39 | 72.99 | 79.18 |
| LoCoMo | FalkorDB before optimization | 106.09 | 102.38 | 132.44 | Not available |
| LoCoMo | FalkorDB optimized | 126.55 | 105.97 | 204.86 | 298.79 |
| LongMemEval | Kùzu | 69.57 | 68.43 | 82.59 | 99.96 |
| LongMemEval | FalkorDB before optimization | 187.31 | 203.99 | 217.05 | Not available |
| LongMemEval | FalkorDB optimized | 1,044.31 | 886.83 | 2,310.40 | 2,920.83 |

The initial FalkorDB integration can encounter `GRAPH.COPY failed, could not fork` during Redis background persistence. Optimized integration retries only that explicit pre-copy error within the configured timeout, while requiring an absent destination and an owned lease. It does not retry ambiguous transport failures. Graph copying for every coordinated write remains part of the implementation.

## Retrieval latency and time differences

Negative changes below indicate lower optimized latency. Percentages compare the means of the same dataset/profile; ingestion and retrieval timings have different units and scopes.

| Dataset | Profile | Kùzu mean ms | FalkorDB before ms | FalkorDB optimized ms | Change vs Kùzu | Change vs before |
| --- | --- | --- | --- | --- | --- | --- |
| DMR | Vector | 11.46 | 14.13 | 14.59 | +27.34% | +3.23% |
| DMR | Hybrid without reranking | 39.84 | 54.27 | 27.95 | -29.82% | -48.49% |
| DMR | Hybrid with reranking | 1,730.61 | 1,943.89 | 2,356.74 | +36.18% | +21.24% |
| LoCoMo | Vector | 9.11 | 15.47 | 14.87 | +63.20% | -3.90% |
| LoCoMo | Hybrid without reranking | 27.50 | 33.03 | 20.72 | -24.66% | -37.26% |
| LoCoMo | Hybrid with reranking | 414.97 | 432.51 | 415.73 | +0.18% | -3.88% |
| LongMemEval | Vector | 101.11 | 118.99 | 114.71 | +13.45% | -3.59% |
| LongMemEval | Hybrid without reranking | 177.70 | 337.72 | 121.90 | -31.40% | -63.91% |
| LongMemEval | Hybrid with reranking | 1,152.98 | 1,480.72 | 2,212.27 | +91.87% | +49.40% |

### DMR Vector

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 11.46 | 10.72 | 15.31 | 17.03 | 17.25 | 84.23 |
| FalkorDB before optimization | 14.13 | 13.72 | 16.55 | 16.91 | 21.06 | 68.74 |
| FalkorDB optimized | 14.59 | 14.34 | 16.85 | 18.10 | 20.73 | 66.23 |

### DMR Hybrid without reranking

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 39.84 | 39.49 | 46.96 | 49.46 | 50.86 | 24.80 |
| FalkorDB before optimization | 54.27 | 52.69 | 56.92 | 127.29 | 130.49 | 18.29 |
| FalkorDB optimized | 27.95 | 27.80 | 30.49 | 35.38 | 37.31 | 35.24 |

### DMR Hybrid with reranking

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 1,730.61 | 1,740.94 | 1,768.20 | 1,779.84 | 1,781.09 | 0.58 |
| FalkorDB before optimization | 1,943.89 | 1,779.84 | 2,454.36 | 2,568.68 | 2,774.24 | 0.51 |
| FalkorDB optimized | 2,356.74 | 2,366.53 | 2,399.26 | 2,421.73 | 2,422.13 | 0.42 |

### LoCoMo Vector

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 9.11 | 8.84 | 12.02 | 13.78 | 15.00 | 104.38 |
| FalkorDB before optimization | 15.47 | 15.13 | 19.96 | 23.29 | 26.62 | 62.69 |
| FalkorDB optimized | 14.87 | 14.59 | 18.37 | 19.74 | 24.23 | 65.18 |

### LoCoMo Hybrid without reranking

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 27.50 | 27.18 | 35.40 | 38.74 | 43.33 | 35.75 |
| FalkorDB before optimization | 33.03 | 32.77 | 37.12 | 40.46 | 110.78 | 29.85 |
| FalkorDB optimized | 20.72 | 20.17 | 24.83 | 37.32 | 44.10 | 47.16 |

### LoCoMo Hybrid with reranking

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 414.97 | 356.56 | 605.73 | 677.80 | 927.64 | 2.41 |
| FalkorDB before optimization | 432.51 | 375.33 | 633.54 | 719.86 | 994.09 | 2.31 |
| FalkorDB optimized | 415.73 | 357.55 | 601.11 | 637.23 | 664.78 | 2.40 |

### LongMemEval Vector

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 101.11 | 82.16 | 203.66 | 289.88 | 292.82 | 9.83 |
| FalkorDB before optimization | 118.99 | 115.29 | 135.65 | 171.81 | 330.12 | 8.36 |
| FalkorDB optimized | 114.71 | 118.95 | 138.63 | 153.08 | 223.24 | 8.67 |

### LongMemEval Hybrid without reranking

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 177.70 | 173.80 | 211.40 | 266.85 | 310.99 | 5.61 |
| FalkorDB before optimization | 337.72 | 319.35 | 419.79 | 441.29 | 453.20 | 2.96 |
| FalkorDB optimized | 121.90 | 119.57 | 140.88 | 169.59 | 219.91 | 8.16 |

### LongMemEval Hybrid with reranking

| Backend | Mean ms | Median ms | P95 ms | P99 ms | Maximum ms | Requests per second |
| --- | --- | --- | --- | --- | --- | --- |
| Kùzu | 1,152.98 | 1,133.91 | 1,324.79 | 1,513.16 | 1,896.56 | 0.87 |
| FalkorDB before optimization | 1,480.72 | 1,372.14 | 2,130.28 | 2,413.89 | 2,551.44 | 0.68 |
| FalkorDB optimized | 2,212.27 | 2,166.21 | 2,899.54 | 3,020.12 | 3,470.52 | 0.45 |

Mean total latency is retrieval plus first-line generation. Throughput uses the full evaluation-loop elapsed time, which also includes scoring and raw-result recording. The complete total/generation latency columns are in `all_latency_metrics.csv`. Each full matrix profile measures the whole selected cohort after three warm-up examples, with one measured pass. Separate repeated default-hybrid tests are reported in the supporting evidence. Small timing differences are not confidence intervals or proof of a general performance advantage.

## All retrieval and answer metrics

Every returned ID, ranking and predicted answer matched the Kùzu reference for each profile. All retrieval and answer metric differences between backends are zero. The following tables show the common value shared by all three backends; the CSV preserves a separate row for every backend/metric. Metrics range from zero to one.

### DMR quality metrics

Selected questions: 100. Retrieval-scored questions: 100. Answer-scored questions: 100. Questions lacking annotated retrieval evidence or a nonempty answer are excluded from the corresponding quality average, while remaining included in latency measurements.

| Metric | Vector | Hybrid | Reranked hybrid | Backend difference |
| --- | --- | --- | --- | --- |
| recall@1 | 0.030000 | 0.030000 | 0.000000 | 0 |
| recall@3 | 0.030000 | 0.030000 | 0.040000 | 0 |
| recall@5 | 0.060000 | 0.060000 | 0.090000 | 0 |
| recall@10 | 0.090000 | 0.090000 | 0.140000 | 0 |
| precision@1 | 0.030000 | 0.030000 | 0.000000 | 0 |
| precision@3 | 0.010000 | 0.010000 | 0.013333 | 0 |
| precision@5 | 0.012000 | 0.012000 | 0.018000 | 0 |
| precision@10 | 0.009000 | 0.009000 | 0.014000 | 0 |
| mrr | 0.041429 | 0.041429 | 0.031583 | 0 |
| ndcg@1 | 0.030000 | 0.030000 | 0.000000 | 0 |
| ndcg@3 | 0.030000 | 0.030000 | 0.020000 | 0 |
| ndcg@5 | 0.042920 | 0.042920 | 0.041096 | 0 |
| ndcg@10 | 0.052563 | 0.052563 | 0.056843 | 0 |
| average_precision@10 | 0.041429 | 0.041429 | 0.031583 | 0 |
| exact_match | 0.000000 | 0.000000 | 0.000000 | 0 |
| substring_match | 0.030000 | 0.030000 | 0.000000 | 0 |
| token_f1 | 0.045182 | 0.045182 | 0.033770 | 0 |

### LoCoMo quality metrics

Selected questions: 397. Retrieval-scored questions: 395. Answer-scored questions: 328. Questions lacking annotated retrieval evidence or a nonempty answer are excluded from the corresponding quality average, while remaining included in latency measurements.

| Metric | Vector | Hybrid | Reranked hybrid | Backend difference |
| --- | --- | --- | --- | --- |
| recall@1 | 0.299367 | 0.299367 | 0.572363 | 0 |
| recall@3 | 0.499367 | 0.499367 | 0.732996 | 0 |
| recall@5 | 0.616034 | 0.616034 | 0.787215 | 0 |
| recall@10 | 0.785401 | 0.785401 | 0.896160 | 0 |
| precision@1 | 0.336709 | 0.336709 | 0.622785 | 0 |
| precision@3 | 0.194937 | 0.194937 | 0.277637 | 0 |
| precision@5 | 0.147848 | 0.147848 | 0.183797 | 0 |
| precision@10 | 0.097215 | 0.097215 | 0.108608 | 0 |
| mrr | 0.477159 | 0.477159 | 0.717436 | 0 |
| ndcg@1 | 0.336709 | 0.336709 | 0.622785 | 0 |
| ndcg@3 | 0.427282 | 0.427282 | 0.682795 | 0 |
| ndcg@5 | 0.476912 | 0.476912 | 0.706395 | 0 |
| ndcg@10 | 0.536184 | 0.536184 | 0.745584 | 0 |
| average_precision@10 | 0.444039 | 0.444039 | 0.684417 | 0 |
| exact_match | 0.000000 | 0.000000 | 0.000000 | 0 |
| substring_match | 0.015244 | 0.015244 | 0.012195 | 0 |
| token_f1 | 0.022964 | 0.022964 | 0.020280 | 0 |

### LongMemEval quality metrics

Selected questions: 100. Retrieval-scored questions: 100. Answer-scored questions: 100. Questions lacking annotated retrieval evidence or a nonempty answer are excluded from the corresponding quality average, while remaining included in latency measurements.

| Metric | Vector | Hybrid | Reranked hybrid | Backend difference |
| --- | --- | --- | --- | --- |
| recall@1 | 0.464833 | 0.474833 | 0.476500 | 0 |
| recall@3 | 0.739500 | 0.746167 | 0.750333 | 0 |
| recall@5 | 0.843833 | 0.833833 | 0.851333 | 0 |
| recall@10 | 0.940000 | 0.936667 | 0.945500 | 0 |
| precision@1 | 0.650000 | 0.660000 | 0.660000 | 0 |
| precision@3 | 0.403333 | 0.403333 | 0.420000 | 0 |
| precision@5 | 0.292000 | 0.290000 | 0.300000 | 0 |
| precision@10 | 0.161000 | 0.160000 | 0.163000 | 0 |
| mrr | 0.752401 | 0.752397 | 0.756234 | 0 |
| ndcg@1 | 0.650000 | 0.660000 | 0.660000 | 0 |
| ndcg@3 | 0.717007 | 0.721428 | 0.731668 | 0 |
| ndcg@5 | 0.751566 | 0.749018 | 0.765141 | 0 |
| ndcg@10 | 0.786547 | 0.785891 | 0.798222 | 0 |
| average_precision@10 | 0.726968 | 0.727464 | 0.744764 | 0 |
| exact_match | 0.000000 | 0.000000 | 0.000000 | 0 |
| substring_match | 0.080000 | 0.080000 | 0.100000 | 0 |
| token_f1 | 0.024277 | 0.025818 | 0.025311 | 0 |

Recall measures the fraction of annotated relevant memories returned. Precision divides unique relevant hits by the cutoff even when fewer results are returned. MRR measures the reciprocal rank of the first relevant result. NDCG measures ranking quality with discounted gains. Average precision at ten divides accumulated hit precision by the full number of annotated relevant memories. Duplicate IDs consume ranks without earning extra credit.

Exact match compares normalized answers, substring match checks whether the normalized gold answer occurs within the normalized prediction, and token F1 uses token overlap. Case, punctuation, articles and whitespace follow the implemented normalization. Category-level recall, MRR and answer scores are in `category_metrics.csv`.

## Memory use and reliability

| Dataset | Profile | Backend | Peak process RSS MiB | Retrieval failures |
| --- | --- | --- | --- | --- |
| DMR | Vector | Kùzu | 1,375.8 | 0 |
| DMR | Vector | FalkorDB before optimization | 1,375.0 | 0 |
| DMR | Vector | FalkorDB optimized | 1,376.0 | 0 |
| DMR | Hybrid without reranking | Kùzu | 1,375.5 | 0 |
| DMR | Hybrid without reranking | FalkorDB before optimization | 1,376.6 | 0 |
| DMR | Hybrid without reranking | FalkorDB optimized | 1,376.6 | 0 |
| DMR | Hybrid with reranking | Kùzu | 1,423.5 | 0 |
| DMR | Hybrid with reranking | FalkorDB before optimization | 1,424.7 | 0 |
| DMR | Hybrid with reranking | FalkorDB optimized | 1,423.3 | 0 |
| LoCoMo | Vector | Kùzu | 1,423.2 | 0 |
| LoCoMo | Vector | FalkorDB before optimization | 1,423.3 | 0 |
| LoCoMo | Vector | FalkorDB optimized | 1,423.3 | 0 |
| LoCoMo | Hybrid without reranking | Kùzu | 1,425.9 | 0 |
| LoCoMo | Hybrid without reranking | FalkorDB before optimization | 1,425.9 | 0 |
| LoCoMo | Hybrid without reranking | FalkorDB optimized | 1,425.9 | 0 |
| LoCoMo | Hybrid with reranking | Kùzu | 1,479.9 | 0 |
| LoCoMo | Hybrid with reranking | FalkorDB before optimization | 1,482.0 | 0 |
| LoCoMo | Hybrid with reranking | FalkorDB optimized | 1,482.0 | 0 |
| LongMemEval | Vector | Kùzu | 856.6 | 0 |
| LongMemEval | Vector | FalkorDB before optimization | 856.7 | 0 |
| LongMemEval | Vector | FalkorDB optimized | 856.8 | 0 |
| LongMemEval | Hybrid without reranking | Kùzu | 860.7 | 0 |
| LongMemEval | Hybrid without reranking | FalkorDB before optimization | 869.6 | 0 |
| LongMemEval | Hybrid without reranking | FalkorDB optimized | 869.6 | 0 |
| LongMemEval | Hybrid with reranking | Kùzu | 1,140.7 | 0 |
| LongMemEval | Hybrid with reranking | FalkorDB before optimization | 1,147.9 | 0 |
| LongMemEval | Hybrid with reranking | FalkorDB optimized | 1,148.1 | 0 |

RSS includes the shared model host allocations and live storage objects. The measurements run in one process and are not isolated database footprints; they should not be added to or directly compared with server memory as if they represented equivalent components. Server and fresh-process storage memory measurements, when supplied, are separately identified. GPU provider/version and initial device memory are recorded in `preflight.json`.

## Concurrency and graph structure

The supporting 20% DMR concurrent test uses one shared engine with one, four and eight request workers. Its exact readings are linked below. A graph lease still serializes cooperating requests; higher worker counts can increase queue latency without increasing throughput proportionally. The optimization does not implement concurrent-reader access.

A separate synthetic graph has 500 entities, 1,500 observations, 499 RELATES, 1,500 ABOUT and 50 SUPERSEDES relationships. Batched traversal and cached conflicts are compared with the initial FalkorDB implementation, with exact result matching. These are structural microbenchmarks, not dataset retrieval-quality scores.

## Interpretation and limits

Revision-aware conflict caching avoids repeated ownership/relationship reads while the graph is unchanged. Seed batching reduces multiple entity queries to bounded batches. Writes invalidate the cache, so read-heavy and alternating write/search workloads have different costs. Full-graph copies remain a write-cost and scaling consideration.

The results apply to these complete-context cohorts, model settings, local machine and pinned service. They do not establish capacity for arbitrary larger graphs, distributed deployment or untested prompt concurrency. Graph-backed recall improvements require actual entity/relationship extraction; default extraction is disabled here. The local first-line answer scores do not represent an LLM answering the tasks.

Kùzu and FalkorDB use different storage/recovery designs. FalkorDB uses a persistent Redis service with append-only logging and one-second fsync; process-level compensation preserves caught-error recovery across the graph and vectors but does not provide cross-store crash atomicity. No durability guarantee was removed to improve the retrieval figures.

## Validation and reproduction

Optimization validation: 119 regression tests and four dataset checks passed. Tests exercise real FalkorDB with declared offline neural/provider fixtures, including seed ordering/limits, shared-client cache refresh, rollback invalidation, lost publication responses and bounded copy-retry behavior. Performance evaluations use the real GPU models.

Run `python scripts/full_graph_analysis.py --run-id NEW_RUN_ID --report report/NEW_REPORT` with FalkorDB running and the retained inputs and isolated CUDA runtime available. Install the optional profiling and migration dependencies for memory probes and legacy comparisons. The script saves normalized complete-context inputs and fingerprints, raw per-query results, per-add timings, model checks and resumable state. It rejects a changed application source on resume. Original historical stores and reports are read-only inputs.

## Evidence

- [Complete run state](state.json)
- [Validated summary](verified_summary.json)
- [All accuracy metrics](all_accuracy_metrics.csv)
- [All latency metrics](all_latency_metrics.csv)
- [Ingestion metrics](ingestion_metrics.csv)
- [Latency differences](latency_differences.csv)
- [Category metrics](category_metrics.csv)
- [Model and runtime checks](preflight.json)
- [Repeated hybrid and concurrency tests](../falkordb_optimization_20261013/comparison.json)
- [Graph structure and mixed workload tests](../falkordb_optimization_20261013/additional_workloads.json)

## Combined workload time

The following values add separately measured fresh ingestion time and the complete selected query-loop time. They exclude model loading and graph import/setup. They are derived sums, not a separate uninterrupted end-to-end test. Failed ingestions have no combined completion time.

| Dataset | Profile | Backend | Derived combined seconds |
| --- | --- | --- | --- |
| DMR | Vector | Kùzu | 28.03 |
| DMR | Vector | FalkorDB before optimization | Not available |
| DMR | Vector | FalkorDB optimized | 87.18 |
| DMR | Hybrid without reranking | Kùzu | 30.88 |
| DMR | Hybrid without reranking | FalkorDB before optimization | Not available |
| DMR | Hybrid without reranking | FalkorDB optimized | 88.51 |
| DMR | Hybrid with reranking | Kùzu | 199.95 |
| DMR | Hybrid with reranking | FalkorDB before optimization | Not available |
| DMR | Hybrid with reranking | FalkorDB optimized | 321.39 |
| LoCoMo | Vector | Kùzu | 8.32 |
| LoCoMo | Vector | FalkorDB before optimization | Not available |
| LoCoMo | Vector | FalkorDB optimized | 15.52 |
| LoCoMo | Hybrid without reranking | Kùzu | 15.62 |
| LoCoMo | Hybrid without reranking | FalkorDB before optimization | Not available |
| LoCoMo | Hybrid without reranking | FalkorDB optimized | 17.85 |
| LoCoMo | Hybrid with reranking | Kùzu | 169.45 |
| LoCoMo | Hybrid with reranking | FalkorDB before optimization | Not available |
| LoCoMo | Hybrid with reranking | FalkorDB optimized | 174.69 |
| LongMemEval | Vector | Kùzu | 350.59 |
| LongMemEval | Vector | FalkorDB before optimization | Not available |
| LongMemEval | Vector | FalkorDB optimized | 4,879.67 |
| LongMemEval | Hybrid without reranking | Kùzu | 358.25 |
| LongMemEval | Hybrid without reranking | FalkorDB before optimization | Not available |
| LongMemEval | Hybrid without reranking | FalkorDB optimized | 4,880.39 |
| LongMemEval | Hybrid with reranking | Kùzu | 455.77 |
| LongMemEval | Hybrid with reranking | FalkorDB before optimization | Not available |
| LongMemEval | Hybrid with reranking | FalkorDB optimized | 5,089.44 |

## Derived ingestion offset

If optimized ingestion takes longer but warm retrieval is faster, the extra ingestion time can be divided by the average time saved per query. This estimates how many queries to an unchanged corpus would offset the extra initial ingestion time. It assumes these measured means continue to hold, no further writes invalidate the cache, and no concurrency/queue changes occur. It is not a measured capacity guarantee. A missing value means no finite positive offset can be derived from the observed means.

| Dataset | Profile | Extra ingestion seconds | Seconds saved per query | Estimated queries |
| --- | --- | --- | --- | --- |
| DMR | Vector | 58.83 | -0.003132 | Not available |
| DMR | Hybrid without reranking | 58.83 | 0.011881 | 4,952 |
| DMR | Hybrid with reranking | 58.83 | -0.626124 | Not available |
| LoCoMo | Vector | 4.91 | -0.005757 | Not available |
| LoCoMo | Hybrid without reranking | 4.91 | 0.006782 | 725 |
| LoCoMo | Hybrid with reranking | 4.91 | -0.000759 | Not available |
| LongMemEval | Vector | 4,527.73 | -0.013599 | Not available |
| LongMemEval | Hybrid without reranking | 4,527.73 | 0.055806 | 81,134 |
| LongMemEval | Hybrid with reranking | 4,527.73 | -1.059286 | Not available |

The batching and cache changes were applied to the FalkorDB integration only. Equivalent optimizations were not applied to the Kùzu reference, so measured improvements cannot be attributed solely to the database engine.

## Fresh process storage memory

Each row runs in a separate Python process without loading neural model weights. It includes the graph client or embedded graph plus embedded Qdrant. The graph data for FalkorDB lives in a separate server process, so client RSS is not whole-system database memory. Redis MEMORY USAGE returned only 56 or 64 bytes for the module value; that does not measure the full graph allocation and is not used as a graph-RAM result.

| Dataset | Backend | Baseline RSS MiB | Warm RSS MiB | Increase MiB |
| --- | --- | --- | --- | --- |
| DMR | FalkorDB optimized | 114.6 | 138.4 | 23.8 |
| DMR | FalkorDB before optimization | 117.7 | 138.8 | 21.1 |
| DMR | Kùzu | 117.2 | 223.2 | 105.9 |
| LoCoMo | FalkorDB optimized | 114.4 | 128.1 | 13.7 |
| LoCoMo | FalkorDB before optimization | 117.1 | 128.2 | 11.1 |
| LoCoMo | Kùzu | 117.2 | 211.5 | 94.4 |
| LongMemEval | FalkorDB optimized | 114.6 | 281.9 | 167.3 |
| LongMemEval | FalkorDB before optimization | 117.8 | 282.6 | 164.8 |
| LongMemEval | Kùzu | 117.4 | 358.2 | 240.8 |

## Concurrent prompt measurements

These supporting runs each execute all 100 questions from the 20% DMR cohort through one shared engine. Latency includes application queue waits. Returned rankings matched the retained reference. These tests measure the current serialized engine rather than parallel native database capacity.

| Workers | Backend | Queries | Mean ms | P95 ms | Requests per second |
| --- | --- | --- | --- | --- | --- |
| 1 | Kùzu | 100 | 34.58 | 40.94 | 28.72 |
| 1 | FalkorDB before optimization | 100 | 47.51 | 52.34 | 20.94 |
| 1 | FalkorDB optimized | 100 | 24.66 | 29.22 | 40.13 |
| 4 | Kùzu | 100 | 121.41 | 143.79 | 32.25 |
| 4 | FalkorDB before optimization | 100 | 193.58 | 240.50 | 20.34 |
| 4 | FalkorDB optimized | 100 | 101.56 | 115.24 | 38.70 |
| 8 | Kùzu | 100 | 262.27 | 318.80 | 29.43 |
| 8 | FalkorDB before optimization | 100 | 379.09 | 449.27 | 20.28 |
| 8 | FalkorDB optimized | 100 | 178.44 | 241.18 | 43.14 |

## Graph structure measurements

| Operation | Before mean ms | Optimized mean ms | Change | Exact results |
| --- | --- | --- | --- | --- |
| expansion | 73.08 | 21.53 | -70.55% | True |
| conflicts | 55.70 | 5.40 | -90.31% | True |

## Alternating write and search measurements

This supporting test alternates a valid importance update and a search for each of 100 questions in the 20% DMR cohort. Each write invalidates the conflict cache. Failed runs retain only completed-step timing and are not full-workload completion results.

| Backend | Result | Steps | Write mean ms | Search mean ms | Combined mean ms |
| --- | --- | --- | --- | --- | --- |
| Kùzu | complete | 100 | 35.17 | 46.31 | 81.51 |
| FalkorDB before optimization | failed | 3 | 292.20 | 70.75 | 363.10 |
| FalkorDB optimized | complete | 100 | 288.05 | 62.83 | 350.93 |

## Recorded environment

| Item | Recorded value |
| --- | --- |
| python | 3.12.14 |
| operating_system | Windows-11-10.0.26200-SP0 |
| cpu | AMD64 Family 25 Model 117 Stepping 2, AuthenticAMD |
| logical_cpus | 12 |
| redis_version | 8.10.2 |
| falkordb_threads | 12 |
| falkordb_resultset_size | -1 |
| persistence | {'appendonly': 'yes'} |
| fsync | {'appendfsync': 'everysec'} |
| gpu | NVIDIA GeForce RTX 4050 Laptop GPU, 592.82, 6141 MiB |
| final_rerank_gpu_snapshot | {'stage': 'LongMemEval reranked hybrid optimized pass', 'utilization_percent': 100, 'clock_mhz': 2130, 'power_watts': 61.95, 'temperature_c': 86, 'memory_used_mib': 5600, 'scope': 'One instantaneous snapshot; not a peak trace or proof of cause.'} |

## Timing variability

The full matrix uses one measured pass per backend/profile in a fixed order, after warm-up. Reranked timing varied between passes. An instantaneous GPU snapshot during the final optimized LongMemEval reranked pass recorded 100% utilization, 86 C, 2,130 MHz and 5,600 MiB used. There is no matched whole-run GPU trace for every pass. The snapshot does not establish a cause for the differences, and the report does not attribute all reranked variation to the database. Repeated rotated-order hybrid measurements are provided separately.
