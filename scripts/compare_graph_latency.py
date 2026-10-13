"""Compare saved DMR retrieval with both backends; never modify original stores."""

import argparse
from contextlib import nullcontext
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def stats(values):
    import numpy as np

    return {
        "mean_ms": float(np.mean(values)),
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "samples": len(values),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    from scripts.reevaluate import initialize_runtime, preflight

    initialize_runtime(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    report = Path(args.report).resolve()
    report.mkdir(parents=True, exist_ok=True)
    embedder, _ = preflight(report, True)
    from memory.engine import MemoryEngine
    from memory.evaluation.slices import load_slice
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator
    from scripts.migrate_kuzu_to_falkordb import import_graph, file_hash

    token = uuid.uuid4().hex[:12]
    work = ROOT / "data/graph_latency" / token
    work.mkdir(parents=True)
    old_source = subprocess.check_output(
        [
            "git",
            "-c",
            "safe.directory=" + ROOT.as_posix(),
            "show",
            "6d10601:memory/graph/kuzu_store.py",
        ]
    )
    module_path = work / "legacy_store.py"
    module_path.write_bytes(old_source)
    spec = importlib.util.spec_from_file_location("legacy_graph_latency", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from scripts.benchmark_graph_optimization import load_revision

    initial_module = load_revision(
        "a0769ca", "memory/graph/falkordb_store.py", work, "initial_falkordb_latency"
    )
    FalkorDBGraphStore = initial_module.FalkorDBGraphStore
    source = ROOT / "data/reevaluation/reevaluation_20261013/stores/p5/dmr"
    original_hash = file_hash(source / "graph.db")
    shutil.copy2(source / "graph.db", work / "graph.db")
    shutil.copytree(source / "vectors", work / "vectors")
    legacy = module.KuzuGraphStore(db_path=str(work / "graph.db"))
    falkor = FalkorDBGraphStore("latency_" + token)
    engines = []
    try:
        imported = import_graph(source / "graph.db", falkor)
        adapter = load_slice(
            ROOT / "data/reevaluation/reevaluation_20261013/inputs/p5/dmr", "dmr"
        )
        examples = adapter.load_examples()
        engine = MemoryEngine(
            config={
                "extraction_policy": "none",
                "retrieval": {"reranker_enabled": False},
            },
            graph_store=falkor,
            embedder=embedder,
            qdrant_path=str(work / "vectors"),
            use_gpu=True,
        )
        engines.append(engine)
        output = {
            "cohort": "DMR retained 5%",
            "questions": len(examples),
            "documents": len(adapter.load_documents()),
            "rounds": args.rounds,
            "import": imported,
            "backends": {},
            "source_commit": "6d10601",
            "falkordb_revision": "a0769ca",
            "current_commit": subprocess.check_output(
                ["git", "-c", "safe.directory=" + ROOT.as_posix(), "rev-parse", "HEAD"],
                text=True,
            ).strip(),
        }
        timings = {
            label: [] for label in ["kuzu", "falkordb", "falkordb_grouped_lease"]
        }
        first = {}
        for round_id in range(-1, args.rounds):
            # Rotate order between rounds to reduce systematic warm-up/order effects.
            labels = list(timings)
            labels = labels[round_id % 3 :] + labels[: round_id % 3]
            for label in labels:
                engine.graph_store = legacy if label == "kuzu" else falkor
                evaluator = BenchmarkEvaluator(
                    engine, adapter, retrieval_mode="hybrid", k=10
                )
                records = []
                for example in examples:
                    context = (
                        falkor.write_lock
                        if label.endswith("grouped_lease")
                        else nullcontext()
                    )
                    start = time.perf_counter()
                    with context:
                        ids, _, _ = evaluator.retrieve_for_example(example)
                    elapsed = (time.perf_counter() - start) * 1000
                    if round_id >= 0:
                        timings[label].append(elapsed)
                    records.append(
                        {
                            "example_id": example.example_id,
                            "retrieved_ids": ids,
                            "recall@10": len(set(ids) & set(example.ground_truth_ids))
                            / len(set(example.ground_truth_ids)),
                            "latency_ms": elapsed,
                        }
                    )
                if round_id == 0:
                    first[label] = records
                elif round_id > 0:
                    assert [r["retrieved_ids"] for r in records] == [
                        r["retrieved_ids"] for r in first[label]
                    ]
                print(
                    json.dumps(
                        {
                            "round": round_id,
                            "backend": label,
                            "mean_ms": stats([r["latency_ms"] for r in records])[
                                "mean_ms"
                            ],
                        }
                    ),
                    flush=True,
                )
        historical = [
            json.loads(line)
            for line in (
                ROOT
                / "report/reevaluation_20261013/raw/dmr/reevaluation_20261013_p5_default_hybrid_hybrid_local.jsonl"
            )
            .read_text()
            .splitlines()
        ]
        reference = {r["example_id"]: r["retrieved_ids"] for r in historical}
        for label in timings:
            output["backends"][label] = {
                **stats(timings[label]),
                "recall@10": sum(r["recall@10"] for r in first[label]) / len(examples),
                "ordered_results_match_historical": all(
                    r["retrieved_ids"] == reference[r["example_id"]]
                    for r in first[label]
                ),
                "ordered_results_match_kuzu": [r["retrieved_ids"] for r in first[label]]
                == [r["retrieved_ids"] for r in first["kuzu"]],
            }
        # Count actual Redis commands separately, outside the timed samples.
        engine.graph_store = falkor
        execute = falkor.redis.execute_command
        for label in ["falkordb", "falkordb_grouped_lease"]:
            commands = Counter()

            def counted(*command, **kwargs):
                commands[str(command[0])] += 1
                return execute(*command, **kwargs)

            falkor.redis.execute_command = counted
            graph_execute = falkor.graph.execute_command
            falkor.graph.execute_command = counted
            try:
                evaluator = BenchmarkEvaluator(
                    engine, adapter, retrieval_mode="hybrid", k=10
                )
                for example in examples:
                    with falkor.write_lock if label.endswith(
                        "grouped_lease"
                    ) else nullcontext():
                        evaluator.retrieve_for_example(example)
            finally:
                falkor.redis.execute_command = execute
                falkor.graph.execute_command = graph_execute
            output["backends"][label]["commands_per_cohort"] = dict(commands)
        output["source_unchanged"] = file_hash(source / "graph.db") == original_hash
        assert output["source_unchanged"]
        output["graph_microbenchmark"] = graph_microbenchmark(token)
        (report / "comparison.json").write_text(
            json.dumps(output, indent=2) + "\n", encoding="utf-8"
        )
        (report / "retrieved_ids.json").write_text(
            json.dumps(first, indent=2) + "\n", encoding="utf-8"
        )
    finally:
        for engine in engines:
            engine.close()
        legacy.close()
        falkor.graph.delete()
        falkor.redis.delete(
            falkor.lock_key,
            falkor.revision_key,
            "{" + falkor.graph_name + "}:publication",
        )
        falkor.close()


def graph_microbenchmark(token):
    """Compare ten individual entity reads with one equivalent bounded batch."""
    from memory.graph import FalkorDBGraphStore
    from scripts.migrate_kuzu_to_falkordb import import_graph
    import random

    store = FalkorDBGraphStore("latency_entities_" + token)
    try:
        imported = import_graph(ROOT / "data/kuzu/memory.db", store)
        ids = [row[0] for row in store.get_entity_name_index()]
        fields = [
            "id",
            "name",
            "entity_type",
            "description",
            "importance",
            "created_at",
            "updated_at",
        ]
        query = "MATCH (e:Entity) WHERE e.id IN $ids RETURN " + ", ".join(
            "e." + field for field in fields
        )

        def individual():
            return [store.get_entity(eid) for eid in ids]

        def batched():
            rows = store.execute(query, {"ids": ids}).rows
            by_id = {row[0]: dict(zip(fields, row)) for row in rows}
            return [by_id[eid] for eid in ids]

        assert individual() == batched()
        samples = {"individual": [], "batched": []}
        rng = random.Random(42)
        for _ in range(50):
            labels = list(samples)
            rng.shuffle(labels)
            for label in labels:
                start = time.perf_counter()
                # Both implementations retain the same full-operation lease.
                with store.write_lock:
                    result = individual() if label == "individual" else batched()
                samples[label].append((time.perf_counter() - start) * 1000)
                assert len(result) == len(ids)
        profile = store.graph.profile(
            "MATCH (o:Observation) RETURN o.id, o.entity_id, o.source_memory_id"
        )
        return {
            "entity_count": len(ids),
            "samples_per_strategy": 50,
            "individual": stats(samples["individual"]),
            "batched": stats(samples["batched"]),
            "exact_entity_properties_match": True,
            "legacy_import": imported,
            "observation_inventory_server_profile": str(profile),
        }
    finally:
        store.graph.delete()
        store.redis.delete(
            store.lock_key, store.revision_key, "{" + store.graph_name + "}:publication"
        )
        store.close()


if __name__ == "__main__":
    main()
