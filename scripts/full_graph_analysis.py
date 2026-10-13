"""Full retained 20% graph comparison with fresh API ingestion and local metrics."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def prepare(work, timestamp):
    from memory.evaluation.harness.runner import BenchmarkRunner
    from memory.evaluation.slices import validate_slice
    from memory.evaluation.harness.persistence import fingerprint

    jobs = {}
    for name in ("dmr", "locomo", "longmemeval"):
        if name != "longmemeval":
            source = (
                ROOT
                / "data/reevaluation/reevaluation_20261013/inputs/p20"
                / name
                / (name + ".json")
            )
            payload = json.loads(source.read_text(encoding="utf-8"))
        else:
            adapter = BenchmarkRunner.ADAPTER_REGISTRY[name]()
            frozen = json.loads(
                (
                    ROOT / "data/official_upstream/slices/longmemeval_20percent.json"
                ).read_text(encoding="utf-8")
            )
            by_id = {e.example_id: e for e in adapter.load_examples()}
            examples = [by_id[e["example_id"]] for e in frozen["examples"]]
            ids = set().union(
                *(
                    set(e.metadata["corpus_ids"]) | set(e.ground_truth_ids)
                    for e in examples
                )
            )
            payload = dict(
                benchmark=name,
                profile="complete_context_v2",
                selection=dict(
                    nominal_percent=20,
                    source_examples=500,
                    selected_examples=len(examples),
                    rule="retained_frozen_question_ids",
                ),
                documents=[
                    asdict(d) for d in adapter.load_documents() if d.doc_id in ids
                ],
                examples=[asdict(e) for e in examples],
            )
        validate_slice(payload)
        # Use one run timestamp only where the original source omits time.
        for doc in payload["documents"]:
            if doc.get("timestamp") is None:
                doc["timestamp"] = timestamp
        for example in payload["examples"]:
            if example.get("query_time") is None:
                example["query_time"] = timestamp
        target = work / "inputs" / name / (name + ".json")
        if target.exists():
            assert json.loads(target.read_text(encoding="utf-8")) == payload
        else:
            dump(target, payload)
        dump(
            target.parent / "manifest.json",
            dict(
                schema_version=2,
                slices={name: dict(path=target.name, fingerprint=fingerprint(payload))},
            ),
        )
        jobs[name] = dict(
            input=str(target),
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            questions=len(payload["examples"]),
            documents=len(payload["documents"]),
            text_characters=sum(len(d["text"]) for d in payload["documents"]),
        )
    return jobs


def attach_legacy_transactions(store):
    store.begin = lambda: store.conn.execute("BEGIN TRANSACTION")
    store.commit = lambda: store.conn.execute("COMMIT")
    store.rollback = lambda: store.conn.execute("ROLLBACK")
    store.finish = lambda: None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--phase", choices=["ingestion", "retrieval", "all"], default="all"
    )
    args = parser.parse_args()
    if not all(c.isalnum() or c in "_.-" for c in args.run_id):
        parser.error("Invalid run ID")
    report = Path(args.report).resolve()
    report.mkdir(parents=True, exist_ok=True)
    work = ROOT / "data/graph_full_analysis" / args.run_id
    work.mkdir(parents=True, exist_ok=True)
    state_path = report / "state.json"
    from memory.evaluation.harness.persistence import source_fingerprint

    current_source = source_fingerprint()
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert (
            state["source_fingerprint"] == current_source
        ), "Source changed; use a new run ID."
    else:
        state = dict(
            run_id=args.run_id,
            timestamp=int(time.time()),
            source_fingerprint=current_source,
            commit=subprocess.check_output(
                ["git", "-c", "safe.directory=" + ROOT.as_posix(), "rev-parse", "HEAD"],
                text=True,
            ).strip(),
            ingestion={},
            retrieval={},
            protocol="local_retrieval_v2",
            generator="first_context_line",
            reference_policy="identical_canonical_corpus_and_vectors",
        )
    jobs = prepare(work, state["timestamp"])
    state["jobs"] = jobs
    dump(state_path, state)
    from scripts.reevaluate import initialize_runtime, preflight

    initialize_runtime(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    embedder, reranker = preflight(report, True)
    from scripts.benchmark_graph_optimization import load_revision, rss_samples
    from scripts.compare_graph_latency import stats
    from scripts.summarize_reevaluation import aggregate
    from scripts.migrate_kuzu_to_falkordb import import_graph, file_hash
    from memory.graph import FalkorDBGraphStore
    from memory.engine import MemoryEngine
    from memory.evaluation.slices import load_slice
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator

    legacy = load_revision("6d10601", "memory/graph/kuzu_store.py", work, "full_legacy")
    before = load_revision(
        "a0769ca", "memory/graph/falkordb_store.py", work, "full_before"
    )
    kinds = {
        "kuzu": legacy.KuzuGraphStore,
        "falkordb_before": before.FalkorDBGraphStore,
        "falkordb_after": FalkorDBGraphStore,
    }
    for name in ("dmr", "locomo", "longmemeval"):
        adapter = load_slice(Path(jobs[name]["input"]).parent, name)
        documents = adapter.load_documents()
        examples = adapter.load_examples()
        if args.phase in ("ingestion", "all"):
            state["ingestion"].setdefault(name, {})
            for label, kind in kinds.items():
                if label in state["ingestion"][name]:
                    continue
                directory = work / "ingestion" / name / label
                directory.mkdir(parents=True, exist_ok=True)
                graph_name = args.run_id + "_ingest_" + name + "_" + label
                store = (
                    kind(str(directory / "graph.db"))
                    if label == "kuzu"
                    else kind(graph_name)
                )
                if label == "kuzu":
                    attach_legacy_transactions(store)
                engine = None
                latencies = []
                failed = []
                start = time.perf_counter()
                log_path = report / "ingestion" / (name + "_" + label + ".jsonl")
                log_path.parent.mkdir(exist_ok=True)
                try:
                    engine = MemoryEngine(
                        config={"extraction_policy": "none"},
                        graph_store=store,
                        embedder=embedder,
                        qdrant_path=str(directory / "vectors"),
                        use_gpu=True,
                    )
                    original = engine.add
                    with log_path.open("a", encoding="utf-8") as log:

                        def measured_add(*values, **kwargs):
                            t0 = time.perf_counter()
                            try:
                                result = original(*values, **kwargs)
                                elapsed = (time.perf_counter() - t0) * 1000
                                latencies.append(elapsed)
                                log.write(
                                    json.dumps(
                                        dict(
                                            document_id=result,
                                            latency_ms=elapsed,
                                            success=True,
                                        )
                                    )
                                    + "\n"
                                )
                                log.flush()
                                if len(latencies) % 100 == 0:
                                    print(
                                        json.dumps(
                                            dict(
                                                event="ingest_progress",
                                                benchmark=name,
                                                backend=label,
                                                completed=len(latencies),
                                                elapsed_sec=time.perf_counter() - start,
                                            )
                                        ),
                                        flush=True,
                                    )
                                return result
                            except Exception as error:
                                failed.append(
                                    dict(
                                        error_type=type(error).__name__,
                                        error=str(error),
                                        latency_ms=(time.perf_counter() - t0) * 1000,
                                    )
                                )
                                log.write(
                                    json.dumps(dict(success=False, **failed[-1])) + "\n"
                                )
                                log.flush()
                                raise

                        engine.add = measured_add
                        evaluator = BenchmarkEvaluator(engine, adapter)
                        with rss_samples() as memory:
                            result = evaluator.ingest_documents(
                                documents, show_progress=False
                            )
                    result.update(
                        status="complete",
                        latency=stats(latencies),
                        p99_ms=__import__("numpy").percentile(latencies, 99).item(),
                        failures=len(failed),
                        peak_process_rss_mb=max(memory),
                        node_counts=store.get_node_counts(),
                        vector_records=engine.vector_store.count(),
                        directory=str(directory),
                        graph_name=graph_name,
                    )
                    assert result["node_counts"]["Observation"] == len(documents)
                    assert result["vector_records"] == len(documents)
                except Exception as error:
                    result = dict(
                        status="failed",
                        error_type=type(error).__name__,
                        error=str(error),
                        completed_documents=store.get_node_counts()["Observation"],
                        total_documents=len(documents),
                        wall_sec=time.perf_counter() - start,
                        successful_add_latency=stats(latencies) if latencies else None,
                        failures=failed,
                        directory=str(directory),
                        graph_name=graph_name,
                    )
                finally:
                    if engine:
                        engine.close()
                    store.close()
                state["ingestion"][name][label] = result
                dump(state_path, state)
                print(
                    json.dumps(
                        dict(
                            event="ingestion_complete",
                            benchmark=name,
                            backend=label,
                            result=result,
                        )
                    ),
                    flush=True,
                )
        if args.phase == "ingestion":
            continue
        # DMR and LoCoMo reuse the verified saved complete-context canonical stores.
        canonical = (
            (ROOT / "data/reevaluation/reevaluation_20261013/stores/p20" / name)
            if name != "longmemeval"
            else work / "ingestion" / name / "kuzu"
        )
        assert canonical.exists(), "Canonical corpus must be ingested first."
        source_hash = file_hash(canonical / "graph.db")
        read_dir = work / "retrieval" / name
        read_dir.mkdir(parents=True, exist_ok=True)
        if not (read_dir / "vectors").exists():
            shutil.copytree(canonical / "vectors", read_dir / "vectors")
        if not (read_dir / "graph.db").exists():
            shutil.copy2(canonical / "graph.db", read_dir / "graph.db")
        old_store = legacy.KuzuGraphStore(str(read_dir / "graph.db"))
        graph_name = args.run_id + "_read_" + name
        before_store = before.FalkorDBGraphStore(graph_name)
        after_store = FalkorDBGraphStore(graph_name)
        engine = None
        try:
            # Import with the current bounded persistence retry into an empty graph.
            imported = import_graph(canonical / "graph.db", after_store)
            state.setdefault("canonical_imports", {})[name] = imported
            engine = MemoryEngine(
                config={
                    "extraction_policy": "none",
                    "retrieval": {"reranker_enabled": False},
                },
                graph_store=after_store,
                embedder=embedder,
                reranker=reranker,
                qdrant_path=str(read_dir / "vectors"),
                use_gpu=True,
            )
            stores = {
                "kuzu": old_store,
                "falkordb_before": before_store,
                "falkordb_after": after_store,
            }
            state["retrieval"].setdefault(name, {})
            for profile, mode, rerank in (
                ("vector", "vector", False),
                ("default_hybrid", "hybrid", False),
                ("reranked_hybrid", "hybrid", True),
            ):
                state["retrieval"][name].setdefault(profile, {})
                reference = None
                for label in kinds:
                    raw_path = (
                        report / "raw" / (name + "_" + profile + "_" + label + ".jsonl")
                    )
                    raw_path.parent.mkdir(exist_ok=True)
                    if label in state["retrieval"][name][profile]:
                        prior = [
                            json.loads(line)
                            for line in raw_path.read_text(
                                encoding="utf-8"
                            ).splitlines()
                        ]
                        if reference is None:
                            reference = {
                                r["example_id"]: (
                                    r["retrieved_ids"],
                                    r["predicted_answer"],
                                )
                                for r in prior
                            }
                        continue
                    engine.graph_store = stores[label]
                    engine.config_data["retrieval"]["reranker_enabled"] = rerank
                    evaluator = BenchmarkEvaluator(
                        engine, adapter, retrieval_mode=mode, k=10
                    )
                    for example in examples[:3]:
                        evaluator.evaluate_example(example, args.run_id)
                    rows = []
                    start = time.perf_counter()
                    with rss_samples() as memory, raw_path.open(
                        "w", encoding="utf-8"
                    ) as log:
                        for i, example in enumerate(examples):
                            result = evaluator.evaluate_example(example, args.run_id)
                            row = asdict(result)
                            rows.append(row)
                            log.write(json.dumps(row, ensure_ascii=False) + "\n")
                            log.flush()
                            if (i + 1) % 25 == 0:
                                print(
                                    json.dumps(
                                        dict(
                                            event="retrieval_progress",
                                            benchmark=name,
                                            profile=profile,
                                            backend=label,
                                            completed=i + 1,
                                            elapsed_sec=time.perf_counter() - start,
                                        )
                                    ),
                                    flush=True,
                                )
                    wall = time.perf_counter() - start
                    metrics = aggregate(rows, adapter)
                    rankings = {
                        r["example_id"]: (r["retrieved_ids"], r["predicted_answer"])
                        for r in rows
                    }
                    if reference is None:
                        reference = rankings
                    matched = rankings == reference
                    metrics.update(
                        wall_sec=wall,
                        requests_per_sec=len(rows) / wall,
                        peak_process_rss_mb=max(memory),
                        ordered_results_and_answers_match_kuzu=matched,
                    )
                    assert matched, (
                        name,
                        profile,
                        label,
                        "ranking or answer regression",
                    )
                    assert metrics["failed_examples"] == 0
                    state["retrieval"][name][profile][label] = metrics
                    dump(state_path, state)
                    print(
                        json.dumps(
                            dict(
                                event="retrieval_complete",
                                benchmark=name,
                                profile=profile,
                                backend=label,
                                result=metrics,
                            )
                        ),
                        flush=True,
                    )
            assert file_hash(canonical / "graph.db") == source_hash
        finally:
            if engine:
                engine.close()
            old_store.close()
            before_store.close()
            after_store.close()
    dump(state_path, state)


if __name__ == "__main__":
    main()
