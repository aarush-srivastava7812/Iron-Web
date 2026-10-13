"""Measure warmed storage RSS in a fresh process without neural model loading."""

import argparse
import json
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "backend", choices=["kuzu", "falkordb_before", "falkordb_after"]
    )
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--benchmark", choices=["dmr", "locomo", "longmemeval"], default="dmr"
    )
    parser.add_argument("--graph-name")
    args = parser.parse_args()
    import psutil
    from scripts.benchmark_graph_optimization import load_revision
    from scripts.migrate_kuzu_to_falkordb import import_graph
    from memory.graph import FalkorDBGraphStore
    from memory.vector_store.qdrant_store import QdrantVectorStore

    token = uuid.uuid4().hex[:12]
    work = ROOT / "data/graph_optimization/memory" / token
    work.mkdir(parents=True)
    source = (
        (
            ROOT
            / "data/graph_full_analysis/full20_graph_20261013/ingestion/longmemeval/kuzu"
        )
        if args.benchmark == "longmemeval"
        else ROOT
        / "data/reevaluation/reevaluation_20261013/stores/p20"
        / args.benchmark
    )
    shutil.copytree(source / "vectors", work / "vectors")
    if args.backend == "kuzu":
        kind = load_revision(
            "6d10601", "memory/graph/kuzu_store.py", work, "legacy_memory"
        ).KuzuGraphStore
        shutil.copy2(source / "graph.db", work / "graph.db")
    elif args.backend == "falkordb_before":
        kind = load_revision(
            "a0769ca", "memory/graph/falkordb_store.py", work, "baseline_memory"
        ).FalkorDBGraphStore
    else:
        kind = FalkorDBGraphStore
    process = psutil.Process()
    before = process.memory_info().rss
    store = (
        kind(str(work / "graph.db"))
        if args.backend == "kuzu"
        else kind(args.graph_name or "optimization_memory_" + token)
    )
    vector = None
    try:
        if args.backend != "kuzu" and not args.graph_name:
            import_graph(source / "graph.db", store)
        vector = QdrantVectorStore(
            path=str(work / "vectors"), collection_name="semantic_memory"
        )
        store.get_node_counts()
        store.get_entity_name_index()
        store.get_relationship_conflicts_batch(["memory_probe"])
        vector.count()
        time.sleep(0.1)
        after = process.memory_info().rss
        result = dict(
            benchmark=args.benchmark,
            backend=args.backend,
            protocol="storage_only_no_neural_models",
            process_baseline_rss_mb=before / 1024**2,
            process_warm_rss_mb=after / 1024**2,
            process_rss_increase_mb=(after - before) / 1024**2,
            vector_records=vector.count(),
            graph_nodes=store.get_node_counts(),
        )
        if args.backend != "kuzu":
            result["server_graph_memory_bytes"] = store.redis.memory_usage(
                store.graph_name
            )
        Path(args.report).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result), flush=True)
    finally:
        if vector:
            vector.close()
        if args.backend != "kuzu" and not args.graph_name:
            store.graph.delete()
            store.redis.delete(
                store.lock_key,
                store.revision_key,
                "{" + store.graph_name + "}:publication",
            )
        store.close()


if __name__ == "__main__":
    main()
