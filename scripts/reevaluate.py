"""Reevaluate retained question cohorts with real models and current metric definitions.

Historical inputs/results are read only. New stores and complete-context inputs live
under data/reevaluation; reproducible run records live under the report directory.
"""

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DLL_HANDLES = []


def initialize_runtime(directory):
    directory = Path(directory).resolve()
    if directory.exists():
        sys.path.insert(0, str(directory))
        dll_roots = [directory, directory.parent / "cuda12_extra"]
        for dll_directory in sorted(
            {
                dll.parent
                for dll_root in dll_roots
                for dll in dll_root.glob("nvidia/*/bin/*.dll")
            }
        ):
            DLL_HANDLES.append(os.add_dll_directory(str(dll_directory)))
            os.environ["PATH"] = (
                str(dll_directory) + os.pathsep + os.environ.get("PATH", "")
            )
        # Keep the inherited dependency environment intact; only this process
        # selects the isolated CUDA 12 ONNX Runtime wheel.
    from memory.device import ensure_cuda_dlls_loaded

    ensure_cuda_dlls_loaded()


def write_json(path, value):
    from memory.evaluation.harness.persistence import write_atomic

    write_atomic(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_inputs(destination):
    from memory.evaluation.harness.runner import BenchmarkRunner
    from memory.evaluation.harness.persistence import fingerprint
    from memory.evaluation.slices import validate_slice

    plan = []
    frozen_root = ROOT / "data/official_upstream/slices"
    manifest = json.loads(
        (frozen_root / "freeze_manifest.json").read_text(encoding="utf-8")
    )
    for benchmark in ("locomo", "dmr", "longmemeval"):
        path = frozen_root / f"{benchmark}_20percent.json"
        if sha256(path) != manifest["slices"][benchmark]["sha256"]:
            raise ValueError(f"Historical slice hash differs: {benchmark}")
        frozen = json.loads(path.read_text(encoding="utf-8"))
        adapter = BenchmarkRunner.ADAPTER_REGISTRY[benchmark]()
        documents, examples = adapter.load_documents(), adapter.load_examples()
        by_id = {example.example_id: example for example in examples}
        for percent in (5, 20):
            if percent == 20 and benchmark == "longmemeval":
                continue
            count = (
                math.floor(len(examples) * 0.05)
                if percent == 5
                else len(frozen["examples"])
            )
            selected = [by_id[e["example_id"]] for e in frozen["examples"][:count]]
            if benchmark == "dmr":
                # One MSC question owns five session documents. Retain all
                # sessions for each selected conversation, with cross-conversation
                # distractors inside the cohort (no per-query corpus filter).
                prefixes = {
                    e.example_id.rsplit(":qa", 1)[0] + ":session:" for e in selected
                }
                selected_docs = [
                    d
                    for d in documents
                    if any(d.doc_id.startswith(p) for p in prefixes)
                ]
            else:
                needed = set().union(
                    *(
                        set(e.metadata["corpus_ids"]) | set(e.ground_truth_ids)
                        for e in selected
                    )
                )
                selected_docs = [d for d in documents if d.doc_id in needed]
            payload = dict(
                benchmark=benchmark,
                profile="complete_context_v2",
                selection=dict(
                    nominal_percent=percent,
                    source_examples=len(examples),
                    selected_examples=count,
                    actual_fraction=count / len(examples),
                    rule="historical_frozen_question_ids_in_release_order",
                    historical_slice_sha256=sha256(path),
                ),
                documents=[asdict(d) for d in selected_docs],
                examples=[asdict(e) for e in selected],
            )
            validate_slice(payload)
            directory = destination / f"p{percent}" / benchmark
            input_path = directory / f"{benchmark}.json"
            directory.mkdir(parents=True, exist_ok=True)
            if input_path.exists():
                if json.loads(input_path.read_text(encoding="utf-8")) != payload:
                    raise ValueError(
                        "Prepared evaluation input differs; choose a new run ID."
                    )
            else:
                write_json(input_path, payload)
            write_json(
                directory / "manifest.json",
                dict(
                    schema_version=2,
                    slices={
                        benchmark: dict(
                            path=input_path.name,
                            fingerprint=fingerprint(payload),
                            documents=len(selected_docs),
                            examples=count,
                        )
                    },
                ),
            )
            old_doc_ids = {d["doc_id"] for d in frozen["documents"]}
            plan.append(
                dict(
                    benchmark=benchmark,
                    percent=percent,
                    questions=count,
                    documents=len(selected_docs),
                    old_documents=len(old_doc_ids),
                    added_context_documents=sum(
                        d.doc_id not in old_doc_ids for d in selected_docs
                    ),
                    selected_evidence_outside_old_corpus=sum(
                        bool(set(e.ground_truth_ids) - old_doc_ids) for e in selected
                    ),
                    slice_directory=str(directory),
                    input_sha256=sha256(input_path),
                )
            )
    return sorted(
        plan,
        key=lambda job: (
            job["percent"],
            ("locomo", "dmr", "longmemeval").index(job["benchmark"]),
        ),
    )


class Telemetry:
    def __init__(self):
        self.samples = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.collect, daemon=True)

    def collect(self):
        from memory.device import query_vram_telemetry

        while not self.stop.is_set():
            total, used, free = query_vram_telemetry()
            self.samples.append(
                dict(time=time.time(), total_mb=total, used_mb=used, free_mb=free)
            )
            self.stop.wait(2)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=5)


