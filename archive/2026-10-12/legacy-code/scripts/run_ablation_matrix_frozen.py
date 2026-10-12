"""Ablation matrix on the FROZEN official upstream slices.

Differences from run_ablations_phase7.py:
- Documents and questions come from the frozen slice JSONs, verified against
  data/official_upstream/slices/freeze_manifest.json (SHA-256).  This makes the
  matrix directly comparable with the official upstream benchmark numbers.
- Extraction goes through CachedNIMExtractor (real NIM, disk-cached), so the
  graph is populated with real entity edges and later modes never re-hit the API.
- Fixed run_id "frozen_v1" makes runs resumable across sessions.

Modes: no_memory, vector, graph, hybrid_no_rerank, hybrid_no_graph,
hybrid_no_temporal, hybrid.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from memory.engine import MemoryEngine
from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
)
from memory.evaluation.harness import BenchmarkRunner

SLICES_DIR = ROOT / "data" / "official_upstream" / "slices"
MODES = [
    "no_memory",           # Baseline A
    "vector",              # Baseline B
    "graph",               # Baseline C
    "hybrid_no_rerank",    # Variant D: vector + graph, no reranker
    "hybrid_no_graph",     # Vector + reranker, no graph
    "hybrid_no_temporal",  # Full, no temporal filtering
    "hybrid",              # Variant E: full proposed architecture
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_frozen_slice(bench: str) -> Dict[str, Any]:
    """Load a frozen slice and verify its hash against the freeze manifest."""
    manifest_path = SLICES_DIR / "freeze_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("freeze_manifest.json missing - run freeze_official_slices.py first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if bench not in manifest["slices"]:
        raise KeyError(f"Benchmark '{bench}' not in freeze manifest")
    entry = manifest["slices"][bench]
    path = SLICES_DIR / f"{bench}_20percent.json"
    actual = sha256_file(path)
    if actual != entry["sha256"]:
        raise ValueError(
            f"FROZEN SLICE MODIFIED: {bench} sha256 {actual} != frozen {entry['sha256']}. "
            "The slice is immutable; results would not be comparable."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"[freeze] {bench}: verified {entry['num_documents']} docs, "
          f"{entry['num_examples']} examples (sha256 OK)")
    return data


class FrozenSliceAdapter(BenchmarkAdapter):
    """Serves documents/examples from a frozen slice JSON - never the live dataset."""

    def __init__(self, bench: str, slice_data: Dict[str, Any]):
        super().__init__()
        self._bench = bench
        self._documents = [BenchmarkDocument(**d) for d in slice_data["documents"]]
        self._examples = [BenchmarkExample(**e) for e in slice_data["examples"]]

    @property
    def benchmark_name(self) -> str:
        return self._bench

    def load_documents(self, limit: Optional[int] = None) -> List[BenchmarkDocument]:
        return self._documents if limit is None else self._documents[:limit]

    def load_examples(self, limit: Optional[int] = None) -> List[BenchmarkExample]:
        return self._examples if limit is None else self._examples[:limit]


def run_ablation_matrix(
    benchmark_name: str,
    modes: Optional[List[str]] = None,
    k: int = 10,
    output_dir: str = "results/ablation_matrix_frozen",
    use_gpu: bool = False,
) -> Dict[str, Any]:
    modes = modes or MODES
    slice_data = verify_frozen_slice(benchmark_name)
    adapter = FrozenSliceAdapter(benchmark_name, slice_data)

    print("=" * 75)
    print(f"FROZEN-SLICE ABLATION MATRIX: {benchmark_name.upper()}")
    print(f"Modes: {modes}")
    print(f"Docs: {len(slice_data['documents'])}  Examples: {len(slice_data['examples'])}  k={k}")
    print("=" * 75)

    eval_db_dir = ROOT / "data" / "ablation_matrix_frozen"
    eval_db_dir.mkdir(parents=True, exist_ok=True)
    runner = BenchmarkRunner(output_dir=output_dir, run_id="frozen_v1")

    ablation_results: Dict[str, Dict[str, Any]] = {}
    for mode in modes:
        print(f"\n>>> Running Configuration: {mode.upper()} <<<")
        mode_qdrant = str(eval_db_dir / f"qdrant_{benchmark_name}_{mode}")
        mode_kuzu = str(eval_db_dir / f"kuzu_{benchmark_name}_{mode}.db")

        with MemoryEngine(qdrant_path=mode_qdrant, kuzu_path=mode_kuzu, use_gpu=use_gpu) as engine:
            t0 = time.time()
            summary = runner.run_benchmark(
                benchmark_name=benchmark_name,
                engine=engine,
                adapter=adapter,
                retrieval_mode=mode,
                k=k,
                resume=True,
                is_smoke_test=False,
            )
            print(f"  [{mode}] wall time: {time.time()-t0:.1f}s")
            ablation_results[mode] = summary

    # Compile comparative ablation table vs vector baseline
    ret_of = lambda m: ablation_results.get(m, {}).get("evaluation", {}).get("retrieval", {})
    vector_mrr = ret_of("vector").get("mrr", 0.0)
    vector_recall = ret_of("vector").get(f"recall@{k}", 0.0)

    comparisons = []
    for mode, data in ablation_results.items():
        ev = data.get("evaluation", {})
        ret = ev.get("retrieval", {})
        ans = ev.get("answer", {})
        lat = ev.get("latency", {})
        cats = ev.get("by_category", {})
        comparisons.append({
            "mode": mode,
            "recall@k": ret.get(f"recall@{k}", 0.0),
            "precision@k": ret.get(f"precision@{k}", 0.0),
            "mrr": ret.get("mrr", 0.0),
            "ndcg@k": ret.get(f"ndcg@{k}", 0.0),
            "token_f1": ans.get("token_f1", 0.0),
            "latency_ms": lat.get("mean_retrieval_ms", 0.0),
            "delta_recall_vs_vector": ret.get(f"recall@{k}", 0.0) - vector_recall,
            "delta_mrr_vs_vector": ret.get("mrr", 0.0) - vector_mrr,
            "category_recall": {c: v.get("recall@k", 0.0) for c, v in cats.items()},
            "category_mrr": {c: v.get("mrr", 0.0) for c, v in cats.items()},
        })

    report = {
        "benchmark": benchmark_name,
        "k": k,
        "frozen": True,
        "run_id": runner.run_id,
        "comparisons": comparisons,
        "timestamp": int(time.time()),
    }
    report_path = Path(output_dir) / f"ablation_matrix_{benchmark_name}_{runner.run_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 75)
    print(f"ABLATION MATRIX COMPLETE: {benchmark_name.upper()}")
    print(f"{'mode':<20} {'R@'+str(k):>8} {'MRR':>8} {'NDCG':>8} {'lat(ms)':>10}")
    for c in comparisons:
        print(f"{c['mode']:<20} {c['recall@k']:>8.4f} {c['mrr']:>8.4f} "
              f"{c['ndcg@k']:>8.4f} {c['latency_ms']:>10.2f}")
    print(f"Report saved: {report_path}")
    print("=" * 75)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Frozen-slice ablation matrix")
    parser.add_argument("--benchmark", type=str, required=True, choices=["locomo", "dmr", "longmemeval"])
    parser.add_argument("--modes", nargs="+", default=None)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default="results/ablation_matrix_frozen")
    parser.add_argument("--use-gpu", action="store_true")
    args = parser.parse_args()
    run_ablation_matrix(
        benchmark_name=args.benchmark,
        modes=args.modes,
        k=args.k,
        output_dir=args.output_dir,
        use_gpu=args.use_gpu,
    )
