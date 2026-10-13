"""Controlled retained-cohort benchmarks for Kuzu and both FalkorDB revisions."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Event, Thread
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def load_revision(revision, path, work, name):
    data = subprocess.check_output(
        [
            "git",
            "-c",
            "safe.directory=" + ROOT.as_posix(),
            "show",
            revision + ":" + path,
        ]
    )
    target = work / (name + ".py")
    target.write_bytes(data)
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def rss_samples():
    import psutil

    process = psutil.Process()
    samples = []
    stop = Event()

    def sample():
        while not stop.is_set():
            samples.append(process.memory_info().rss / 1024**2)
            stop.wait(0.05)

    thread = Thread(target=sample, daemon=True)
    thread.start()
    try:
        yield samples
    finally:
        stop.set()
        thread.join()


def summarize(rows, wall):
    import numpy as np

    latencies = [r.retrieval_latency_ms for r in rows]
    keys = sorted({key for row in rows for key in row.retrieval_metrics})
    metrics = {
        key: float(
            np.mean(
                [
                    row.retrieval_metrics[key]
                    for row in rows
                    if key in row.retrieval_metrics
                ]
            )
        )
        for key in keys
    }
    return dict(
        queries=len(rows),
        retrieval_scored_queries=sum(bool(row.retrieval_metrics) for row in rows),
        retrieval=metrics,
        mean_ms=float(np.mean(latencies)),
        p50_ms=float(np.percentile(latencies, 50)),
        p95_ms=float(np.percentile(latencies, 95)),
        wall_sec=wall,
        requests_per_sec=len(rows) / wall,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--resume-completed-cohorts", action="store_true")
    args = parser.parse_args()
    report = Path(args.report).resolve()
    report.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    work = ROOT / "data/graph_optimization" / token
    work.mkdir(parents=True)
    from scripts.reevaluate import initialize_runtime, preflight

    initialize_runtime(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    embedder, _ = preflight(report, True)
    from memory.engine import MemoryEngine
    from memory.graph import FalkorDBGraphStore
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator
    from memory.evaluation.slices import load_slice
    from scripts.migrate_kuzu_to_falkordb import import_graph, file_hash

    old = load_revision("6d10601", "memory/graph/kuzu_store.py", work, "old_graph")
    baseline = load_revision(
        "a0769ca", "memory/graph/falkordb_store.py", work, "baseline_graph"
    )
    records = {
        "run_token": token,
        "legacy_revision": "6d10601",
        "falkordb_baseline_revision": "a0769ca",
        "cohorts": {},
        "ingestion": {},
        "notes": [
            "RSS includes shared GPU model host memory and all live stores; not isolated per-backend memory.",
            "End-to-end measurements include application lease and queue waits.",
        ],
    }
    if args.resume_completed_cohorts and (report / "comparison.json").exists():
        records = json.loads((report / "comparison.json").read_text())
        records["resumed_tokens"] = records.get("resumed_tokens", []) + [token]
    records["optimization_revision"] = subprocess.check_output(
        ["git", "-c", "safe.directory=" + ROOT.as_posix(), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    records["rounds"] = args.rounds
    for benchmark in ("dmr", "locomo"):
        source = ROOT / "data/reevaluation/reevaluation_20261013/stores/p20" / benchmark
        original_hash = file_hash(source / "graph.db")
        if benchmark in records["cohorts"]:
            assert (
                records["cohorts"][benchmark]["import"]["source_sha256"]
                == original_hash
            )
            continue
        directory = work / benchmark
        directory.mkdir()
        shutil.copy2(source / "graph.db", directory / "graph.db")
        shutil.copytree(source / "vectors", directory / "vectors")
        legacy = old.KuzuGraphStore(str(directory / "graph.db"))
        graph_name = "optimization_" + token + "_" + benchmark
        unoptimized = baseline.FalkorDBGraphStore(graph_name)
        optimized = FalkorDBGraphStore(graph_name)
        engine = None
        try:
            imported = import_graph(source / "graph.db", unoptimized)
            adapter = load_slice(
                ROOT / "data/reevaluation/reevaluation_20261013/inputs/p20" / benchmark,
                benchmark,
            )
            examples = adapter.load_examples()
            engine = MemoryEngine(
                config={
                    "extraction_policy": "none",
                    "retrieval": {"reranker_enabled": False},
                },
                graph_store=optimized,
                embedder=embedder,
                qdrant_path=str(directory / "vectors"),
                use_gpu=True,
            )
            stores = {
                "kuzu": legacy,
                "falkordb_before": unoptimized,
                "falkordb_after": optimized,
            }
            rows = {label: [] for label in stores}
            rss = {label: [] for label in stores}
            walls = Counter()
            for round_id in range(-1, args.rounds):
                labels = list(stores)
                labels = (
                    labels[round_id % len(labels) :] + labels[: round_id % len(labels)]
                )
                for label in labels:
                    engine.graph_store = stores[label]
                    evaluator = BenchmarkEvaluator(
                        engine, adapter, retrieval_mode="hybrid", k=10
                    )
                    start = time.perf_counter()
                    with rss_samples() as samples:
                        current = [
                            evaluator.evaluate_example(example, token)
                            for example in examples
                        ]
                    elapsed = time.perf_counter() - start
                    if round_id >= 0:
                        rows[label].extend(current)
                        rss[label].extend(samples)
                        walls[label] += elapsed
                    print(
                        json.dumps(
                            dict(
                                event="retrieval",
                                benchmark=benchmark,
                                round=round_id,
                                backend=label,
                                **summarize(current, elapsed),
                            )
                        ),
                        flush=True,
                    )
            historical = {
                row["example_id"]: row["retrieved_ids"]
                for row in [
                    json.loads(line)
                    for line in (
                        ROOT
                        / "report/reevaluation_20261013/raw"
                        / benchmark
                        / (
                            "reevaluation_20261013_p20_default_hybrid_hybrid_local.jsonl"
                        )
                    )
                    .read_text()
                    .splitlines()
                ]
            }
            cohort = {
                "questions": len(examples),
                "documents": len(adapter.load_documents()),
                "import": imported,
                "sequential": {},
                "concurrent": {},
            }
            for label in stores:
                summary = summarize(rows[label], walls[label])
                summary["ordered_results_match_historical"] = all(
                    row.retrieved_ids == historical[row.example_id]
                    for row in rows[label]
                )
                summary["process_peak_rss_mb"] = max(rss[label])
                assert summary["ordered_results_match_historical"]
                cohort["sequential"][label] = summary
                write(
                    report / (benchmark + "_" + label + "_raw.json"),
                    [asdict(row) for row in rows[label]],
                )
            # One shared engine reflects the application lock and shared-graph lease.
            if benchmark == "dmr":
                for workers in (1, 4, 8):
                    cohort["concurrent"][str(workers)] = {}
                    for label in stores:
                        engine.graph_store = stores[label]
                        evaluator = BenchmarkEvaluator(
                            engine, adapter, retrieval_mode="hybrid", k=10
                        )
                        start = time.perf_counter()
                        with ThreadPoolExecutor(max_workers=workers) as pool:
                            current = list(
                                pool.map(
                                    lambda ex: evaluator.evaluate_example(ex, token),
                                    examples,
                                )
                            )
                        summary = summarize(current, time.perf_counter() - start)
                        summary["ordered_results_match_historical"] = all(
                            row.retrieved_ids == historical[row.example_id]
                            for row in current
                        )
                        assert summary["ordered_results_match_historical"]
                        cohort["concurrent"][str(workers)][label] = summary
                        print(
                            json.dumps(
                                dict(
                                    event="concurrent",
                                    workers=workers,
                                    backend=label,
                                    **summary,
                                )
                            ),
                            flush=True,
                        )
            cohort["source_unchanged"] = file_hash(source / "graph.db") == original_hash
            assert cohort["source_unchanged"]
            records["cohorts"][benchmark] = cohort
            write(report / "comparison.json", records)
        finally:
            if engine:
                engine.close()
            legacy.close()
            optimized.close()
            unoptimized.graph.delete()
            unoptimized.redis.delete(
                unoptimized.lock_key,
                unoptimized.revision_key,
                "{" + graph_name + "}:publication",
            )
            unoptimized.close()
    # Fresh ingestion on all 500 DMR documents, including source timestamps/metadata.
    adapter = load_slice(
        ROOT / "data/reevaluation/reevaluation_20261013/inputs/p20/dmr", "dmr"
    )
    for label, kind in (
        ("kuzu", old.KuzuGraphStore),
        ("falkordb_before", baseline.FalkorDBGraphStore),
        ("falkordb_after", FalkorDBGraphStore),
    ):
        if label in records["ingestion"]:
            continue
        directory = work / ("ingest_" + label)
        directory.mkdir()
        store = (
            kind(str(directory / "graph.db"))
            if label == "kuzu"
            else kind("optimization_ingest_" + token + "_" + label)
        )
        if label == "kuzu":
            store.begin = lambda: store.conn.execute("BEGIN TRANSACTION")
            store.commit = lambda: store.conn.execute("COMMIT")
            store.rollback = lambda: store.conn.execute("ROLLBACK")
            store.finish = lambda: None
        started = time.perf_counter()
        try:
            with MemoryEngine(
                config={"extraction_policy": "none"},
                graph_store=store,
                embedder=embedder,
                qdrant_path=str(directory / "vectors"),
                use_gpu=True,
            ) as engine:
                evaluator = BenchmarkEvaluator(engine, adapter)
                with rss_samples() as samples:
                    ingestion = evaluator.ingest_documents(
                        adapter.load_documents(), show_progress=False
                    )
                ingestion["process_peak_rss_mb"] = max(samples)
                ingestion["node_counts"] = store.get_node_counts()
                records["ingestion"][label] = ingestion
                print(
                    json.dumps(dict(event="ingestion", backend=label, **ingestion)),
                    flush=True,
                )
                write(report / "comparison.json", records)
        except Exception as error:
            records["ingestion"][label] = dict(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                wall_sec=time.perf_counter() - started,
                node_counts=store.get_node_counts(),
            )
            write(report / "comparison.json", records)
            print(
                json.dumps(
                    dict(
                        event="ingestion_failed",
                        backend=label,
                        **records["ingestion"][label],
                    )
                ),
                flush=True,
            )
        finally:
            if label != "kuzu":
                store.graph.delete()
                store.redis.delete(
                    store.lock_key,
                    store.revision_key,
                    "{" + store.graph_name + "}:publication",
                )
            store.close()


if __name__ == "__main__":
    main()