def preflight(report, use_gpu):
    import numpy as np
    import onnxruntime as ort
    from memory.embeddings.embedder import get_embedder
    from memory.ranking.reranker import get_reranker
    from memory.device import inspect_device_status

    t0 = time.perf_counter()
    embedder = get_embedder(use_gpu=use_gpu)
    reranker = get_reranker(use_gpu=use_gpu)
    vectors = embedder.embed(
        ["Paris is the capital of France.", "Lima is the capital of Peru."]
    )
    ranked = reranker.rerank(
        "Capital of France",
        [
            dict(memory_id="paris", text="Paris is the capital of France."),
            dict(memory_id="lima", text="Lima is the capital of Peru."),
        ],
    )
    if (
        vectors.shape != (2, 384)
        or not np.isfinite(vectors).all()
        or ranked[0]["memory_id"] != "paris"
    ):
        raise RuntimeError("Real model preflight returned invalid outputs.")
    device = inspect_device_status(use_gpu, embedder, reranker).model_dump()
    if use_gpu and (
        device["embedder_provider"] != "CUDAExecutionProvider"
        or device["reranker_provider"] != "CUDAExecutionProvider"
    ):
        raise RuntimeError(f"GPU preflight requires actual CUDA sessions: {device}")
    packages = {}
    for name in (
        "fastembed",
        "qdrant-client",
        "falkordb",
        "numpy",
        "nvidia-cublas-cu12",
        "nvidia-cudnn-cu12",
    ):
        packages[name] = importlib.metadata.version(name)
    write_json(
        report / "preflight.json",
        dict(
            device=device,
            packages=packages,
            onnxruntime_version=ort.__version__,
            onnxruntime_path=ort.__file__,
            model_load_and_check_sec=time.perf_counter() - t0,
            checks=dict(
                embedding_shape=list(vectors.shape),
                ranked_ids=[r["memory_id"] for r in ranked],
            ),
        ),
    )
    return embedder, reranker


def run_matrix(options):
    from memory.engine import MemoryEngine
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator
    from memory.evaluation.harness.runner import BenchmarkRunner
    from memory.evaluation.slices import load_slice

    report = Path(options.report).resolve()
    report.mkdir(parents=True, exist_ok=True)
    data = ROOT / "data/reevaluation" / options.run_id
    plan = prepare_inputs(data / "inputs")
    write_json(report / "input_plan.json", plan)
    print(json.dumps(dict(event="prepared", jobs=plan)), flush=True)
    if options.prepare_only:
        return
    embedder, reranker = preflight(report, not options.cpu)
    print(json.dumps(dict(event="real_model_preflight_passed")), flush=True)
    original = BenchmarkEvaluator.evaluate_example
    progress = dict(completed=0, benchmark=None, profile=None, percent=None)

    def evaluate_with_progress(self, example, run_id):
        result = original(self, example, run_id)
        progress["completed"] += 1
        if progress["completed"] % 10 == 0:
            print(json.dumps(dict(event="queries", **progress)), flush=True)
        return result

    BenchmarkEvaluator.evaluate_example = evaluate_with_progress
    completed = []
    profiles = [
        ("vector", "vector", False),
        ("default_hybrid", "hybrid", False),
        ("reranked_hybrid", "hybrid", True),
    ]
    try:
        for job in plan:
            adapter = load_slice(job["slice_directory"], job["benchmark"])
            store = data / "stores" / f'p{job["percent"]}' / job["benchmark"]
            for profile, mode, enabled in profiles:
                run_id = f'{options.run_id}_p{job["percent"]}_{profile}'
                progress.update(
                    completed=0,
                    benchmark=job["benchmark"],
                    profile=profile,
                    percent=job["percent"],
                )
                print(
                    json.dumps(
                        dict(
                            event="start",
                            **progress,
                            documents=job["documents"],
                            questions=job["questions"],
                        )
                    ),
                    flush=True,
                )
                runner = BenchmarkRunner(str(report / "raw"), run_id)
                t0 = time.perf_counter()
                with Telemetry() as telemetry:
                    with MemoryEngine(
                        config={
                            "extraction_policy": "none",
                            "retrieval": {"reranker_enabled": enabled},
                        },
                        embedder=embedder,
                        reranker=reranker if enabled else None,
                        qdrant_path=str(store / "vectors"),
                        graph_name="reevaluation_"
                        + options.run_id
                        + "_p"
                        + str(job["percent"])
                        + "_"
                        + job["benchmark"],
                        use_gpu=not options.cpu,
                    ) as engine:
                        # Models are exercised by preflight; record query latency
                        # separately from ingestion and the full per-profile wall time.
                        summary = runner.run_benchmark(
                            job["benchmark"],
                            engine,
                            adapter=adapter,
                            retrieval_mode=mode,
                            k=10,
                        )
                        graph_counts = dict(
                            nodes=engine.graph_store.get_node_counts(),
                            edges=engine.graph_store.get_edge_counts(),
                        )
                record = dict(
                    job=job,
                    profile=profile,
                    summary=summary,
                    graph_counts=graph_counts,
                    telemetry=telemetry.samples,
                    wall_time_sec=time.perf_counter() - t0,
                )
                write_json(
                    report / f'p{job["percent"]}_{job["benchmark"]}_{profile}.json',
                    record,
                )
                completed.append(record)
                write_json(report / "matrix.json", completed)
                print(
                    json.dumps(
                        dict(
                            event="complete",
                            benchmark=job["benchmark"],
                            percent=job["percent"],
                            profile=profile,
                            evaluation=summary["evaluation"],
                        )
                    ),
                    flush=True,
                )
    finally:
        BenchmarkEvaluator.evaluate_example = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--runtime", default=str(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    )
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    options = parser.parse_args()
    if not all(c.isalnum() or c in "_.-" for c in options.run_id):
        parser.error(
            "Run ID must use only letters, digits, underscores, dots or hyphens."
        )
    if not options.prepare_only:
        initialize_runtime(options.runtime)
    run_matrix(options)


if __name__ == "__main__":
    main()
