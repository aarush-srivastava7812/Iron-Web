"""Validate exclusive latency samples and produce a factual attribution report."""

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NAMES = ("dmr", "locomo", "longmemeval")
PROFILES = ("vector", "default_hybrid", "reranked_hybrid")


def csv_file(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
                *("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows),
            ]
        )
        + "\n"
    )


def main():
    from scripts.profile_latency_breakdown import aggregate_spans

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    args = parser.parse_args()
    report = Path(args.report).resolve()
    state = json.loads((report / "state.json").read_text(encoding="utf-8"))
    assert state["complete"] and state["options"]["limit"] == 0
    assert not state["options"]["skip_rerank"]
    prior_path = Path(state["prior_report"])
    prior = json.loads((prior_path / "state.json").read_text(encoding="utf-8"))
    assert state["application_fingerprint"] == prior["source_fingerprint"]
    accuracy, components, latency, command_rows = [], [], [], []
    queries = 0
    for name in NAMES:
        for profile in PROFILES:
            rows = [
                json.loads(line)
                for line in (report / f"{name}_{profile}.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            cohort = state["cohorts"][name][profile]
            expected = prior["jobs"][name]["questions"]
            assert len(rows) == len({r["example_id"] for r in rows}) == expected
            assert all(r["returned_ids_match"] and r["prediction_match"] for r in rows)
            expected_commands = {"SET": 1.0, "EVALSHA": 1.0}
            if profile != "vector":
                expected_commands["GET"] = 2.0
            assert {
                command: stats["per_request"]
                for command, stats in cohort["command_statistics"].items()
            } == expected_commands
            assert (
                aggregate_spans(rows)["exclusive_mean_ms"]
                == cohort["exclusive_mean_ms"]
            )
            assert cohort["accounting_error_ms"] < 1e-6
            queries += len(rows)
            total = cohort["total"]["mean_ms"]
            for label, value in cohort["exclusive_mean_ms"].items():
                components.append(
                    dict(
                        dataset=name,
                        workload=profile,
                        component=label,
                        mean_ms=value,
                        percent=100 * value / total,
                    )
                )
            latency.append(dict(dataset=name, workload=profile, **cohort["total"]))
            for group in ("retrieval", "answer"):
                assert (
                    cohort["metrics"][group]
                    == prior["retrieval"][name][profile]["falkordb_after"][group]
                )
                for metric, value in cohort["metrics"][group].items():
                    accuracy.append(
                        dict(
                            dataset=name,
                            profile=profile,
                            metric=metric,
                            value=value,
                            difference_from_previous=0,
                        )
                    )
            for command, stats in cohort["command_statistics"].items():
                command_rows.append(
                    dict(
                        dataset=name,
                        workload=profile,
                        command=command,
                        per_request=stats["per_request"],
                        mean_ms=stats["mean_ms"],
                        server_execution_ms=stats.get("server_execution", {}).get(
                            "mean_ms"
                        ),
                    )
                )
        write_rows = [
            json.loads(line)
            for line in (report / f"{name}_writes.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        written = state["ingestion_probes"][name]
        assert len(write_rows) == written["writes"] == 20 and written["exact_readback"]
        assert (
            aggregate_spans(write_rows)["exclusive_mean_ms"]
            == written["exclusive_mean_ms"]
        )
        for label, value in written["exclusive_mean_ms"].items():
            components.append(
                dict(
                    dataset=name,
                    workload="existing_corpus_write",
                    component=label,
                    mean_ms=value,
                    percent=100 * value / written["total"]["mean_ms"],
                )
            )
        latency.append(
            dict(dataset=name, workload="existing_corpus_write", **written["total"])
        )
        for command, stats in written["command_statistics"].items():
            command_rows.append(
                dict(
                    dataset=name,
                    workload="existing_corpus_write",
                    command=command,
                    per_request=stats["per_request"],
                    mean_ms=stats["mean_ms"],
                    server_execution_ms=stats.get("server_execution", {}).get(
                        "mean_ms"
                    ),
                )
            )
        assert state["preserved_sources"][name]
    assert queries == 1791 and len(accuracy) == 153
    csv_file(report / "components.csv", components)
    csv_file(report / "latency.csv", latency)
    csv_file(report / "accuracy.csv", accuracy)
    csv_file(report / "commands.csv", command_rows)

    text = [
        "# Iron Web latency attribution report\n",
        "Analysis date: 14 October 2026. All times below are measured wall-clock milliseconds.\n",
        "## Scope and interpretation\n",
        f"The measured application is the optimized FalkorDB revision used in the previous 20% report. "
        f"The isolated source comes from commit `{state['revision']}`; its application fingerprint is "
        f"`{state['application_fingerprint']}`. Newer uncommitted application changes are outside this analysis.\n",
        "All 597 retained questions were repeated in vector, default hybrid, and reranked hybrid modes: "
        "1,791 measured retrieval requests. DMR has 100 questions and 500 documents; LoCoMo has 397 questions "
        "and 70 documents; LongMemEval has 100 questions and 4,612 documents. Each profile uses three warm-up "
        "queries before the timed pass. Twenty additional documents were written to a private copy of each "
        "complete corpus, giving 60 write probes. Those probes measure writes to an existing corpus; they "
        "do not repeat or replace the earlier full fresh-ingestion measurements.\n",
        "BAAI/bge-small-en-v1.5 generates embeddings locally on CUDA. BAAI/bge-reranker-base reranks locally "
        "on CUDA with batch size 16. Qdrant is embedded in the Python application. FalkorDB runs in Docker "
        "on this computer, reached through TCP at the loopback address. Entity extraction is disabled, "
        "as in the prior benchmark. These corpora contain observations but no extracted entities or graph "
        "edges; graph traversal workload is therefore absent. Model loading and graph import are excluded "
        "from request times. External answer generation and remote embedding APIs are also absent.\n",
        "## Retrieval: where the time goes\n",
        "The following components are exclusive: a nested database call is subtracted from its parent. "
        "Each row sums to the measured request mean. Other time includes validation, merging and scoring, "
        "formatting, Python lock management, and measurement overhead. P95 is the time at or below which "
        "95% of this pass's requests completed; it is not a confidence bound.\n",
    ]
    rows = []
    for name in NAMES:
        for profile in PROFILES:
            c = state["cohorts"][name][profile]
            m = c["exclusive_mean_ms"]
            tracked = sum(
                m.get(k, 0)
                for k in ("embedding", "vector_read", "reranking", "redis_control")
            )
            rows.append(
                [
                    name,
                    profile.replace("_", " "),
                    f"{c['total']['mean_ms']:.2f}",
                    f"{m.get('embedding',0):.2f}",
                    f"{m.get('vector_read',0):.2f}",
                    f"{m.get('reranking',0):.2f}",
                    f"{m.get('redis_control',0):.2f}",
                    f"{c['total']['mean_ms']-tracked:.2f}",
                    f"{c['total']['p95_ms']:.2f}",
                ]
            )
    text.append(
        table(
            [
                "Dataset",
                "Mode",
                "Total",
                "Embed",
                "Vector",
                "Rerank",
                "Redis",
                "Other",
                "P95",
            ],
            rows,
        )
    )
    text.append(
        "Reranking includes preparing and tokenizing candidate texts, neural inference, and sorting "
        "the scores. Embedding includes text preparation and neural inference. These measurements "
        "do not split GPU kernel execution from CPU preparation. Vector search includes local "
        "candidate filtering and result construction.\n"
    )
    for name in NAMES:
        c = state["cohorts"][name]["reranked_hybrid"]
        share = c["exclusive_mean_ms"]["reranking"] / c["total"]["mean_ms"] * 100
        raw = [
            json.loads(line)
            for line in (report / f"{name}_reranked_hybrid.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        candidates = [r["rerank_candidates"] for r in raw]
        text.append(
            f"For {name}, reranking accounts for {share:.1f}% of average request time. "
            f"The reranker scores {min(candidates)} to {max(candidates)} candidates per query.\n"
        )
    text.extend(
        [
            "## Network and database commands\n",
            "The PING measurements below are 100 consecutive warm pooled round trips after ten discarded "
            "warm-up calls. They include Python client work, TCP transport through Docker, Redis dispatch "
            "and response handling. They are a round-trip reference, not a direct measurement of pure "
            "network transmission time. No packet capture or separate client/server clock measurements "
            "were used.\n",
        ]
    )
    text.append(
        table(
            ["Dataset phase", "PING mean", "PING P95"],
            [
                [
                    n,
                    f"{state['ping'][n]['mean_ms']:.3f}",
                    f"{state['ping'][n]['p95_ms']:.3f}",
                ]
                for n in NAMES
            ],
        )
    )
    text.append(
        "Warm vector requests issue two Redis commands: SET to acquire the lease and EVALSHA to release "
        "it. Warm default and reranked hybrid requests issue four: those two plus two GET calls for "
        "cache revisions. The full warm passes issue no GRAPH.QUERY commands because the empty entity "
        "lookup and conflict lookup are cached. Thus the Redis column in the retrieval table mainly "
        "represents lock/cache round trips, not graph traversal.\n"
    )
    text.append(
        "The graph SDK reports internal server execution time for GRAPH.QUERY. The table below uses "
        "queries observed during write probes. Client command wall time minus server execution includes "
        "transport, dispatch/queueing outside the reported interval, argument encoding, Redis protocol "
        "parsing and client scheduling. It must not be labeled pure network latency. Graph SDK result "
        "decoding after the Redis response is separately included in Other.\n"
    )
    query_rows = []
    for name in NAMES:
        s = state["ingestion_probes"][name]["command_statistics"]["GRAPH.QUERY"]
        query_rows.append(
            [
                name,
                f"{s['per_request']:.1f}",
                f"{s['mean_ms']:.3f}",
                f"{s['server_execution']['mean_ms']:.3f}",
                f"{s['wall_minus_server']['mean_ms']:.3f}",
            ]
        )
    text.append(
        table(
            [
                "Dataset",
                "Queries/write",
                "Client/query",
                "Server/query",
                "Remaining/query",
            ],
            query_rows,
        )
    )
    text.extend(
        [
            "## Writes: copying the graph\n",
            "Every coordinated write starts by copying the complete graph to a private staging graph, "
            "applies graph changes and the vector update, then publishes the graph using a Redis script "
            "and removes the recovery copy. The copy column is the entire GRAPH.COPY command wait; "
            "server copy work and transport are not separated. The complete command time is counted "
            "once. Transaction/retry time covers staging/publication bookkeeping and retry waits, "
            "excluding the command waits already shown. Other includes recovery-copy deletion, vector "
            "snapshot reads, SDK decoding, serialization and Python execution.\n",
        ]
    )
    write_table = []
    for name in NAMES:
        c = state["ingestion_probes"][name]
        m = c["exclusive_mean_ms"]
        keys = (
            "embedding",
            "vector_write",
            "graph_copy",
            "graph_query",
            "redis_control",
            "transaction_other",
        )
        other = c["total"]["mean_ms"] - sum(m.get(k, 0) for k in keys)
        write_table.append(
            [
                name,
                f"{c['total']['mean_ms']:.2f}",
                *(f"{m.get(k,0):.2f}" for k in keys),
                f"{other:.2f}",
            ]
        )
    text.append(
        table(
            [
                "Dataset",
                "Total",
                "Embed",
                "Vector write",
                "Graph copy",
                "Graph queries",
                "Redis",
                "Txn/retry",
                "Other",
            ],
            write_table,
        )
    )
    for name in NAMES:
        c = state["ingestion_probes"][name]
        pct = 100 * c["exclusive_mean_ms"].get("graph_copy", 0) / c["total"]["mean_ms"]
        failures = (
            sum(
                s["count"]
                for command, s in c["command_statistics"].items()
                if command == "GRAPH.COPY"
            )
            - c["writes"]
        )
        text.append(
            f"For {name}, graph copy accounts for {pct:.1f}% of average write time. "
            f"There were {failures} additional copy command attempts across 20 successful writes.\n"
        )
    long_writes = state["ingestion_probes"]["longmemeval"]
    long_retries = (
        long_writes["command_statistics"]["GRAPH.COPY"]["count"] - long_writes["writes"]
    )
    text.append(
        f"LongMemEval had {long_retries} recovered GRAPH.COPY failures across 20 writes. The retry path requests "
        f"a 50 ms pause per failed attempt: {long_retries*0.05:.2f} seconds in total, or "
        f"{long_retries*50/20:.0f} ms per write, derived from the attempt count. The complete measured "
        f"transaction/retry component is {long_writes['exclusive_mean_ms']['transaction_other']:.2f} ms "
        f"per write. This waiting is separate from the {long_writes['exclusive_mean_ms']['graph_copy']:,.2f} "
        "ms spent inside successful and failed copy commands.\n"
    )
    copy_rows = []
    for name in NAMES:
        probes = [
            json.loads(line)
            for line in (report / f"{name}_writes.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        events = [
            e for r in probes for e in r["commands"] if e["command"] == "GRAPH.COPY"
        ]
        successes = sum(e["wall_ms"] for e in events if e["error"] is None) / 20
        failures = sum(e["wall_ms"] for e in events if e["error"] is not None) / 20
        copy_rows.append(
            [
                name,
                f"{successes:.2f}",
                f"{failures:.2f}",
                str(sum(e["error"] is not None for e in events)),
            ]
        )
    text.append(
        table(
            [
                "Dataset",
                "Successful copy time/write",
                "Failed copy time/write",
                "Recovered failures",
            ],
            copy_rows,
        )
    )
    text.append(
        "All 60 write probes succeeded and their stored text was read back exactly. Original benchmark "
        "input files and canonical graph files retained their SHA-256 hashes. Only this run's graph "
        "namespaces were removed after measurement.\n"
    )
    text.extend(
        [
            "## Concurrent prompts and waiting\n",
            "The engine serializes operations through one graph lease and a local mutex. Multiple "
            "submitted requests therefore wait for earlier requests, including their embedding and "
            "reranking work. The measurements below use the whole DMR or LongMemEval question cohort "
            "in default hybrid mode with four or eight workers sharing one engine. Local lock wait is "
            "measured separately and is already included in total latency. This is client-side waiting, "
            "not a server network round trip.\n",
        ]
    )
    text.append(
        table(
            [
                "Dataset",
                "Workers",
                "Mean total",
                "Mean local wait",
                "P95 total",
                "Requests/s",
            ],
            [
                [
                    name,
                    workers,
                    f"{c['total']['mean_ms']:.2f}",
                    f"{c['exclusive_mean_ms'].get('local_lock_wait',0):.2f}",
                    f"{c['total']['p95_ms']:.2f}",
                    f"{c['requests_per_sec']:.2f}",
                ]
                for name in ("dmr", "longmemeval")
                for workers, c in state["concurrency"][name].items()
            ],
        )
    )
    text.extend(
        [
            "## Cold caches\n",
            "Ten queries per dataset were run after invalidating both graph lookup caches. These are "
            "measured separately and do not enter the warm-cohort means. Cache refresh scans observation "
            "ownership and conflict relationships; this matters after writes or cache invalidation.\n",
        ]
    )
    text.append(
        table(
            [
                "Dataset",
                "Warm hybrid mean",
                "Cold hybrid mean",
                "Cold graph command time",
            ],
            [
                [
                    n,
                    f"{state['cohorts'][n]['default_hybrid']['total']['mean_ms']:.2f}",
                    f"{state['cold_cache'][n]['total']['mean_ms']:.2f}",
                    f"{state['cold_cache'][n]['exclusive_mean_ms'].get('graph_query',0):.2f}",
                ]
                for n in NAMES
            ],
        )
    )
    text.extend(
        [
            "## Accuracy and comparison with previous timings\n",
            "Every returned ID and its order, every predicted answer, and all 17 local quality metrics "
            "matched the previous optimized FalkorDB result for the same dataset and profile. The "
            "153 dataset/profile/metric rows are saved in accuracy.csv. Metrics include recall, "
            "precision and nDCG at 1/3/5/10, MRR, average precision at 10, exact match, substring match "
            "and token F1. LoCoMo has 395 retrieval-scored and 397 answer-scored examples. Answer scoring "
            "uses the same first-context-line generator, not an external language model.\n",
            "This run adds instrumentation; it does not apply an optimization. Differences between "
            "its total timings and the previous report are fresh measurement differences, not a "
            "measured improvement caused by a code change. GPU clocks/temperature, CPU scheduling, "
            "Docker load and persistence activity were not controlled.\n",
        ]
    )
    text.append(
        table(
            ["Dataset", "Mode", "Previous mean", "This mean"],
            [
                [
                    n,
                    p.replace("_", " "),
                    f"{prior['retrieval'][n][p]['falkordb_after']['latency']['mean_retrieval_ms']:.2f}",
                    f"{state['cohorts'][n][p]['total']['mean_ms']:.2f}",
                ]
                for n in NAMES
                for p in PROFILES
            ],
        )
    )
    text.extend(
        [
            "## Measurement sensitivity\n",
            "Twenty default-hybrid queries per dataset were each repeated with active timers and "
            "disabled timers, alternating their order. Instrumentation wrappers remain installed in "
            "both cases. The paired mean difference describes timer sensitivity under changing runtime "
            "conditions; it is not an exact estimate of all instrumentation overhead.\n",
        ]
    )
    if (report / "interruption.json").exists():
        interruption = json.loads(
            (report / "interruption.json").read_text(encoding="utf-8")
        )
        text.extend(
            [
                "## Observed interruption\n",
                f"The initial LoCoMo reranked pass recorded {interruption['successful_partial_samples']} successful "
                "requests before a Redis socket read timed out during EVALSHA, the lease-release command. "
                "The configured socket timeout is 10 seconds; the complete failed request duration was not "
                "saved. The partial pass is retained in locomo_reranked_hybrid.partial_attempt_1.jsonl and is "
                "excluded from the completed-pass averages. The full LoCoMo reranked cohort was subsequently "
                "repeated with the same application settings. Already completed cohorts were reused.\n",
                "Redis responded to PING after the interruption and the container reported healthy. Persistence "
                "logs showed a completed background save, but available timing evidence does not establish it "
                "as the cause of the timeout. No service configuration was changed or service restarted. One "
                "observed failure does not establish a general failure rate. The completed-pass P95 values "
                "do not include this failed attempt; they cannot describe the full failure tail.\n",
            ]
        )
    text.append(
        table(
            [
                "Dataset",
                "Active timers mean",
                "Disabled timers mean",
                "Paired mean difference",
            ],
            [
                [
                    n,
                    f"{sum(x['True'] for x in state['calibration'][n])/20:.3f}",
                    f"{sum(x['False'] for x in state['calibration'][n])/20:.3f}",
                    f"{sum(x['True']-x['False'] for x in state['calibration'][n])/20:.3f}",
                ]
                for n in NAMES
            ],
        )
    )
    text.extend(
        [
            "## Priorities supported by the measurements\n",
            "1. For ingestion, reduce the need to copy the entire graph for each document. This would "
            "require a change to the coordinated-write design while preserving its rollback behavior; "
            "it has not been applied or validated here.\n",
            "2. For reranked retrieval, investigate scoring fewer candidate documents or batching model "
            "work. Candidate reduction can change answer quality and requires the same quality checks.\n",
            "3. For large-corpus retrieval, investigate the embedded vector search cost. A server-backed "
            "indexed vector store could change that cost, but its latency and quality have not been "
            "measured in this report.\n",
            "4. For simultaneous prompts, investigate read concurrency while maintaining consistency. "
            "The current lock covers the whole request, so extra callers mainly accumulate waiting time.\n",
            "5. Reduce sequential Redis lock/cache checks where equivalent ownership and freshness checks "
            "can be preserved. Fewer round trips could help short requests; the measured network "
            "reference does not establish the improvement of any untested change.\n",
            "## Reproduction and evidence\n",
            "Run `.venv/Scripts/python.exe scripts/profile_latency_breakdown.py --run-id NEW_RUN_ID --writes 20`, "
            "then `.venv/Scripts/python.exe scripts/build_latency_breakdown_report.py report/NEW_RUN_ID`. "
            "Use a new run ID: completed probe stores have additional documents, and their temporary "
            "graphs are cleaned up. The retained canonical stores, the pinned Git commit, model caches, "
            "optional Kuzu dependency and running FalkorDB service are required.\n",
            "Evidence: state.json contains configuration and aggregates; the nine retrieval JSONL files "
            "contain exclusive timings and command counts for every request. The three write JSONL "
            "files contain all 60 probe timings. Cold-cache and concurrent JSON files contain their "
            "individual samples. components.csv, latency.csv, commands.csv and accuracy.csv provide "
            "tabular exports. preflight.json verifies actual CUDA model providers.\n",
        ]
    )
    (report / "report.md").write_text("\n".join(text), encoding="utf-8")
    (report / "verification.json").write_text(
        json.dumps(
            dict(
                measured_retrieval_requests=queries,
                measured_writes=60,
                quality_metric_rows=len(accuracy),
                complete_cohorts=9,
                exact_rankings_and_predictions=True,
                exclusive_accounting_verified=True,
                canonical_sources_preserved=True,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figures = report / "figures"
    figures.mkdir(exist_ok=True)
    for profile in (*PROFILES, "ingestion"):
        parts = (
            [
                ("embedding", "Embedding"),
                ("vector_read", "Vector search"),
                ("reranking", "Reranking"),
                ("redis_control", "Redis commands"),
            ]
            if profile != "ingestion"
            else [
                ("embedding", "Embedding"),
                ("vector_write", "Vector write"),
                ("graph_copy", "Graph copy"),
                ("graph_query", "Graph queries"),
                ("redis_control", "Redis commands"),
                ("graph_cleanup", "Graph cleanup"),
                ("transaction_other", "Transaction/retries"),
            ]
        )
        cohorts = [
            state["cohorts"][n][profile]
            if profile != "ingestion"
            else state["ingestion_probes"][n]
            for n in NAMES
        ]
        fig, ax = plt.subplots(figsize=(10, 4.3))
        left = np.zeros(3)
        for label, title in parts:
            values = np.array([c["exclusive_mean_ms"].get(label, 0) for c in cohorts])
            ax.barh(NAMES, values, left=left, label=title)
            left += values
        other = np.array([c["total"]["mean_ms"] for c in cohorts]) - left
        ax.barh(NAMES, other, left=left, label="Other", color="#999999")
        for index, c in enumerate(cohorts):
            ax.text(
                c["total"]["mean_ms"] * 1.01,
                index,
                f"{c['total']['mean_ms']:.1f} ms",
                va="center",
                fontsize=9,
            )
        ax.set_xlim(0, max(c["total"]["mean_ms"] for c in cohorts) * 1.18)
        ax.set_xlabel("Mean measured wall time (ms)")
        ax.set_title(
            "Existing corpus: 20 write probes"
            if profile == "ingestion"
            else "Full 20% cohort: " + profile.replace("_", " ")
        )
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.21), ncol=3, frameon=False
        )
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        for extension in ("png", "pdf"):
            fig.savefig(
                figures / (profile + "." + extension), dpi=170, bbox_inches="tight"
            )
        plt.close(fig)
    print(str(report / "report.md"))


if __name__ == "__main__":
    main()
