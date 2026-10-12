"""
Phase 7: Baselines, Component Ablations, and Quantitative Analysis.

Executes controlled ablation study on the benchmark suite across:
- Baseline A: No external memory (returns empty retrieved context)
- Baseline B: Vector-only (FastEmbed + Qdrant, without graph expansion or reranking)
- Baseline C: Graph-only (Kùzu-based entity linking & observation expansion without vector similarity)
- Variant D: Vector + Graph (Hybrid candidate fusion without cross-encoder reranker)
- Variant E: Full Proposed Architecture (Vector + Graph + Bitemporal + Contradiction Supersession + Reranker)
- Ablation F: Full Proposed without Graph Expansion (hybrid_no_graph)
- Ablation G: Full Proposed without Temporal Filtering (hybrid_no_temporal)

Outputs:
- Raw per-example logs (.jsonl)
- Summary JSON metrics per mode
- Unified comparative ablation report (JSON & formatted Markdown table)
"""
from __future__ import annotations

import os
import sys
import time
import json
import argparse
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.engine import MemoryEngine
from memory.evaluation.harness import (
    BenchmarkRunner,
    LongMemEvalAdapter,
    LoCoMoAdapter,
    DMRAdapter,
)


def run_ablation_study(
    benchmark_name: str = "locomo",
    modes: list[str] = None,
    max_docs: int = 50,
    max_examples: int = 25,
    k: int = 10,
    output_dir: str = "data/results/ablations",
    use_gpu: bool = False
) -> dict:
    """Execute Phase 7 ablations and compile comparative performance deltas."""
    if modes is None:
        modes = [
            "no_memory",           # Baseline A
            "vector",              # Baseline B
            "graph",               # Baseline C
            "hybrid_no_rerank",    # Variant D
            "hybrid_no_graph",     # Ablation: without graph
            "hybrid_no_temporal",  # Ablation: without temporal
            "hybrid"               # Variant E: Full proposed architecture
        ]

    print("=" * 75)
    print("PHASE 7: BASELINES, COMPONENT ABLATIONS & QUANTITATIVE ANALYSIS")
    print("=" * 75)
    print(f"Benchmark:        {benchmark_name.upper()}")
    print(f"Configurations:   {modes}")
    print(f"Documents:        {max_docs}")
    print(f"Examples:         {max_examples}")
    print(f"Top-K:            {k}")
    print(f"Output Directory: {output_dir}")
    print("=" * 75)

    eval_db_dir = ROOT / "data" / "ablation_run"
    eval_db_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = str(eval_db_dir / "qdrant")
    kuzu_path = str(eval_db_dir / "kuzu.db")

    runner = BenchmarkRunner(output_dir=output_dir)

    adapters = {
        "locomo": LoCoMoAdapter(),
        "longmemeval": LongMemEvalAdapter(),
        "dmr": DMRAdapter()
    }
    
    if benchmark_name.lower() not in adapters:
        raise ValueError(f"Unknown benchmark: {benchmark_name}")
    adapter = adapters[benchmark_name.lower()]

    ablation_results = {}

    for mode in modes:
        print(f"\n>>> Running Configuration: {mode.upper()} <<<")
        
        mode_qdrant = f"{qdrant_path}_{benchmark_name}_{mode}"
        mode_kuzu = f"{kuzu_path}_{benchmark_name}_{mode}.db"

        with MemoryEngine(qdrant_path=mode_qdrant, kuzu_path=mode_kuzu, use_gpu=use_gpu) as engine:
            summary = runner.run_benchmark(
                benchmark_name=benchmark_name,
                engine=engine,
                adapter=adapter,
                max_documents=max_docs,
                max_examples=max_examples,
                retrieval_mode=mode,
                k=k,
                resume=True,
                is_smoke_test=False
            )
            
            eval_metrics = summary.get("evaluation", {}).get("retrieval", {})
            ans_metrics = summary.get("evaluation", {}).get("answer", {})
            latency = summary.get("evaluation", {}).get("latency", {})
            
            print(f"  Processed Examples: {summary.get('evaluation', {}).get('total_examples', 0)}")
            print(f"  Recall@{k}:           {eval_metrics.get(f'recall@{k}', 0.0):.4f}")
            print(f"  Precision@{k}:        {eval_metrics.get(f'precision@{k}', 0.0):.4f}")
            print(f"  MRR:                 {eval_metrics.get('mrr', 0.0):.4f}")
            print(f"  NDCG@{k}:             {eval_metrics.get(f'ndcg@{k}', 0.0):.4f}")
            print(f"  Token F1:            {ans_metrics.get('token_f1', 0.0):.4f}")
            print(f"  Mean Latency:        {latency.get('mean_retrieval_ms', 0.0):.2f} ms")
            
            ablation_results[mode] = summary

    # Compile comparative ablation table & marginal gains
    vector_mrr = ablation_results.get("vector", {}).get("evaluation", {}).get("retrieval", {}).get("mrr", 0.0)
    vector_recall = ablation_results.get("vector", {}).get("evaluation", {}).get("retrieval", {}).get(f"recall@{k}", 0.0)
    
    comparisons = []
    for mode, data in ablation_results.items():
        ret = data.get("evaluation", {}).get("retrieval", {})
        ans = data.get("evaluation", {}).get("answer", {})
        lat = data.get("evaluation", {}).get("latency", {})
        cats = data.get("evaluation", {}).get("by_category", {})
        
        mrr = ret.get("mrr", 0.0)
        rec = ret.get(f"recall@{k}", 0.0)
        delta_mrr = mrr - vector_mrr
        delta_rec = rec - vector_recall
        
        comparisons.append({
            "mode": mode,
            "recall@10": rec,
            "precision@10": ret.get(f"precision@{k}", 0.0),
            "mrr": mrr,
            "ndcg@10": ret.get(f"ndcg@{k}", 0.0),
            "token_f1": ans.get("token_f1", 0.0),
            "latency_ms": lat.get("mean_retrieval_ms", 0.0),
            "delta_recall_vs_vector": delta_rec,
            "delta_mrr_vs_vector": delta_mrr,
            "category_mrr": {c: v.get("mrr", 0.0) for c, v in cats.items()}
        })

    report = {
        "benchmark": benchmark_name,
        "k": k,
        "configurations": ablation_results,
        "comparisons": comparisons,
        "timestamp": int(time.time())
    }

    report_path = Path(output_dir) / f"phase7_ablation_report_{benchmark_name}_{runner.run_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 75)
    print(f"PHASE 7 ABLATION STUDY COMPLETE")
    print(f"Ablation Report Saved: {report_path}")
    print("=" * 75)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 7 Ablation Study")
    parser.add_argument("--benchmark", type=str, default="locomo", choices=["locomo", "dmr", "longmemeval"])
    parser.add_argument("--modes", nargs="+", default=None)
    parser.add_argument("--max-docs", type=int, default=50)
    parser.add_argument("--max-examples", type=int, default=25)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default="data/results/ablations")
    parser.add_argument("--use-gpu", action="store_true")

    args = parser.parse_args()
    run_ablation_study(
        benchmark_name=args.benchmark,
        modes=args.modes,
        max_docs=args.max_docs,
        max_examples=args.max_examples,
        k=args.k,
        output_dir=args.output_dir,
        use_gpu=args.use_gpu
    )
