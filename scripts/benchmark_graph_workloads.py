"""Graph-rich lookup and write-then-search checks on isolated stores."""

import argparse
import json
from pathlib import Path
import random
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def structure(work, token):
    from scripts.benchmark_graph_optimization import load_revision
    from scripts.compare_graph_latency import stats
    from memory.graph import FalkorDBGraphStore

    baseline = load_revision(
        "a0769ca", "memory/graph/falkordb_store.py", work, "structural_baseline"
    )
    before = baseline.FalkorDBGraphStore("optimization_structure_" + token)
    after = FalkorDBGraphStore(before.graph_name)
    try:
        entities = [
            dict(
                id="entity_" + str(i),
                name="Topic " + str(i),
                entity_type="Concept",
                description="",
                importance=1.0,
                created_at=100,
                updated_at=100,
            )
            for i in range(500)
        ]
        observations = [
            dict(
                id="observation_" + str(i),
                entity_id="entity_" + str(i // 3),
                source_memory_id="memory_" + str(i),
                content="Observation " + str(i),
                embedding="[]",
                valid_from=0,
                valid_until=2**63 - 1,
                importance=1.0,
                source="synthetic",
                created_at=100,
            )
            for i in range(1500)
        ]
        for label, items in (("Entity", entities), ("Observation", observations)):
            for start in range(0, len(items), 100):
                before.execute(
                    f"UNWIND $rows AS row CREATE(n:{label} {{id:row.id}}) SET n += row",
                    {"rows": items[start : start + 100]},
                )
        before.execute(
            "MATCH(o:Observation),(e:Entity) WHERE e.id=o.entity_id CREATE(o)-[:ABOUT {relevance:1.0}]->(e)"
        )
        for start in range(0, 499, 100):
            before.execute(
                "UNWIND $rows AS row MATCH(a:Entity {id:row.a}),(b:Entity {id:row.b}) CREATE(a)-[:RELATES {relation_type:'RELATED_TO',confidence:1.0,valid_from:0,valid_until:9223372036854775807,created_at:100,updated_at:100,metadata:''}]->(b)",
                {
                    "rows": [
                        dict(a="entity_" + str(i), b="entity_" + str(i + 1))
                        for i in range(start, min(start + 100, 499))
                    ]
                },
            )
        before.execute(
            "UNWIND $rows AS row MATCH(a:Observation {id:row.a}),(b:Observation {id:row.b}) CREATE(a)-[:SUPERSEDES {confidence:0.9,superseded_at:200,reason:'synthetic'}]->(b)",
            {
                "rows": [
                    dict(
                        a="observation_" + str(i * 3), b="observation_" + str(i * 3 + 1)
                    )
                    for i in range(50)
                ]
            },
        )
        seeds = ["entity_" + str(i * 25) for i in range(20)]
        owners = ["memory_" + str(i) for i in range(150)]
        operations = {
            "expansion": lambda g: g.expand_graph(
                seeds, hops=2, max_nodes=50, temporal_mode="auto"
            ),
            "conflicts": lambda g: g.get_relationship_conflicts_batch(owners),
        }
        output = {
            "type": "synthetic_structural_microbenchmark",
            "nodes": before.get_node_counts(),
            "edges": before.get_edge_counts(),
            "operations": {},
        }
        rng = random.Random(42)
        for name, operation in operations.items():
            assert operation(before) == operation(after)
            samples = {"before": [], "after": []}
            for _ in range(50):
                labels = list(samples)
                rng.shuffle(labels)
                for label in labels:
                    store = before if label == "before" else after
                    start = time.perf_counter()
                    operation(store)
                    samples[label].append((time.perf_counter() - start) * 1000)
            output["operations"][name] = {
                label: stats(values) for label, values in samples.items()
            }
            output["operations"][name]["exact_results_match"] = True
        return output
    finally:
        after.close()
        before.graph.delete()
        before.redis.delete(
            before.lock_key,
            before.revision_key,
            "{" + before.graph_name + "}:publication",
        )
        before.close()


def mixed(work, token, checkpoint=None):
    from scripts.reevaluate import initialize_runtime

    initialize_runtime(ROOT / "data/evaluation_runtime/cuda12_ort1232")
    from memory.embeddings.embedder import get_embedder
    from memory.engine import MemoryEngine
    from memory.graph import FalkorDBGraphStore
    from memory.evaluation.slices import load_slice
    from memory.evaluation.harness.evaluator import BenchmarkEvaluator
    from scripts.benchmark_graph_optimization import load_revision
    from scripts.compare_graph_latency import stats
    from scripts.migrate_kuzu_to_falkordb import import_graph

    embedder = get_embedder(use_gpu=True)
    legacy = load_revision(
        "6d10601", "memory/graph/kuzu_store.py", work, "mixed_legacy"
    )
    baseline = load_revision(
        "a0769ca", "memory/graph/falkordb_store.py", work, "mixed_baseline"
    )
    source = ROOT / "data/reevaluation/reevaluation_20261013/stores/p20/dmr"
    adapter = load_slice(
        ROOT / "data/reevaluation/reevaluation_20261013/inputs/p20/dmr", "dmr"
    )
    documents = adapter.load_documents()
    examples = adapter.load_examples()
    output = {"steps": len(examples), "documents": len(documents), "backends": {}}
    reference = None
    for label, kind in (
        ("kuzu", legacy.KuzuGraphStore),
        ("falkordb_before", baseline.FalkorDBGraphStore),
        ("falkordb_after", FalkorDBGraphStore),
    ):
        directory = work / label
        directory.mkdir()
        shutil.copytree(source / "vectors", directory / "vectors")
        if label == "kuzu":
            shutil.copy2(source / "graph.db", directory / "graph.db")
            store = kind(str(directory / "graph.db"))
            store.begin = lambda: store.conn.execute("BEGIN TRANSACTION")
            store.commit = lambda: store.conn.execute("COMMIT")
            store.rollback = lambda: store.conn.execute("ROLLBACK")
            store.finish = lambda: None
        else:
            store = kind("optimization_mixed_" + token + "_" + label)
            import_graph(source / "graph.db", store)
        try:
            with MemoryEngine(
                config={
                    "extraction_policy": "none",
                    "retrieval": {"reranker_enabled": False},
                },
                graph_store=store,
                embedder=embedder,
                qdrant_path=str(directory / "vectors"),
                use_gpu=True,
            ) as engine:
                evaluator = BenchmarkEvaluator(engine, adapter)
                evaluator.retrieve_for_example(examples[0])
                total = []
                search = []
                writes = []
                rankings = []
                for i, example in enumerate(examples):
                    start = time.perf_counter()
                    assert engine.update(documents[i].doc_id, importance=0.99)
                    written = time.perf_counter()
                    ids, _, latency = evaluator.retrieve_for_example(example)
                    writes.append((written - start) * 1000)
                    search.append(latency)
                    total.append((time.perf_counter() - start) * 1000)
                    rankings.append(ids)
                if reference is None:
                    reference = rankings
                assert rankings == reference
                output["backends"][label] = {
                    "status": "complete",
                    "write": stats(writes),
                    "search_after_write": stats(search),
                    "total": stats(total),
                    "ordered_results_match_kuzu": True,
                }
        except Exception as error:
            output["backends"][label] = dict(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                completed_steps=len(rankings),
                expected_steps=len(examples),
                write=stats(writes) if writes else None,
                search_after_write=stats(search) if search else None,
                total=stats(total) if total else None,
            )
        finally:
            if checkpoint:
                checkpoint(output)
            if label != "kuzu":
                store.graph.delete()
                store.redis.delete(
                    store.lock_key,
                    store.revision_key,
                    "{" + store.graph_name + "}:publication",
                )
            store.close()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-structure", action="store_true")
    args = parser.parse_args()
    token = uuid.uuid4().hex[:12]
    work = ROOT / "data/graph_optimization/workloads" / token
    work.mkdir(parents=True)
    output = (
        json.loads(Path(args.report).read_text(encoding="utf-8"))
        if args.skip_structure
        else {"structure": structure(work, token)}
    )
    Path(args.report).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    def checkpoint(result):
        output["mixed"] = result
        Path(args.report).write_text(
            json.dumps(output, indent=2) + "\n", encoding="utf-8"
        )

    output["mixed"] = mixed(work, token, checkpoint)
    Path(args.report).write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
