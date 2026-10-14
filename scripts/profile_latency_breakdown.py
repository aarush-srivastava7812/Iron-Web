"""Attribute latency on the evaluated 20% corpora without editing live code.

The application and existing benchmark helpers are loaded from a committed Git
archive. Only copied vector stores and run-owned FalkorDB graphs are written.
Nested spans report exclusive wall time; command time is not pure network time.
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict
from functools import wraps
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = "2035c7ece628d777aed0a184ffe73865a59acf2e"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def summary(values):
    import numpy as np

    return dict(
        samples=len(values),
        mean_ms=float(np.mean(values)),
        p50_ms=float(np.percentile(values, 50)),
        p95_ms=float(np.percentile(values, 95)),
        max_ms=float(max(values)),
    )


class Recorder:
    """Thread-local nested wall-clock spans with no double-counted components."""

    def __init__(self):
        self.local = threading.local()
        self.enabled = True

    @contextmanager
    def request(self, kind):
        if getattr(self.local, "state", None) is not None:
            raise RuntimeError("Nested request recording")
        state = dict(
            kind=kind,
            components_ms=defaultdict(float),
            inclusive_ms=defaultdict(float),
            calls=Counter(),
            commands=[],
            stack=[],
        )
        self.local.state = state
        started = time.perf_counter()
        try:
            yield state
        finally:
            total = (time.perf_counter() - started) * 1000
            state["total_ms"] = total
            accounted = sum(state["components_ms"].values())
            state["components_ms"]["application_other"] += total - accounted
            assert abs(sum(state["components_ms"].values()) - total) < 1e-6
            assert all(v >= -1e-6 for v in state["components_ms"].values())
            state.pop("stack")
            self.local.state = None
            self.local.last = state

    @contextmanager
    def span(self, label):
        state = getattr(self.local, "state", None)
        if state is None or not self.enabled:
            yield
            return
        frame = [time.perf_counter(), 0.0]
        state["stack"].append(frame)
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - frame[0]) * 1000
            state["stack"].pop()
            if state["stack"]:
                state["stack"][-1][1] += elapsed
            state["components_ms"][label] += elapsed - frame[1]
            state["inclusive_ms"][label] += elapsed
            state["calls"][label] += 1

    def wrap(self, obj, name, label):
        original = getattr(obj, name)

        @wraps(original)
        def measured(*args, **kwargs):
            state = getattr(self.local, "state", None)
            if state is not None and self.enabled and label == "reranking":
                candidates = args[1] if len(args) > 1 else kwargs["candidates"]
                state["rerank_candidates"] = len(candidates)
                state["rerank_input_characters"] = sum(
                    len(c.get("text", "")) for c in candidates
                )
            with self.span(label):
                return original(*args, **kwargs)

        setattr(obj, name, measured)

    def command(self, original):
        @wraps(original)
        def measured(*args, **kwargs):
            name = str(args[0]).upper()
            label = (
                "graph_copy"
                if name == "GRAPH.COPY"
                else "graph_query"
                if name in {"GRAPH.QUERY", "GRAPH.RO_QUERY"}
                else "graph_cleanup"
                if name == "GRAPH.DELETE"
                else "redis_control"
            )
            state = getattr(self.local, "state", None)
            started = time.perf_counter()
            error = None
            result = None
            try:
                with self.span(label):
                    result = original(*args, **kwargs)
                return result
            except Exception as exc:
                error = type(exc).__name__
                raise
            finally:
                if state is not None and self.enabled:
                    event = dict(
                        command=name,
                        wall_ms=(time.perf_counter() - started) * 1000,
                        error=error,
                    )
                    # Read server statistics from the raw response. Never retain
                    # query text, tokens, credentials, or command arguments.
                    if name in {"GRAPH.QUERY", "GRAPH.RO_QUERY"} and isinstance(
                        result, list
                    ):
                        for statistic in result[-1]:
                            text = (
                                statistic.decode()
                                if isinstance(statistic, bytes)
                                else str(statistic)
                            )
                            if text.startswith("Query internal execution time:"):
                                event["server_execution_ms"] = float(
                                    text.split(":", 1)[1].split()[0]
                                )
                    state["commands"].append(event)

        return measured


class TimedMutex:
    def __init__(self, inner, recorder):
        self.inner, self.recorder = inner, recorder

    def acquire(self, *args, **kwargs):
        with self.recorder.span("local_lock_wait"):
            return self.inner.acquire(*args, **kwargs)

    def release(self):
        return self.inner.release()


def instrument(recorder, graph, engine, embedder, reranker):
    recorder.wrap(embedder, "embed_single", "embedding")
    recorder.wrap(reranker, "rerank", "reranking")
    for name in ("search", "get_memory"):
        recorder.wrap(engine.vector_store, name, "vector_read")
    recorder.wrap(engine.vector_store, "upsert_memory", "vector_write")
    recorder.wrap(graph, "execute", "graph_client")
    for name in ("begin", "commit", "finish"):
        recorder.wrap(graph, name, "transaction_other")
    graph.write_lock.mutex = TimedMutex(graph.write_lock.mutex, recorder)
    graph.redis.execute_command = recorder.command(graph.redis.execute_command)
    # FalkorDB also binds the original Redis method on its own client object.
    # Future graph objects bind that method rather than Redis directly.
    graph.db.execute_command = graph.redis.execute_command
    original_select = graph.db.select_graph

    def select(name):
        selected = original_select(name)
        # The SDK binds execute_command when each graph object is created.
        # It already binds the wrapped Redis method, so do not wrap it twice.
        recorder.wrap(selected, "query", "graph_sdk_decode")
        return selected

    graph.db.select_graph = select
    graph.graph.execute_command = graph.redis.execute_command
    recorder.wrap(graph.graph, "query", "graph_sdk_decode")
    return original_select


def aggregate_spans(rows):
    labels = sorted(set().union(*(r["components_ms"] for r in rows)))
    means = {
        label: sum(r["components_ms"].get(label, 0) for r in rows) / len(rows)
        for label in labels
    }
    command_names = sorted({c["command"] for r in rows for c in r["commands"]})
    commands = {}
    for name in command_names:
        events = [c for r in rows for c in r["commands"] if c["command"] == name]
        commands[name] = dict(
            count=len(events),
            per_request=len(events) / len(rows),
            **summary([c["wall_ms"] for c in events]),
        )
        server = [
            c["server_execution_ms"] for c in events if "server_execution_ms" in c
        ]
        if server:
            commands[name]["server_execution"] = summary(server)
            commands[name]["wall_minus_server"] = summary(
                [
                    c["wall_ms"] - c["server_execution_ms"]
                    for c in events
                    if "server_execution_ms" in c
                ]
            )
    return dict(
        total=summary([r["total_ms"] for r in rows]),
        exclusive_mean_ms=means,
        command_statistics=commands,
        accounting_error_ms=max(
            abs(sum(r["components_ms"].values()) - r["total_ms"]) for r in rows
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="latency_breakdown_20261014")
    parser.add_argument("--writes", type=int, default=20)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Smoke check only; zero runs every question",
    )
    parser.add_argument("--skip-rerank", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed checkpoints; rerun incomplete profiles",
    )
    args = parser.parse_args()
    if not args.run_id.replace("_", "").isalnum() or args.writes < 1 or args.limit < 0:
        parser.error("Invalid run options")
    report = ROOT / "report" / args.run_id
    work = ROOT / "data/latency_breakdown" / args.run_id
    if ((report / "state.json").exists() or work.exists()) and not args.resume:
        parser.error(
            "Run ID already exists; select a new run ID to use clean copied stores"
        )
    if args.resume and not (report / "state.json").exists():
        parser.error("Resume requires an existing state.json checkpoint")
    report.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    isolated = work / "source"
    if not isolated.exists():
        archive = subprocess.check_output(
            [
                "git",
                "-c",
                "safe.directory=" + ROOT.as_posix(),
                "archive",
                "--format=zip",
                REVISION,
                "memory",
                "scripts",
                "config.yaml",
            ]
        )
        isolated.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for entry in bundle.infolist():
                if (
                    not (isolated / entry.filename)
                    .resolve()
                    .is_relative_to(isolated.resolve())
                ):
                    raise ValueError("Archive path leaves isolated source")
            bundle.extractall(isolated)
    sys.path.insert(0, str(isolated))
    from scripts.reevaluate import initialize_runtime, preflight

    initialize_runtime(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    from memory.evaluation.harness.persistence import source_fingerprint
    from scripts.migrate_kuzu_to_falkordb import import_graph
    from scripts.summarize_reevaluation import aggregate
    from memory.evaluation.slices import load_slice
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator
    from memory.engine import MemoryEngine
    from memory.graph import FalkorDBGraphStore
    from memory.graph.connection import GraphLease

    old_report = ROOT / "report/full20_graph_analysis_20261013"
    reference = json.loads((old_report / "state.json").read_text(encoding="utf-8"))
    assert source_fingerprint() == reference["source_fingerprint"]
    embedder, reranker = preflight(report, True)
    state = dict(
        revision=REVISION,
        application_fingerprint=source_fingerprint(),
        prior_report=str(old_report),
        options=vars(args),
        cohorts={},
        ingestion_probes={},
        concurrency={},
        source_files={},
        preserved_sources={},
    )
    if args.resume:
        state = json.loads((report / "state.json").read_text(encoding="utf-8"))
        assert (
            state["revision"] == REVISION
            and state["application_fingerprint"] == source_fingerprint()
        )
        for key in ("writes", "limit", "skip_rerank"):
            assert state["options"][key] == getattr(args, key)
        assert not state.get("complete"), "Completed runs require a new run ID"
        state["resumed"] = True
    recorder = Recorder()
    # Instrument special methods on their isolated class; Python does not consult
    # instance attributes for with-statement special method lookup.
    original_enter, original_exit = GraphLease.__enter__, GraphLease.__exit__

    def enter(lease):
        with recorder.span("lease_python"):
            return original_enter(lease)

    def leave(lease, *exc):
        with recorder.span("lease_python"):
            return original_exit(lease, *exc)

    GraphLease.__enter__, GraphLease.__exit__ = enter, leave
    wrapped_models = False
    for name in ("dmr", "locomo", "longmemeval"):
        if name in state["ingestion_probes"] and state["preserved_sources"].get(name):
            print(
                json.dumps(dict(event="reuse_completed_dataset", dataset=name)),
                flush=True,
            )
            continue
        job = reference["jobs"][name]
        source_input = Path(job["input"])
        assert digest(source_input) == job["sha256"]
        adapter = load_slice(source_input.parent, name)
        examples = adapter.load_examples()
        if args.limit:
            examples = examples[: args.limit]
        canonical = (
            ROOT / "data/graph_full_analysis/full20_graph_20261013/retrieval" / name
        )
        source_hash = digest(canonical / "graph.db")
        source_dir = work / name
        source_dir.mkdir(exist_ok=True)
        if not (source_dir / "vectors").exists():
            shutil.copytree(canonical / "vectors", source_dir / "vectors")
        graph_name = args.run_id + "_" + name
        graph = FalkorDBGraphStore(graph_name)
        engine = None
        try:
            imported = import_graph(canonical / "graph.db", graph)
            engine = MemoryEngine(
                config={
                    "extraction_policy": "none",
                    "retrieval": {"reranker_enabled": False},
                },
                graph_store=graph,
                embedder=embedder,
                reranker=reranker,
                qdrant_path=str(source_dir / "vectors"),
                use_gpu=True,
            )
            assert (
                engine.vector_store.count() == job["documents"]
            ), "Copied corpus has incomplete write probes; use a new run ID"
            # Models are shared across cohorts and must only be wrapped once.
            if wrapped_models:
                saved_embed, saved_rank = embedder.embed_single, reranker.rerank
            instrument(recorder, graph, engine, embedder, reranker)
            if wrapped_models:
                embedder.embed_single, reranker.rerank = saved_embed, saved_rank
            wrapped_models = True
            recorder.enabled = True
            pings = []
            for _ in range(110):
                start = time.perf_counter()
                graph.redis.ping()
                pings.append((time.perf_counter() - start) * 1000)
            state.setdefault("ping", {})[name] = summary(pings[10:])
            state["source_files"][name] = dict(
                input_sha256=job["sha256"],
                graph_sha256=source_hash,
                import_result=imported,
            )
            state["cohorts"].setdefault(name, {})
            for profile, mode, rerank in (
                ("vector", "vector", False),
                ("default_hybrid", "hybrid", False),
                ("reranked_hybrid", "hybrid", True),
            ):
                if args.skip_rerank and rerank:
                    continue
                if profile in state["cohorts"][name]:
                    print(
                        json.dumps(
                            dict(
                                event="reuse_completed_profile",
                                dataset=name,
                                profile=profile,
                            )
                        ),
                        flush=True,
                    )
                    continue
                engine.config_data["retrieval"]["reranker_enabled"] = rerank
                evaluator = BenchmarkEvaluator(
                    engine, adapter, retrieval_mode=mode, k=10
                )
                for example in examples[:3]:
                    evaluator.evaluate_example(example, args.run_id)
                reference_rows = {
                    r["example_id"]: r
                    for r in map(
                        json.loads,
                        (old_report / "raw" / f"{name}_{profile}_falkordb_after.jsonl")
                        .read_text(encoding="utf-8")
                        .splitlines(),
                    )
                }
                rows, evaluations = [], []
                raw = report / f"{name}_{profile}.jsonl"
                if raw.exists():
                    partial = raw.with_name(raw.stem + ".partial_attempt_1.jsonl")
                    assert (
                        not partial.exists()
                    ), "Preserve earlier attempts before retrying again"
                    raw.rename(partial)
                with raw.open("w", encoding="utf-8") as log:
                    for index, example in enumerate(examples):
                        # The evaluator also performs generation/scoring. Wrap
                        # only search so those stay outside request time.
                        original_search = engine.search

                        def recorded_search(*a, **kw):
                            with recorder.request("retrieval"):
                                return original_search(*a, **kw)

                        engine.search = recorded_search
                        try:
                            result = evaluator.evaluate_example(example, args.run_id)
                        finally:
                            engine.search = original_search
                        row = recorder.local.last
                        row["example_id"] = example.example_id
                        row["returned_ids_match"] = (
                            result.retrieved_ids
                            == reference_rows[example.example_id]["retrieved_ids"]
                        )
                        row["prediction_match"] = (
                            result.predicted_answer
                            == reference_rows[example.example_id]["predicted_answer"]
                        )
                        assert (
                            row["returned_ids_match"]
                            and row["prediction_match"]
                            and not result.error
                        )
                        rows.append(row)
                        evaluations.append(asdict(result))
                        log.write(json.dumps(row) + "\n")
                        log.flush()
                        if (index + 1) % 25 == 0:
                            print(
                                json.dumps(
                                    dict(
                                        event="retrieval_progress",
                                        dataset=name,
                                        profile=profile,
                                        done=index + 1,
                                        total=len(examples),
                                    )
                                ),
                                flush=True,
                            )
                metrics = aggregate(evaluations, adapter)
                cohort = dict(
                    **aggregate_spans(rows),
                    metrics=metrics,
                    exact_outputs_match=True,
                    questions=len(examples),
                    documents=job["documents"],
                )
                if not args.limit:
                    previous = aggregate(list(reference_rows.values()), adapter)
                    for group in ("retrieval", "answer"):
                        assert metrics[group] == previous[group], (name, profile, group)
                state["cohorts"][name][profile] = cohort
                dump(report / "state.json", state)
                print(
                    json.dumps(
                        dict(
                            event="retrieval_complete",
                            dataset=name,
                            profile=profile,
                            components=cohort["exclusive_mean_ms"],
                            total=cohort["total"],
                        )
                    ),
                    flush=True,
                )

            engine.config_data["retrieval"]["reranker_enabled"] = False
            # Quantify instrumentation sensitivity with alternating on/off order.
            pairs = []
            for index in range(min(20, len(examples))):
                example = examples[index]
                timings = {}
                ids = []
                for enabled in (True, False) if index % 2 else (False, True):
                    recorder.enabled = enabled
                    with recorder.request("calibration") as row:
                        result = engine.search(
                            example.query,
                            k=10,
                            query_time=example.query_time,
                            document_ids=example.metadata.get("corpus_ids"),
                        )
                    timings[str(enabled)] = row["total_ms"]
                    ids.append([r.memory_id for r in result])
                assert ids[0] == ids[1]
                pairs.append(timings)
            recorder.enabled = True
            state.setdefault("calibration", {})[name] = pairs

            # Cold cache is measured separately from the warm full-cohort passes.
            cold = []
            for example in examples[:10]:
                graph.invalidate_entity_name_index()
                with recorder.request("cold_cache") as row:
                    engine.search(
                        example.query,
                        k=10,
                        query_time=example.query_time,
                        document_ids=example.metadata.get("corpus_ids"),
                    )
                cold.append(row)
            dump(report / f"{name}_cold_cache.json", cold)
            state.setdefault("cold_cache", {})[name] = aggregate_spans(cold)

            if name != "locomo" and not args.limit:
                state["concurrency"][name] = {}
                for workers in (4, 8):

                    def search_one(example):
                        with recorder.request("concurrent_retrieval") as row:
                            result = engine.search(
                                example.query,
                                k=10,
                                query_time=example.query_time,
                                document_ids=example.metadata.get("corpus_ids"),
                            )
                        assert [
                            r.memory_id for r in result
                        ] == reference_rows_for_hybrid[example.example_id]
                        return row

                    reference_rows_for_hybrid = {
                        r["example_id"]: r["retrieved_ids"]
                        for r in map(
                            json.loads,
                            (
                                old_report
                                / "raw"
                                / f"{name}_default_hybrid_falkordb_after.jsonl"
                            )
                            .read_text(encoding="utf-8")
                            .splitlines(),
                        )
                    }
                    start = time.perf_counter()
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        concurrent_rows = list(pool.map(search_one, examples))
                    wall = time.perf_counter() - start
                    state["concurrency"][name][str(workers)] = dict(
                        **aggregate_spans(concurrent_rows),
                        wall_sec=wall,
                        requests_per_sec=len(concurrent_rows) / wall,
                        exact_outputs_match=True,
                    )
                    dump(report / f"{name}_concurrent_{workers}.json", concurrent_rows)

            # Existing complete 20% corpus, a bounded number of new documents:
            # this measures steady-state writes, not full fresh ingestion time.
            documents = adapter.load_documents()
            write_rows = []
            with (report / f"{name}_writes.jsonl").open("w", encoding="utf-8") as log:
                for index in range(args.writes):
                    doc = documents[index * len(documents) // args.writes]
                    mid = args.run_id + ":probe:" + name + ":" + str(index)
                    with recorder.request("ingestion_probe") as row:
                        added = engine.add(
                            doc.text,
                            memory_id=mid,
                            timestamp=doc.timestamp,
                            valid_from=doc.valid_from,
                            valid_until=doc.valid_until,
                            metadata=doc.metadata,
                        )
                    assert added == mid and engine.get(mid).content == doc.text
                    row["probe_index"], row["text_characters"] = index, len(doc.text)
                    names = Counter(c["command"] for c in row["commands"])
                    assert names["GRAPH.COPY"] >= 1 and names["GRAPH.QUERY"] >= 1
                    assert (
                        names["GRAPH.DELETE"] == 1
                    ), "Graph command instrumentation incomplete"
                    write_rows.append(row)
                    log.write(json.dumps(row) + "\n")
                    log.flush()
                assert engine.vector_store.count() == job["documents"] + args.writes
            state["ingestion_probes"][name] = dict(
                **aggregate_spans(write_rows),
                starting_documents=job["documents"],
                writes=args.writes,
                exact_readback=True,
            )
            assert digest(canonical / "graph.db") == source_hash
            assert digest(source_input) == job["sha256"]
            state["preserved_sources"][name] = True
            dump(report / "state.json", state)
            print(
                json.dumps(
                    dict(
                        event="dataset_complete",
                        dataset=name,
                        write_components=state["ingestion_probes"][name][
                            "exclusive_mean_ms"
                        ],
                    )
                ),
                flush=True,
            )
        finally:
            if engine:
                engine.close()
            # Delete only this run's isolated graph namespace, including retained
            # staging/rollback copies. Leave every other graph untouched.
            from falkordb import FalkorDB

            cleanup = FalkorDB(host="localhost", port=6379)
            owned = [
                g
                for g in cleanup.list_graphs()
                if g == graph_name
                or g.startswith(graph_name + ":")
                or g.startswith("{" + graph_name + "}:")
            ]
            for owned_name in owned:
                cleanup.select_graph(owned_name).delete()
            cleanup.close()
            graph.close()
    state["complete"] = True
    dump(report / "state.json", state)
    print(json.dumps(dict(event="complete", report=str(report))), flush=True)


if __name__ == "__main__":
    main()
