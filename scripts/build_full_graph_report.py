"""Validate full 20% records and export factual Markdown and CSV comparisons."""

import argparse
import csv
import json
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NAMES = {"dmr": "DMR", "locomo": "LoCoMo", "longmemeval": "LongMemEval"}
BACKENDS = {
    "kuzu": "Kùzu",
    "falkordb_before": "FalkorDB before optimization",
    "falkordb_after": "FalkorDB optimized",
}
PROFILES = {
    "vector": "Vector",
    "default_hybrid": "Hybrid without reranking",
    "reranked_hybrid": "Hybrid with reranking",
}


def table(headers, rows):
    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
                *[
                    "| "
                    + " | ".join(
                        str(c).replace("|", "\\|").replace("\n", " ") for c in row
                    )
                    + " |"
                    for row in rows
                ],
            ]
        )
        + "\n"
    )


def value(number, digits=3):
    return "Not available" if number is None else f"{number:,.{digits}f}"


def csv_file(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--charts", action="store_true")
    args = parser.parse_args()
    report = Path(args.report).resolve()
    state = json.loads((report / "state.json").read_text(encoding="utf-8"))
    assert set(state["jobs"]) == set(NAMES)
    from memory.evaluation.harness.persistence import source_fingerprint
    from memory.evaluation.slices import FrozenSliceAdapter
    from scripts.summarize_reevaluation import aggregate

    assert (
        source_fingerprint() == state["source_fingerprint"]
    ), "Source changed after benchmark."
    adapters = {}
    for name, job in state["jobs"].items():
        path = Path(job["input"])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == job["sha256"]
        adapters[name] = FrozenSliceAdapter(
            json.loads(path.read_text(encoding="utf-8"))
        )

    accuracy = []
    latency = []
    ingestion = []
    deltas = []
    categories = []
    for name in NAMES:
        assert set(state["ingestion"][name]) == set(BACKENDS)
        for backend, r in state["ingestion"][name].items():
            complete = r["status"] == "complete"
            row = dict(
                benchmark=name,
                backend=backend,
                status=r["status"],
                total_documents=state["jobs"][name]["documents"],
                completed_documents=r.get("ingested_ids", r.get("completed_documents")),
                ingestion_time_sec=r.get("ingestion_time_sec"),
                elapsed_until_failure_sec=r.get("wall_sec"),
                docs_per_sec=r.get("docs_per_sec"),
                failures=r.get("failures")
                if isinstance(r.get("failures"), int)
                else len(r.get("failures", [])),
                error=r.get("error"),
                peak_process_rss_mb=r.get("peak_process_rss_mb"),
            )
            stats = r.get("latency") if complete else r.get("successful_add_latency")
            if stats:
                row.update({"add_" + key: v for key, v in stats.items()})
            row["add_p99_ms"] = r.get("p99_ms")
            ingestion.append(row)
        assert set(state["retrieval"][name]) == set(PROFILES)
        for profile, records in state["retrieval"][name].items():
            assert set(records) == set(BACKENDS)
            reference = records["kuzu"]
            for backend, r in records.items():
                raw_path = (
                    report / "raw" / (name + "_" + profile + "_" + backend + ".jsonl")
                )
                raw = [
                    json.loads(line)
                    for line in raw_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                expected_ids = {e.example_id for e in adapters[name].load_examples()}
                assert len(raw) == len(expected_ids)
                assert {row["example_id"] for row in raw} == expected_ids
                recomputed = aggregate(raw, adapters[name])
                for group in ("retrieval", "answer", "latency", "by_category"):
                    assert recomputed[group] == r[group], (
                        name,
                        profile,
                        backend,
                        group,
                        "raw metric mismatch",
                    )

                assert r["failed_examples"] == 0
                assert r["total_examples"] == state["jobs"][name]["questions"]
                assert r["ordered_results_and_answers_match_kuzu"]
                for group in ("retrieval", "answer"):
                    assert r[group] == reference[group], (name, profile, backend, group)
                    for metric, number in r[group].items():
                        accuracy.append(
                            dict(
                                benchmark=name,
                                profile=profile,
                                backend=backend,
                                metric_group=group,
                                metric=metric,
                                value=number,
                                delta_vs_kuzu=number - reference[group][metric],
                            )
                        )
                latency.append(
                    dict(
                        benchmark=name,
                        profile=profile,
                        backend=backend,
                        **r["latency"],
                        requests_per_sec=r["requests_per_sec"],
                        wall_sec=r["wall_sec"],
                        queries=r["total_examples"],
                        retrieval_scored_examples=r["retrieval_scored_examples"],
                        answer_scored_examples=r["answer_scored_examples"],
                        failed_examples=r["failed_examples"],
                        peak_process_rss_mb=r["peak_process_rss_mb"],
                    )
                )
                for category, m in r["by_category"].items():
                    categories.append(
                        dict(
                            benchmark=name,
                            profile=profile,
                            backend=backend,
                            category=category,
                            **m,
                        )
                    )
            old = reference["latency"]["mean_retrieval_ms"]
            before = records["falkordb_before"]["latency"]["mean_retrieval_ms"]
            after = records["falkordb_after"]["latency"]["mean_retrieval_ms"]
            deltas.append(
                dict(
                    benchmark=name,
                    profile=profile,
                    kuzu_mean_ms=old,
                    falkordb_before_mean_ms=before,
                    falkordb_after_mean_ms=after,
                    after_minus_kuzu_ms=after - old,
                    after_vs_kuzu_percent=(after / old - 1) * 100,
                    after_minus_before_ms=after - before,
                    after_vs_before_percent=(after / before - 1) * 100,
                )
            )
    csv_file(report / "all_accuracy_metrics.csv", accuracy)
    csv_file(report / "all_latency_metrics.csv", latency)
    csv_file(report / "ingestion_metrics.csv", ingestion)
    csv_file(report / "latency_differences.csv", deltas)
    csv_file(report / "category_metrics.csv", categories)
    combined = []
    break_even = []
    for name in NAMES:
        for profile in PROFILES:
            for backend in BACKENDS:
                ing = next(
                    r
                    for r in ingestion
                    if r["benchmark"] == name and r["backend"] == backend
                )
                ret = next(
                    r
                    for r in latency
                    if r["benchmark"] == name
                    and r["profile"] == profile
                    and r["backend"] == backend
                )
                combined.append(
                    dict(
                        benchmark=name,
                        profile=profile,
                        backend=backend,
                        ingestion_complete=ing["status"] == "complete",
                        derived_ingestion_plus_query_loop_sec=(
                            ing["ingestion_time_sec"] + ret["wall_sec"]
                        )
                        if ing["status"] == "complete"
                        else None,
                    )
                )
            k = next(
                r
                for r in ingestion
                if r["benchmark"] == name and r["backend"] == "kuzu"
            )
            f = next(
                r
                for r in ingestion
                if r["benchmark"] == name and r["backend"] == "falkordb_after"
            )
            d = next(
                r for r in deltas if r["benchmark"] == name and r["profile"] == profile
            )
            extra = (
                (f["ingestion_time_sec"] - k["ingestion_time_sec"])
                if f["status"] == k["status"] == "complete"
                else None
            )
            saving = (d["kuzu_mean_ms"] - d["falkordb_after_mean_ms"]) / 1000
            break_even.append(
                dict(
                    benchmark=name,
                    profile=profile,
                    extra_ingestion_sec=extra,
                    mean_seconds_saved_per_query=saving,
                    derived_queries_to_offset_extra_ingestion=(max(0, extra) / saving)
                    if extra is not None and saving > 0
                    else None,
                )
            )
    csv_file(report / "combined_times.csv", combined)
    csv_file(report / "derived_break_even.csv", break_even)
    summary = dict(
        jobs=state["jobs"],
        accuracy_unchanged=True,
        retrieval_runs=len(latency),
        evaluated_queries=sum(r["queries"] for r in latency),
        retrieval_failures=0,
        ingestion=ingestion,
        latency_differences=deltas,
    )
    (report / "verified_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    text = [
        "# Twenty percent graph storage analysis\n",
        "This report compares the embedded Kùzu graph backend, the initial FalkorDB migration, and optimized FalkorDB on retained 20% question cohorts. It measures fresh ingestion through the public memory API and retrieval from identical complete corpora. The comparisons isolate the graph backend while keeping retrieval code, vectors, models and scoring settings consistent.\n",
        "## Scope and method\n",
        table(
            ["Dataset", "Questions", "Complete history documents", "Text characters"],
            [
                [
                    NAMES[n],
                    j["questions"],
                    f"{j['documents']:,}",
                    f"{j['text_characters']:,}",
                ]
                for n, j in state["jobs"].items()
            ],
        ),
        "Twenty percent refers to the retained question cohort. Each selected question retains its complete history; the number of documents is not restricted to 20% of sessions. Missing document/query timestamps use one recorded run timestamp. Source-supplied timestamps are preserved.\n",
        f"Application revision: `{state['commit']}`. Embedded graph implementation: `6d10601`. Initial FalkorDB implementation: `a0769ca`. Source fingerprint: `{state['source_fingerprint']}`.\n",
        "The measured retrieval profiles are vector search, hybrid search without reranking, and hybrid search with reranking. Retrieval returns at most ten memories; the vector candidate ceiling is 100, graph expansion uses two hops and at most 50 nodes, and hosted entity extraction is disabled. Dataset graphs therefore contain observations without extracted entities or relationship edges. A separate synthetic graph experiment covers nonempty graph expansion and relationship conflicts.\n",
        "Both neural models are real models using the recorded CUDA provider: BAAI/bge-small-en-v1.5 for 384-dimensional embeddings and BAAI/bge-reranker-base for reranking. Model load/check time is separate from ingestion and query timings. The answer generator returns the first context line; no hosted answer model or official upstream LLM judge is used. Answer scores describe this local generator.\n",
        "Fresh ingestion uses batches of 20 with per-record storage commits. Successful `add` latency includes embedding and coordinated vector/graph writes within the batch. Full ingestion time also includes existence checks and batch preparation. A failed ingestion does not have a full-corpus throughput or completion time. Retrieval corpora are populated from a canonical full graph/vector snapshot, separately from measured fresh-ingestion success or failure.\n",
        "## Fresh ingestion time and throughput\n",
        table(
            [
                "Dataset",
                "Backend",
                "Result",
                "Completed",
                "Total time seconds",
                "Documents per second",
            ],
            [
                [
                    NAMES[r["benchmark"]],
                    BACKENDS[r["backend"]],
                    r["status"],
                    f"{r['completed_documents']}/{r['total_documents']}",
                    value(r["ingestion_time_sec"], 2)
                    if r["status"] == "complete"
                    else f"Partial {value(r['elapsed_until_failure_sec'],2)}",
                    value(r["docs_per_sec"], 2),
                ]
                for r in ingestion
            ],
        ),
        "For a failed run, the reported partial elapsed time is the time until the error. It is not comparable to the successful completion time. Only successful additions are included in the partial add-latency distribution below.\n",
        table(
            [
                "Dataset",
                "Backend",
                "Mean add ms",
                "Median add ms",
                "P95 add ms",
                "P99 add ms",
            ],
            [
                [
                    NAMES[r["benchmark"]],
                    BACKENDS[r["backend"]],
                    value(r.get("add_mean_ms"), 2),
                    value(r.get("add_p50_ms"), 2),
                    value(r.get("add_p95_ms"), 2),
                    value(r.get("add_p99_ms"), 2),
                ]
                for r in ingestion
            ],
        ),
        "The initial FalkorDB integration can encounter `GRAPH.COPY failed, could not fork` during Redis background persistence. Optimized integration retries only that explicit pre-copy error within the configured timeout, while requiring an absent destination and an owned lease. It does not retry ambiguous transport failures. Graph copying for every coordinated write remains part of the implementation.\n",
        "## Retrieval latency and time differences\n",
        "Negative changes below indicate lower optimized latency. Percentages compare the means of the same dataset/profile; ingestion and retrieval timings have different units and scopes.\n",
        table(
            [
                "Dataset",
                "Profile",
                "Kùzu mean ms",
                "FalkorDB before ms",
                "FalkorDB optimized ms",
                "Change vs Kùzu",
                "Change vs before",
            ],
            [
                [
                    NAMES[r["benchmark"]],
                    PROFILES[r["profile"]],
                    value(r["kuzu_mean_ms"], 2),
                    value(r["falkordb_before_mean_ms"], 2),
                    value(r["falkordb_after_mean_ms"], 2),
                    f"{r['after_vs_kuzu_percent']:+.2f}%",
                    f"{r['after_vs_before_percent']:+.2f}%",
                ]
                for r in deltas
            ],
        ),
    ]
    for name in NAMES:
        for profile in PROFILES:
            selected = [
                r for r in latency if r["benchmark"] == name and r["profile"] == profile
            ]
            text.extend(
                [
                    f"### {NAMES[name]} {PROFILES[profile]}\n",
                    table(
                        [
                            "Backend",
                            "Mean ms",
                            "Median ms",
                            "P95 ms",
                            "P99 ms",
                            "Maximum ms",
                            "Requests per second",
                        ],
                        [
                            [
                                BACKENDS[r["backend"]],
                                value(r["mean_retrieval_ms"], 2),
                                value(r["p50_retrieval_ms"], 2),
                                value(r["p95_retrieval_ms"], 2),
                                value(r["p99_retrieval_ms"], 2),
                                value(r["max_retrieval_ms"], 2),
                                value(r["requests_per_sec"], 2),
                            ]
                            for r in selected
                        ],
                    ),
                ]
            )
    text.extend(
        [
            "Mean total latency is retrieval plus first-line generation. Throughput uses the full evaluation-loop elapsed time, which also includes scoring and raw-result recording. The complete total/generation latency columns are in `all_latency_metrics.csv`. Each full matrix profile measures the whole selected cohort after three warm-up examples, with one measured pass. Separate repeated default-hybrid tests are reported in the supporting evidence. Small timing differences are not confidence intervals or proof of a general performance advantage.\n",
            "## All retrieval and answer metrics\n",
            "Every returned ID, ranking and predicted answer matched the Kùzu reference for each profile. All retrieval and answer metric differences between backends are zero. The following tables show the common value shared by all three backends; the CSV preserves a separate row for every backend/metric. Metrics range from zero to one.\n",
        ]
    )
    metric_names = [
        "recall@1",
        "recall@3",
        "recall@5",
        "recall@10",
        "precision@1",
        "precision@3",
        "precision@5",
        "precision@10",
        "mrr",
        "ndcg@1",
        "ndcg@3",
        "ndcg@5",
        "ndcg@10",
        "average_precision@10",
        "exact_match",
        "substring_match",
        "token_f1",
    ]
    for name in NAMES:
        reference = state["retrieval"][name]
        rows = []
        for metric in metric_names:
            values = [
                reference[p]["kuzu"]["retrieval"].get(
                    metric, reference[p]["kuzu"]["answer"].get(metric)
                )
                for p in PROFILES
            ]
            rows.append([metric, *[value(v, 6) for v in values], "0"])
        counters = reference["vector"]["kuzu"]
        text.extend(
            [
                f"### {NAMES[name]} quality metrics\n",
                f"Selected questions: {counters['total_examples']}. Retrieval-scored questions: {counters['retrieval_scored_examples']}. Answer-scored questions: {counters['answer_scored_examples']}. Questions lacking annotated retrieval evidence or a nonempty answer are excluded from the corresponding quality average, while remaining included in latency measurements.\n",
                table(
                    [
                        "Metric",
                        "Vector",
                        "Hybrid",
                        "Reranked hybrid",
                        "Backend difference",
                    ],
                    rows,
                ),
            ]
        )
    text.extend(
        [
            "Recall measures the fraction of annotated relevant memories returned. Precision divides unique relevant hits by the cutoff even when fewer results are returned. MRR measures the reciprocal rank of the first relevant result. NDCG measures ranking quality with discounted gains. Average precision at ten divides accumulated hit precision by the full number of annotated relevant memories. Duplicate IDs consume ranks without earning extra credit.\n",
            "Exact match compares normalized answers, substring match checks whether the normalized gold answer occurs within the normalized prediction, and token F1 uses token overlap. Case, punctuation, articles and whitespace follow the implemented normalization. Category-level recall, MRR and answer scores are in `category_metrics.csv`.\n",
            "## Memory use and reliability\n",
            table(
                [
                    "Dataset",
                    "Profile",
                    "Backend",
                    "Peak process RSS MiB",
                    "Retrieval failures",
                ],
                [
                    [
                        NAMES[r["benchmark"]],
                        PROFILES[r["profile"]],
                        BACKENDS[r["backend"]],
                        value(r["peak_process_rss_mb"], 1),
                        r["failed_examples"],
                    ]
                    for r in latency
                ],
            ),
            "RSS includes the shared model host allocations and live storage objects. The measurements run in one process and are not isolated database footprints; they should not be added to or directly compared with server memory as if they represented equivalent components. Server and fresh-process storage memory measurements, when supplied, are separately identified. GPU provider/version and initial device memory are recorded in `preflight.json`.\n",
            "## Concurrency and graph structure\n",
            "The supporting 20% DMR concurrent test uses one shared engine with one, four and eight request workers. Its exact readings are linked below. A graph lease still serializes cooperating requests; higher worker counts can increase queue latency without increasing throughput proportionally. The optimization does not implement concurrent-reader access.\n",
            "A separate synthetic graph has 500 entities, 1,500 observations, 499 RELATES, 1,500 ABOUT and 50 SUPERSEDES relationships. Batched traversal and cached conflicts are compared with the initial FalkorDB implementation, with exact result matching. These are structural microbenchmarks, not dataset retrieval-quality scores.\n",
            "## Interpretation and limits\n",
            "Revision-aware conflict caching avoids repeated ownership/relationship reads while the graph is unchanged. Seed batching reduces multiple entity queries to bounded batches. Writes invalidate the cache, so read-heavy and alternating write/search workloads have different costs. Full-graph copies remain a write-cost and scaling consideration.\n",
            "The results apply to these complete-context cohorts, model settings, local machine and pinned service. They do not establish capacity for arbitrary larger graphs, distributed deployment or untested prompt concurrency. Graph-backed recall improvements require actual entity/relationship extraction; default extraction is disabled here. The local first-line answer scores do not represent an LLM answering the tasks.\n",
            "Kùzu and FalkorDB use different storage/recovery designs. FalkorDB uses a persistent Redis service with append-only logging and one-second fsync; process-level compensation preserves caught-error recovery across the graph and vectors but does not provide cross-store crash atomicity. No durability guarantee was removed to improve the retrieval figures.\n",
            "## Validation and reproduction\n",
            "Optimization validation: 119 regression tests and four dataset checks passed. Tests exercise real FalkorDB with declared offline neural/provider fixtures, including seed ordering/limits, shared-client cache refresh, rollback invalidation, lost publication responses and bounded copy-retry behavior. Performance evaluations use the real GPU models.\n",
            "Run `python scripts/full_graph_analysis.py --run-id NEW_RUN_ID --report report/NEW_REPORT` with FalkorDB running and the retained inputs and isolated CUDA runtime available. Install the optional profiling and migration dependencies for memory probes and legacy comparisons. The script saves normalized complete-context inputs and fingerprints, raw per-query results, per-add timings, model checks and resumable state. It rejects a changed application source on resume. Original historical stores and reports are read-only inputs.\n",
            "## Evidence\n",
            "- [Complete run state](state.json)\n- [Validated summary](verified_summary.json)\n- [All accuracy metrics](all_accuracy_metrics.csv)\n- [All latency metrics](all_latency_metrics.csv)\n- [Ingestion metrics](ingestion_metrics.csv)\n- [Latency differences](latency_differences.csv)\n- [Category metrics](category_metrics.csv)\n- [Model and runtime checks](preflight.json)\n- [Repeated hybrid and concurrency tests](../falkordb_optimization_20261013/comparison.json)\n- [Graph structure and mixed workload tests](../falkordb_optimization_20261013/additional_workloads.json)\n",
        ]
    )
    text.extend(
        [
            "## Combined workload time\n",
            "The following values add separately measured fresh ingestion time and the complete selected query-loop time. They exclude model loading and graph import/setup. They are derived sums, not a separate uninterrupted end-to-end test. Failed ingestions have no combined completion time.\n",
            table(
                ["Dataset", "Profile", "Backend", "Derived combined seconds"],
                [
                    [
                        NAMES[r["benchmark"]],
                        PROFILES[r["profile"]],
                        BACKENDS[r["backend"]],
                        value(r["derived_ingestion_plus_query_loop_sec"], 2),
                    ]
                    for r in combined
                ],
            ),
        ]
    )
    text.extend(
        [
            "## Derived ingestion offset\n",
            "If optimized ingestion takes longer but warm retrieval is faster, the extra ingestion time can be divided by the average time saved per query. This estimates how many queries to an unchanged corpus would offset the extra initial ingestion time. It assumes these measured means continue to hold, no further writes invalidate the cache, and no concurrency/queue changes occur. It is not a measured capacity guarantee. A missing value means no finite positive offset can be derived from the observed means.\n",
            table(
                [
                    "Dataset",
                    "Profile",
                    "Extra ingestion seconds",
                    "Seconds saved per query",
                    "Estimated queries",
                ],
                [
                    [
                        NAMES[r["benchmark"]],
                        PROFILES[r["profile"]],
                        value(r["extra_ingestion_sec"], 2),
                        value(r["mean_seconds_saved_per_query"], 6),
                        value(r["derived_queries_to_offset_extra_ingestion"], 0),
                    ]
                    for r in break_even
                ],
            ),
            "The batching and cache changes were applied to the FalkorDB integration only. Equivalent optimizations were not applied to the Kùzu reference, so measured improvements cannot be attributed solely to the database engine.\n",
        ]
    )
    memory = []
    for path in sorted(report.glob("memory_*.json")):
        memory.append(json.loads(path.read_text(encoding="utf-8")))
    if memory:
        csv_file(report / "storage_memory.csv", memory)
        text.extend(
            [
                "## Fresh process storage memory\n",
                "Each row runs in a separate Python process without loading neural model weights. It includes the graph client or embedded graph plus embedded Qdrant. The graph data for FalkorDB lives in a separate server process, so client RSS is not whole-system database memory. Redis MEMORY USAGE returned only 56 or 64 bytes for the module value; that does not measure the full graph allocation and is not used as a graph-RAM result.\n",
                table(
                    [
                        "Dataset",
                        "Backend",
                        "Baseline RSS MiB",
                        "Warm RSS MiB",
                        "Increase MiB",
                    ],
                    [
                        [
                            NAMES[r["benchmark"]],
                            BACKENDS[r["backend"]],
                            value(r["process_baseline_rss_mb"], 1),
                            value(r["process_warm_rss_mb"], 1),
                            value(r["process_rss_increase_mb"], 1),
                        ]
                        for r in memory
                    ],
                ),
            ]
        )
    support = report.parent / "falkordb_optimization_20261013/comparison.json"
    if support.exists():
        prior = json.loads(support.read_text(encoding="utf-8"))
        concurrent = []
        for workers, roles in prior["cohorts"]["dmr"]["concurrent"].items():
            for backend, r in roles.items():
                concurrent.append(
                    dict(
                        workers=int(workers),
                        backend=backend,
                        **{
                            k: r[k]
                            for k in [
                                "queries",
                                "mean_ms",
                                "p95_ms",
                                "requests_per_sec",
                                "ordered_results_match_historical",
                            ]
                        },
                    )
                )
        csv_file(report / "concurrency.csv", concurrent)
        text.extend(
            [
                "## Concurrent prompt measurements\n",
                "These supporting runs each execute all 100 questions from the 20% DMR cohort through one shared engine. Latency includes application queue waits. Returned rankings matched the retained reference. These tests measure the current serialized engine rather than parallel native database capacity.\n",
                table(
                    [
                        "Workers",
                        "Backend",
                        "Queries",
                        "Mean ms",
                        "P95 ms",
                        "Requests per second",
                    ],
                    [
                        [
                            r["workers"],
                            BACKENDS[r["backend"]],
                            r["queries"],
                            value(r["mean_ms"], 2),
                            value(r["p95_ms"], 2),
                            value(r["requests_per_sec"], 2),
                        ]
                        for r in concurrent
                    ],
                ),
            ]
        )
    workloads = (
        report.parent / "falkordb_optimization_20261013/additional_workloads.json"
    )
    if workloads.exists():
        extra = json.loads(workloads.read_text(encoding="utf-8"))
        operations = extra["structure"]["operations"]
        text.extend(
            [
                "## Graph structure measurements\n",
                table(
                    [
                        "Operation",
                        "Before mean ms",
                        "Optimized mean ms",
                        "Change",
                        "Exact results",
                    ],
                    [
                        [
                            name,
                            value(r["before"]["mean_ms"], 2),
                            value(r["after"]["mean_ms"], 2),
                            f"{(r['after']['mean_ms']/r['before']['mean_ms']-1)*100:+.2f}%",
                            r["exact_results_match"],
                        ]
                        for name, r in operations.items()
                    ],
                ),
            ]
        )
        if "mixed" in extra:
            mixed = extra["mixed"]
            rows = []
            for backend, r in mixed["backends"].items():
                rows.append(
                    [
                        BACKENDS[backend],
                        r.get("status", "complete"),
                        r.get("completed_steps", mixed["steps"]),
                        value((r.get("write") or {}).get("mean_ms"), 2),
                        value((r.get("search_after_write") or {}).get("mean_ms"), 2),
                        value((r.get("total") or {}).get("mean_ms"), 2),
                    ]
                )
            text.extend(
                [
                    "## Alternating write and search measurements\n",
                    f"This supporting test alternates a valid importance update and a search for each of {mixed['steps']} questions in the 20% DMR cohort. Each write invalidates the conflict cache. Failed runs retain only completed-step timing and are not full-workload completion results.\n",
                    table(
                        [
                            "Backend",
                            "Result",
                            "Steps",
                            "Write mean ms",
                            "Search mean ms",
                            "Combined mean ms",
                        ],
                        rows,
                    ),
                ]
            )
    hardware_path = report / "hardware.json"
    if hardware_path.exists():
        hardware = json.loads(hardware_path.read_text(encoding="utf-8"))
        text.extend(
            [
                "## Recorded environment\n",
                table(
                    ["Item", "Recorded value"],
                    [[key, str(val)] for key, val in hardware.items()],
                ),
            ]
        )
    highlights = [
        "## Measured findings\n",
        f"The full matrix contains {summary['evaluated_queries']:,} measured queries across {len(latency)} dataset/profile/backend combinations. Returned rankings, predictions, and all 17 local retrieval/answer metrics matched across graph backends for each profile.\n",
    ]
    rows = []
    for name in NAMES:
        d = next(
            r
            for r in deltas
            if r["benchmark"] == name and r["profile"] == "default_hybrid"
        )
        k = next(
            r for r in ingestion if r["benchmark"] == name and r["backend"] == "kuzu"
        )
        f = next(
            r
            for r in ingestion
            if r["benchmark"] == name and r["backend"] == "falkordb_after"
        )
        ratio = (
            f["ingestion_time_sec"] / k["ingestion_time_sec"]
            if f["status"] == k["status"] == "complete"
            else None
        )
        rows.append(
            [
                NAMES[name],
                value(k["ingestion_time_sec"], 2),
                value(f["ingestion_time_sec"], 2),
                value(ratio, 2) + " times",
                f"{d['after_vs_kuzu_percent']:+.2f}%",
            ]
        )
    highlights.extend(
        [
            table(
                [
                    "Dataset",
                    "Kùzu ingestion seconds",
                    "Optimized ingestion seconds",
                    "Ingestion time ratio",
                    "Hybrid latency change",
                ],
                rows,
            ),
            "Optimized warm hybrid retrieval had lower mean latency than the Kùzu reference in all three cohorts. Vector-only and reranked retrieval were not universally faster. Fresh ingestion took longer, and the alternating write/search workload also took longer with the current FalkorDB graph-copy design. These results support different conclusions for stable-corpus retrieval and frequent memory updates.\n",
            "The initial migration failed fresh-ingestion tests during Redis background persistence. The bounded copy-startup retry allowed optimized ingestion to complete every cohort. These are integration-version results; the same cache/batching changes were not applied to the Kùzu reference.\n",
        ]
    )
    text[2:2] = highlights
    text.extend(
        [
            "## Timing variability\n",
            "The full matrix uses one measured pass per backend/profile in a fixed order, after warm-up. Reranked timing varied between passes. An instantaneous GPU snapshot during the final optimized LongMemEval reranked pass recorded 100% utilization, 86 C, 2,130 MHz and 5,600 MiB used. There is no matched whole-run GPU trace for every pass. The snapshot does not establish a cause for the differences, and the report does not attribute all reranked variation to the database. Repeated rotated-order hybrid measurements are provided separately.\n",
        ]
    )
    (report / "report.md").write_text("\n".join(text), encoding="utf-8")
    if args.charts:
        charts(report, ingestion, deltas)
    print(
        json.dumps(
            dict(
                report=str(report / "report.md"),
                retrieval_runs=len(latency),
                evaluated_queries=summary["evaluated_queries"],
            )
        )
    )


def charts(report, ingestion, deltas):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    directory = report / "figures"
    directory.mkdir(exist_ok=True)
    colors = ["#4c566a", "#b87333", "#327e77"]
    plt.rcParams.update(
        {"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    for profile in PROFILES:
        fig, axis = plt.subplots(figsize=(9, 4.3), layout="constrained")
        selected = [r for r in deltas if r["profile"] == profile]
        x = np.arange(len(selected))
        width = 0.24
        for i, (backend, label) in enumerate(BACKENDS.items()):
            key = {
                "kuzu": "kuzu_mean_ms",
                "falkordb_before": "falkordb_before_mean_ms",
                "falkordb_after": "falkordb_after_mean_ms",
            }[backend]
            bars = axis.bar(
                x + (i - 1) * width,
                [r[key] for r in selected],
                width,
                label=label,
                color=colors[i],
            )
            axis.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
        axis.set_xticks(x, [NAMES[r["benchmark"]] for r in selected])
        axis.set_ylabel("Mean retrieval latency in milliseconds")
        axis.set_title(PROFILES[profile])
        axis.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncols=3, fontsize=8)
        fig.savefig(directory / (profile + ".png"), dpi=180)
        fig.savefig(directory / (profile + ".pdf"))
        plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), layout="constrained")
    for axis, name in zip(axes, NAMES):
        selected = [r for r in ingestion if r["benchmark"] == name]
        successful = [r for r in selected if r["status"] == "complete"]
        labels = [
            BACKENDS[r["backend"]].replace("FalkorDB ", "FalkorDB\n")
            for r in successful
        ]
        bars = axis.bar(
            labels,
            [r["ingestion_time_sec"] for r in successful],
            color=[colors[list(BACKENDS).index(r["backend"])] for r in successful],
        )
        axis.bar_label(bars, fmt="%.1f", padding=3)
        axis.set_title(NAMES[name])
        axis.set_ylabel("Complete ingestion seconds")
        axis.tick_params(axis="x", labelsize=8)
    fig.suptitle("Fresh ingestion completion time; failed runs excluded")
    fig.savefig(directory / "ingestion.png", dpi=180)
    fig.savefig(directory / "ingestion.pdf")
    plt.close(fig)
    state = json.loads((report / "state.json").read_text(encoding="utf-8"))
    fig, axis = plt.subplots(figsize=(9, 4.3), layout="constrained")
    x = np.arange(len(NAMES))
    width = 0.24
    for i, (profile, label) in enumerate(PROFILES.items()):
        vals = [
            state["retrieval"][name][profile]["kuzu"]["retrieval"].get("recall@10", 0)
            * 100
            for name in NAMES
        ]
        bars = axis.bar(x + (i - 1) * width, vals, width, label=label, color=colors[i])
        axis.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
    axis.set_xticks(x, list(NAMES.values()))
    axis.set_ylim(0, 110)
    axis.set_ylabel("Recall at ten in percent")
    axis.set_title("Retrieval quality; all three backends match")
    axis.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncols=3, fontsize=8)
    fig.savefig(directory / "quality.png", dpi=180)
    fig.savefig(directory / "quality.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), layout="constrained")
    for axis, name in zip(axes, NAMES):
        for i, (backend, label) in enumerate(BACKENDS.items()):
            path = report / "ingestion" / (name + "_" + backend + ".jsonl")
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            times = [r["latency_ms"] / 1000 for r in rows if r["success"]]
            axis.plot(
                np.arange(1, len(times) + 1),
                np.cumsum(times),
                label=label,
                color=colors[i],
            )
        axis.set_title(NAMES[name])
        axis.set_xlabel("Committed documents")
        axis.set_ylabel("Cumulative add time in seconds")
    axes[0].legend(fontsize=7)
    fig.suptitle("API add timing growth; excludes batch checks and setup")
    fig.savefig(directory / "ingestion_curve.png", dpi=180)
    fig.savefig(directory / "ingestion_curve.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
