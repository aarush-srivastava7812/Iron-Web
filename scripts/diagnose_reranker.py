"""Profile reranking and compare isolated latency/quality experiments.

Uses the unchanged evaluated application source and complete-context 20% inputs.
No live graph is needed: verified benchmark graphs contain no entities or edges.
"""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gc
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PINNED = ROOT / "data/latency_breakdown/latency_breakdown_20261014/source"
WORK = ROOT / "data/reranker_diagnosis"
REPORT = ROOT / "report/reranker_diagnosis_20261014"


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


class EmptyGraph:
    def get_entity_name_index(self):
        return []

    def expand_graph(self, *args, **kwargs):
        return [], []

    def get_relationship_conflicts_batch(self, ids):
        return {mid: [] for mid in ids}


class Capture:
    def rerank(self, query, candidates, top_k=None):
        self.candidates = deepcopy(candidates)
        return candidates


class TimingSession:
    def __init__(self, session, state):
        self.session, self.state = session, state

    def get_inputs(self):
        return self.session.get_inputs()

    def run(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return self.session.run(*args, **kwargs)
        finally:
            self.state["inference_ms"] += (time.perf_counter() - start) * 1000
            inputs = args[1]
            batch, length = inputs["input_ids"].shape
            self.state["batches"].append([int(batch), int(length)])
            self.state["padded_tokens"] += int(batch * length)
            self.state["active_tokens"] += int(inputs["attention_mask"].sum())


def instrument_model(inner):
    state = dict(
        tokenize_ms=0.0,
        input_build_ms=0.0,
        inference_ms=0.0,
        batches=[],
        padded_tokens=0,
        active_tokens=0,
    )
    for name, label in (
        ("tokenize", "tokenize_ms"),
        ("_build_onnx_input", "input_build_ms"),
    ):
        original = getattr(inner, name)

        def measured(*args, _original=original, _label=label, **kwargs):
            started = time.perf_counter()
            try:
                return _original(*args, **kwargs)
            finally:
                state[_label] += (time.perf_counter() - started) * 1000

        setattr(inner, name, measured)
    return state


def reset(state):
    state.update(
        tokenize_ms=0.0,
        input_build_ms=0.0,
        inference_ms=0.0,
        batches=[],
        padded_tokens=0,
        active_tokens=0,
    )


def run_case(case, variant, reranker, inner, session, timing):
    reset(timing)
    cap, length, batch = variant["cap"], variant["length"], variant["batch"]
    candidates = deepcopy(case["candidates"][:cap] if cap else case["candidates"])
    inner.tokenizer.enable_truncation(max_length=length)
    inner.model = TimingSession(session, timing)
    reranker.batch_size = batch
    started = time.perf_counter()
    ranked = reranker.rerank(case["query"], candidates, top_k=len(candidates))
    elapsed = (time.perf_counter() - started) * 1000
    assert all(c.get("rerank_score") is not None for c in ranked)
    return dict(
        variant=variant["name"],
        example_id=case["example_id"],
        dataset=case["dataset"],
        rerank_ms=elapsed,
        candidate_count=len(candidates),
        **deepcopy(timing),
    ), ranked


def evaluate(case, ranked, adapter, config):
    from memory.ranking.scorer import HybridScorer
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator

    ranked = HybridScorer(config).score_batch(
        ranked, case["query"], [], case["query_time"]
    )[:10]
    evaluator = BenchmarkEvaluator(None, adapter, k=10)
    prediction = None
    if case["reference"]["gold_answer"] not in (None, ""):
        prediction, _ = evaluator.generate_answer(
            case["query"], [c["text"] for c in ranked]
        )
    row = deepcopy(case["reference"])
    row.update(
        run_id="reranker_diagnosis",
        retrieved_ids=[c["memory_id"] for c in ranked],
        predicted_answer=prediction,
        retrieval_latency_ms=0,
        generation_latency_ms=0,
        total_latency_ms=0,
        error=None,
    )
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("prepare", "optimize", "pilot", "full"), default="prepare"
    )
    parser.add_argument("--variants")
    args = parser.parse_args()
    WORK.mkdir(exist_ok=True)
    REPORT.mkdir(exist_ok=True)
    sys.path.insert(0, str(PINNED))
    sys.path.insert(0, str(WORK / "runtime"))
    from scripts.reevaluate import initialize_runtime, preflight

    initialize_runtime(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    from memory.evaluation.harness.persistence import source_fingerprint
    from memory.evaluation.slices import load_slice
    from memory.retrieval.hybrid import HybridRetriever
    from memory.ranking.scorer import RetrievalConfig
    from memory.vector_store.qdrant_store import QdrantVectorStore
    from scripts.summarize_reevaluation import aggregate
    import numpy as np
    import onnxruntime as ort
    import onnx

    prior = ROOT / "report/full20_graph_analysis_20261013"
    reference = json.loads((prior / "state.json").read_text(encoding="utf-8"))
    assert source_fingerprint() == reference["source_fingerprint"]
    embedder, reranker = preflight(REPORT, True)
    inner = reranker._model.model
    model_path = Path(inner._model_dir) / inner.model_description.model_file
    config = RetrievalConfig(use_reranker=True)
    cases, adapters = [], {}
    for name in ("dmr", "locomo", "longmemeval"):
        job = reference["jobs"][name]
        adapters[name] = load_slice(Path(job["input"]).parent, name)
        assert (
            hashlib.sha256(Path(job["input"]).read_bytes()).hexdigest() == job["sha256"]
        )
        cache = WORK / (name + "_cases.json")
        if cache.exists():
            dataset_cases = json.loads(cache.read_text(encoding="utf-8"))
        else:
            target = WORK / name / "vectors"
            if not target.exists():
                shutil.copytree(
                    ROOT
                    / "data/graph_full_analysis/full20_graph_20261013/retrieval"
                    / name
                    / "vectors",
                    target,
                )
            store = QdrantVectorStore(
                str(target), collection_name="semantic_memory", embedder=embedder
            )
            assert store.count() == job["documents"]
            capture = Capture()
            retriever = HybridRetriever(embedder, store, EmptyGraph(), capture, config)
            refs = {
                r["example_id"]: r
                for r in map(
                    json.loads,
                    (prior / "raw" / f"{name}_reranked_hybrid_falkordb_after.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines(),
                )
            }
            dataset_cases = []
            try:
                for example in adapters[name].load_examples():
                    capture.candidates = []
                    retriever.retrieve(
                        example.query,
                        k=10,
                        query_time=example.query_time,
                        document_ids=example.metadata.get("corpus_ids"),
                    )
                    dataset_cases.append(
                        dict(
                            dataset=name,
                            example_id=example.example_id,
                            query=example.query,
                            query_time=example.query_time,
                            candidates=capture.candidates,
                            reference=refs[example.example_id],
                        )
                    )
            finally:
                store.close()
            dump(cache, dataset_cases)
        assert len(dataset_cases) == job["questions"]
        cases.extend(dataset_cases)
    variants = {
        "baseline": dict(
            name="baseline", cap=0, length=512, batch=16, precision="fp32"
        ),
        "batch8": dict(name="batch8", cap=0, length=512, batch=8, precision="fp32"),
        "batch32": dict(name="batch32", cap=0, length=512, batch=32, precision="fp32"),
        "cap20": dict(name="cap20", cap=20, length=512, batch=16, precision="fp32"),
        "cap40": dict(name="cap40", cap=40, length=512, batch=16, precision="fp32"),
        "length256": dict(
            name="length256", cap=0, length=256, batch=16, precision="fp32"
        ),
    }
    if args.phase == "optimize":
        sys.path.insert(0, str(Path(ort.__file__).parent / "transformers"))
        from optimizer import optimize_model

        optimized = optimize_model(
            str(model_path),
            model_type="bert",
            num_heads=12,
            hidden_size=768,
            opt_level=0,
            use_gpu=True,
        )
        statistics = optimized.get_fused_operator_statistics()
        optimized.convert_float_to_float16(keep_io_types=True)
        optimized.save_model_to_file(str(WORK / "model_fp16_optimized.onnx"))
        dump(
            REPORT / "optimizer.json",
            dict(
                fused_operators=statistics,
                conversion="ONNX Runtime transformer optimizer with symbolic shape inference",
                output_bytes=(WORK / "model_fp16_optimized.onnx").stat().st_size,
            ),
        )
        print(
            json.dumps(dict(event="optimized", fused_operators=statistics)), flush=True
        )
        return
    variants["fp16_optimized"] = dict(
        name="fp16_optimized", cap=0, length=512, batch=16, precision="fp16_optimized"
    )
    if args.phase == "prepare":
        model = onnx.load(str(model_path), load_external_data=False)
        counts = Counter(
            onnx.TensorProto.DataType.Name(t.data_type) for t in model.graph.initializer
        )
        inspection = dict(
            model_path=str(model_path),
            weights_bytes=model_path.stat().st_size,
            initializer_types=dict(counts),
            parameter_elements=sum(
                int(np.prod(t.dims)) for t in model.graph.initializer
            ),
            node_types=dict(Counter(n.op_type for n in model.graph.node)),
            tokenizer_truncation=inner.tokenizer.truncation,
            tokenizer_padding=inner.tokenizer.padding,
            packages=dict(onnx=onnx.__version__),
            source_fingerprint=source_fingerprint(),
            cases=len(cases),
            variants=variants,
        )
        dump(REPORT / "model_graph.json", inspection)
        del model
        gc.collect()
        # Operator placement profiling uses a small batch and is excluded from
        # latency comparisons. CPU node durations are not GPU kernel timings.
        options = ort.SessionOptions()
        options.enable_profiling = True
        options.profile_file_prefix = str(WORK / "onnx_profile")
        profiling = ort.InferenceSession(
            str(model_path),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            sess_options=options,
        )
        selected = cases[0]
        tokens = inner.tokenize(
            [(selected["query"], c["text"]) for c in selected["candidates"][:2]]
        )
        inputs = inner._build_onnx_input(tokens)
        for _ in range(3):
            profiling.run(None, inputs)
        profile_path = profiling.end_profiling()
        events = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        nodes = [
            e
            for e in events
            if e.get("cat") == "Node" and e.get("args", {}).get("provider")
        ]
        providers, operators = (
            defaultdict(lambda: dict(events=0, host_duration_us=0)),
            defaultdict(lambda: dict(events=0, host_duration_us=0)),
        )
        for event in nodes:
            arg = event["args"]
            for key, destination in (
                (arg["provider"], providers),
                (arg["provider"] + ":" + arg.get("op_name", ""), operators),
            ):
                destination[key]["events"] += 1
                destination[key]["host_duration_us"] += event.get("dur", 0)
        dump(
            REPORT / "operator_profile.json",
            dict(
                providers=dict(providers),
                operators=dict(operators),
                raw_profile=str(profile_path),
                input_shape=list(inputs["input_ids"].shape),
                limitation="Host node trace durations; no CUPTI GPU kernel timing",
            ),
        )
        print(
            json.dumps(
                dict(
                    event="prepared",
                    cases=len(cases),
                    initializer_types=inspection["initializer_types"],
                    providers=dict(providers),
                )
            ),
            flush=True,
        )
        return
    timing = instrument_model(inner)
    original = inner.model
    session = original
    if args.phase == "pilot":
        selected = []
        for name in ("dmr", "locomo", "longmemeval"):
            group = [c for c in cases if c["dataset"] == name]
            selected.extend(group[i * len(group) // 8] for i in range(8))
        requested = args.variants.split(",") if args.variants else list(variants)
    else:
        selected = cases
        requested = (args.variants or "baseline,cap20,fp16_optimized").split(",")
    if not set(requested).issubset(variants):
        parser.error("Unknown variant; validated FP16 experiments use fp16_optimized")
    summary_path = REPORT / f"{args.phase}_summary.json"
    results = (
        json.loads(summary_path.read_text(encoding="utf-8"))
        if summary_path.exists()
        else {}
    )
    # Evaluate all FP32 experiments before swapping the session to FP16, freeing
    # GPU arena allocations instead of keeping two large inference sessions live.
    for precision in ("fp32", "fp16_optimized"):
        active = [
            variants[name]
            for name in requested
            if variants[name]["precision"] == precision
        ]
        if not active:
            continue
        if precision == "fp32":
            session = original
        else:
            inner.model = None
            original = None
            session = None
            gc.collect()
            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session = ort.InferenceSession(
                str(WORK / ("model_" + precision + ".onnx")),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                sess_options=options,
            )
            assert session.get_providers()[0] == "CUDAExecutionProvider"
        for variant in active:
            print(
                json.dumps(
                    dict(event="variant_started", phase=args.phase, variant=variant)
                ),
                flush=True,
            )
            raw_path = REPORT / f"{args.phase}_{variant['name']}.jsonl"
            if (
                raw_path.exists()
                and args.phase == "full"
                and results.get(variant["name"], {}).get("status") == "complete"
            ):
                assert sum(1 for _ in raw_path.open(encoding="utf-8")) == len(selected)
                print(
                    json.dumps(
                        dict(event="reuse_saved_variant", variant=variant["name"])
                    ),
                    flush=True,
                )
                continue
            measurements, evaluations = [], defaultdict(list)
            try:
                for warm in selected[:2]:
                    run_case(warm, variant, reranker, inner, session, timing)
                with raw_path.open("w", encoding="utf-8", newline="\n") as log:
                    order = list(selected)
                    random.Random(91).shuffle(order)
                    for index, case in enumerate(order):
                        row, ranked = run_case(
                            case, variant, reranker, inner, session, timing
                        )
                        evaluation = evaluate(
                            case, ranked, adapters[case["dataset"]], config
                        )
                        row["retrieved_ids"] = evaluation["retrieved_ids"]
                        row["predicted_answer"] = evaluation["predicted_answer"]
                        row["rerank_scores"] = {
                            c["memory_id"]: c["rerank_score"] for c in ranked
                        }
                        row["ranking_matches_previous"] = (
                            row["retrieved_ids"] == case["reference"]["retrieved_ids"]
                        )
                        if variant["name"] == "baseline":
                            assert (
                                row["ranking_matches_previous"]
                                and row["predicted_answer"]
                                == case["reference"]["predicted_answer"]
                            )
                        row["other_ms"] = (
                            row["rerank_ms"]
                            - row["tokenize_ms"]
                            - row["input_build_ms"]
                            - row["inference_ms"]
                        )
                        assert row["other_ms"] >= -0.01
                        measurements.append(row)
                        evaluations[case["dataset"]].append(evaluation)
                        log.write(json.dumps(row) + "\n")
                        log.flush()
                        if (index + 1) % 25 == 0:
                            try:
                                gpu = subprocess.check_output(
                                    [
                                        "nvidia-smi",
                                        "--query-gpu=temperature.gpu,clocks.sm,power.draw,memory.used,utilization.gpu",
                                        "--format=csv,noheader,nounits",
                                    ],
                                    text=True,
                                ).strip()
                                with (REPORT / f"{args.phase}_telemetry.jsonl").open(
                                    "a", encoding="utf-8", newline="\n"
                                ) as telemetry:
                                    telemetry.write(
                                        json.dumps(
                                            dict(
                                                variant=variant["name"],
                                                done=index + 1,
                                                temperature_clock_power_memory_utilization=gpu,
                                            )
                                        )
                                        + "\n"
                                    )
                            except Exception:
                                pass
                            print(
                                json.dumps(
                                    dict(
                                        event="progress",
                                        phase=args.phase,
                                        variant=variant["name"],
                                        done=index + 1,
                                        total=len(order),
                                    )
                                ),
                                flush=True,
                            )
                results[variant["name"]] = dict(
                    status="complete", settings=variant, datasets={}
                )
                for name in ("dmr", "locomo", "longmemeval"):
                    rows = [r for r in measurements if r["dataset"] == name]
                    results[variant["name"]]["datasets"][name] = dict(
                        samples=len(rows),
                        mean_ms=float(np.mean([r["rerank_ms"] for r in rows])),
                        p95_ms=float(np.percentile([r["rerank_ms"] for r in rows], 95)),
                        component_mean_ms={
                            k: float(np.mean([r[k] for r in rows]))
                            for k in (
                                "tokenize_ms",
                                "input_build_ms",
                                "inference_ms",
                                "other_ms",
                            )
                        },
                        exact_rankings=sum(r["ranking_matches_previous"] for r in rows),
                        mean_batches=float(np.mean([len(r["batches"]) for r in rows])),
                        mean_padded_tokens=float(
                            np.mean([r["padded_tokens"] for r in rows])
                        ),
                        mean_active_tokens=float(
                            np.mean([r["active_tokens"] for r in rows])
                        ),
                        quality=aggregate(evaluations[name], adapters[name]),
                    )
            except Exception as error:
                results[variant["name"]] = dict(
                    status="failed",
                    error_type=type(error).__name__,
                    error=str(error),
                    settings=variant,
                )
                print(
                    json.dumps(
                        dict(
                            event="variant_failed",
                            variant=variant["name"],
                            error=str(error),
                        )
                    ),
                    flush=True,
                )
                if args.phase == "full":
                    raise
            dump(REPORT / f"{args.phase}_summary.json", results)
            print(
                json.dumps(
                    dict(
                        event="variant_complete",
                        variant=variant["name"],
                        status=results[variant["name"]]["status"],
                        mean_ms={
                            n: r["mean_ms"]
                            for n, r in results[variant["name"]]
                            .get("datasets", {})
                            .items()
                        },
                    )
                ),
                flush=True,
            )
    print(json.dumps(dict(event="complete", phase=args.phase)), flush=True)


if __name__ == "__main__":
    main()
