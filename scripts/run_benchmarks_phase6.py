"""
Phase 6: Run Actual Benchmark Evaluations.

Executes official benchmark runs across:
- LongMemEval (Wu et al. 2024)
- LoCoMo (Maharana et al. 2024)
- DMR (Packer et al. 2023 / MemGPT MSC)

Runs identical examples across:
- Baseline (Vector-only)
- Proposed Architecture (Hybrid Vector + Graph + Bitemporal + Reranker)

Saves raw per-example outputs (.jsonl) and aggregate summary metrics (.json).
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


def run_benchmark_evaluations(
    benchmarks: list[str] = None,
    modes: list[str] = None,
    max_docs: int = 50,
    max_examples: int = 25,
    k: int = 10,
    output_dir: str = "data/results",
    use_gpu: bool = False
) -> dict:
    """Run Phase 6 evaluations and record real empirical numbers."""
    benchmarks = benchmarks or ["locomo", "longmemeval", "dmr"]
    modes = modes or ["vector", "hybrid"]
    
    print("=" * 70)
    print("PHASE 6: RUN ACTUAL BENCHMARK EVALUATIONS")
    print("=" * 70)
    print(f"Benchmarks to evaluate: {benchmarks}")
    print(f"Retrieval modes:        {modes}")
    print(f"Max documents/bench:    {max_docs}")
    print(f"Max examples/bench:     {max_examples}")
    print(f"Top-K limit:            {k}")
    print(f"Output directory:       {output_dir}")
    print("=" * 70)

    # Prepare isolated database directory for evaluation
    eval_db_dir = ROOT / "data" / "benchmark_run"
    eval_db_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = str(eval_db_dir / "qdrant")
    kuzu_path = str(eval_db_dir / "kuzu.db")

    runner = BenchmarkRunner(output_dir=output_dir)
    suite_results = {}

    adapters = {
        "locomo": LoCoMoAdapter(),
        "longmemeval": LongMemEvalAdapter(),
        "dmr": DMRAdapter()
    }

    for bench_name in benchmarks:
        if bench_name not in adapters:
            print(f"Skipping unknown benchmark: {bench_name}")
            continue
            
        adapter = adapters[bench_name]
        print(f"\n>>> Running Benchmark: {bench_name.upper()} <<<")
        suite_results[bench_name] = {}

        for mode in modes:
            print(f"\n--- Mode: {mode.upper()} ---")
            
            # Fresh engine per mode to ensure fair identical comparison
            mode_qdrant = f"{qdrant_path}_{bench_name}_{mode}"
            mode_kuzu = f"{kuzu_path}_{bench_name}_{mode}.db"
            
            with MemoryEngine(qdrant_path=mode_qdrant, kuzu_path=mode_kuzu, use_gpu=use_gpu) as engine:
                summary = runner.run_benchmark(
                    benchmark_name=bench_name,
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
                if ans_metrics:
                    print(f"  Exact Match:         {ans_metrics.get('exact_match', 0.0):.4f}")
                    print(f"  Token F1:            {ans_metrics.get('token_f1', 0.0):.4f}")
                print(f"  Mean Latency:        {latency.get('mean_retrieval_ms', 0.0):.2f} ms")
                print(f"  Raw Results Log:     {summary.get('run_file')}")
                
                suite_results[bench_name][mode] = summary

    # Write combined Phase 6 report
    report_file = Path(output_dir) / f"phase6_benchmark_report_{runner.run_id}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(suite_results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"PHASE 6 BENCHMARK EVALUATIONS COMPLETED")
    print(f"Combined report saved to: {report_file}")
    print("=" * 70)
    return suite_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Phase 6 Benchmark Evaluations")
    parser.add_argument("--benchmarks", nargs="+", default=["locomo", "longmemeval", "dmr"])
    parser.add_argument("--modes", nargs="+", default=["vector", "hybrid"])
    parser.add_argument("--max-docs", type=int, default=50)
    parser.add_argument("--max-examples", type=int, default=25)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default="data/results")
    parser.add_argument("--use-gpu", action="store_true")
    
    args = parser.parse_args()
    run_benchmark_evaluations(
        benchmarks=args.benchmarks,
        modes=args.modes,
        max_docs=args.max_docs,
        max_examples=args.max_examples,
        k=args.k,
        output_dir=args.output_dir,
        use_gpu=args.use_gpu
    )
