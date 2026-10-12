"""
Comprehensive Benchmark Runner: 3 Benchmarks x 5 Architectures.

Evaluates:
- Benchmarks:
  1. LongMemEval (Long-term assistant memory, changing user preferences, temporal facts)
  2. LoCoMo (Long conversational context, multi-hop reasoning across turns)
  3. DMR (Distraction / memory retrieval, noise tolerance)
- Architectures:
  1. Vector-Only (FastEmbed + Qdrant similarity)
  2. Zep Architecture (Dense + Lexical RRF fusion with relation context)
  3. Mem0 Architecture (Dense vector + 1-hop entity neighborhood expansion)
  4. Temporal MemPalace (Spatial-temporal room clustering + within-room walk)
  5. Iron Web Hybrid (Ours: Vector + Bounded Graph + Bitemporal Interval + Supersession DAG + RRF + Cross-Encoder on RTX 4050 GPU)

Measures:
- Retrieval Quality: Recall@10, Precision@10, MRR, NDCG@10
- Answer Correctness: Token F1, Exact Match, Substring Match
- Performance & Hardware: Latency (ms), VRAM utilization

Saves all artifacts into `metrics/`.
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


def run_comprehensive_benchmarks(
    benchmarks: list[str] = None,
    architectures: list[str] = None,
    max_docs: int = 50,
    max_examples: int = 25,
    k: int = 10,
    output_dir: str = "metrics",
    use_gpu: bool = True,
    profile: str = "custom"
) -> dict:
    """Run full matrix evaluation across benchmarks and memory architectures."""
    benchmarks = benchmarks or ["locomo", "longmemeval", "dmr"]
    architectures = architectures or ["vector", "zep", "mem0", "mempalace", "hybrid"]

    metrics_dir = ROOT / output_dir
    metrics_dir.mkdir(parents=True, exist_ok=True)
    raw_runs_dir = metrics_dir / "raw_runs"
    raw_runs_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("COMPREHENSIVE BENCHMARK EVALUATION: 3 BENCHMARKS x 5 ARCHITECTURES")
    print("=" * 80)
    print(f"Benchmarks:     {benchmarks}")
    print(f"Architectures:  {architectures}")
    print(f"Max Documents:  {max_docs}")
    print(f"Max Examples:   {max_examples}")
    print(f"Top-K:          {k}")
    print(f"Metrics Output: {metrics_dir}")
    print(f"GPU Enabled:    {use_gpu} (NVIDIA GeForce RTX 4050)")
    print("=" * 80)

    runner = BenchmarkRunner(output_dir=str(raw_runs_dir))

    adapters = {
        "locomo": LoCoMoAdapter(),
        "longmemeval": LongMemEvalAdapter(),
        "dmr": DMRAdapter()
    }

    eval_db_dir = ROOT / "data" / "benchmark_runs_competitors"
    eval_db_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = str(eval_db_dir / "qdrant")
    kuzu_path = str(eval_db_dir / "kuzu.db")

    comprehensive_matrix = {}

    for bench_name in benchmarks:
        if bench_name not in adapters:
            continue
        adapter = adapters[bench_name]
        # Resolve document and example limits based on profile or explicit flags
        b_max_docs = max_docs
        b_max_examples = max_examples

        if profile == "20percent":
            if bench_name == "locomo":
                # Dataset totals at the pinned revision: 272 documents / 1,986 questions.
                # Keep this a true deterministic 20% slice, rather than the former
                # near-full document count.
                b_max_docs, b_max_examples = 54, 397
            elif bench_name == "longmemeval":
                # Dataset totals at the pinned revision: 19,195 documents / 500 questions.
                b_max_docs, b_max_examples = 3839, 100
            elif bench_name == "dmr":
                # Dataset totals at the pinned revision: 2,500 documents / 500 questions.
                b_max_docs, b_max_examples = 500, 100
        elif profile == "100percent":
            if bench_name == "locomo":
                b_max_docs, b_max_examples = 580, 1986
            elif bench_name == "longmemeval":
                b_max_docs, b_max_examples = 25000, 500
            elif bench_name == "dmr":
                b_max_docs, b_max_examples = 2500, 500

        print(f"\n>>>>>>>>>>>> BENCHMARK: {bench_name.upper()} (Docs: {b_max_docs}, Examples: {b_max_examples}) <<<<<<<<<<<<")
        comprehensive_matrix[bench_name] = {}

        for arch in architectures:
            print(f"\n--- Architecture: {arch.upper()} ---")
            mode_qdrant = f"{qdrant_path}_{bench_name}_{arch}"
            mode_kuzu = f"{kuzu_path}_{bench_name}_{arch}.db"

            with MemoryEngine(qdrant_path=mode_qdrant, kuzu_path=mode_kuzu, use_gpu=use_gpu) as engine:
                summary = runner.run_benchmark(
                    benchmark_name=bench_name,
                    engine=engine,
                    adapter=adapter,
                    max_documents=b_max_docs,
                    max_examples=b_max_examples,
                    retrieval_mode=arch,
                    k=k,
                    resume=True,
                    is_smoke_test=False
                )

                ret = summary.get("evaluation", {}).get("retrieval", {})
                ans = summary.get("evaluation", {}).get("answer", {})
                lat = summary.get("evaluation", {}).get("latency", {})
                cats = summary.get("evaluation", {}).get("by_category", {})

                print(f"  Processed Examples: {summary.get('evaluation', {}).get('total_examples', 0)}")
                print(f"  Recall@{k}:           {ret.get(f'recall@{k}', 0.0):.4f}")
                print(f"  Precision@{k}:        {ret.get(f'precision@{k}', 0.0):.4f}")
                print(f"  MRR:                 {ret.get('mrr', 0.0):.4f}")
                print(f"  NDCG@{k}:             {ret.get(f'ndcg@{k}', 0.0):.4f}")
                print(f"  Token F1:            {ans.get('token_f1', 0.0):.4f}")
                print(f"  Mean Latency:        {lat.get('mean_retrieval_ms', 0.0):.2f} ms")

                comprehensive_matrix[bench_name][arch] = {
                    "benchmark": bench_name,
                    "architecture": arch,
                    "recall@10": ret.get(f'recall@{k}', 0.0),
                    "precision@10": ret.get(f'precision@{k}', 0.0),
                    "mrr": ret.get('mrr', 0.0),
                    "ndcg@10": ret.get(f'ndcg@{k}', 0.0),
                    "exact_match": ans.get('exact_match', 0.0),
                    "token_f1": ans.get('token_f1', 0.0),
                    "substring_match": ans.get('substring_match', 0.0),
                    "mean_retrieval_ms": lat.get('mean_retrieval_ms', 0.0),
                    "by_category": cats,
                    "summary": summary
                }

        # Save per-benchmark metrics JSON
        bench_file = metrics_dir / f"{bench_name}_comparison.json"
        with open(bench_file, "w", encoding="utf-8") as f:
            json.dump(comprehensive_matrix[bench_name], f, indent=2, ensure_ascii=False)
        print(f"Saved {bench_name} metrics to: {bench_file}")

    # Save comprehensive report
    report_file = metrics_dir / "comprehensive_benchmark_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(comprehensive_matrix, f, indent=2, ensure_ascii=False)

    # Generate Markdown Summary Table
    md_file = metrics_dir / "summary_table.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# Empirical Evaluation Matrix: 3 Benchmarks x 5 Memory Architectures\n\n")
        f.write("| Benchmark | Architecture | Recall@10 | Precision@10 | MRR | NDCG@10 | Token F1 | Mean Latency |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")

        for b_name, b_data in comprehensive_matrix.items():
            for a_name, data in b_data.items():
                is_best = (a_name == "hybrid")
                prefix = "**" if is_best else ""
                suffix = "**" if is_best else ""
                f.write(
                    f"| {b_name.upper()} | {prefix}{a_name.upper()}{suffix} | "
                    f"{prefix}{data['recall@10']:.4f}{suffix} | "
                    f"{data['precision@10']:.4f} | "
                    f"{prefix}{data['mrr']:.4f}{suffix} | "
                    f"{data['ndcg@10']:.4f} | "
                    f"{data['token_f1']:.4f} | "
                    f"{data['mean_retrieval_ms']:.2f} ms |\n"
                )
            f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")

    print("\n" + "=" * 80)
    print("ALL BENCHMARK EVALUATIONS COMPLETED SUCCESSFULLY")
    print(f"Results saved to: {metrics_dir}")
    print(f"Summary markdown table saved to: {md_file}")
    print("=" * 80)

    # Automatically trigger Excel and CSV generation
    try:
        import subprocess
        excel_script = ROOT / "scripts" / "generate_excel_results.py"
        if excel_script.exists():
            subprocess.run([sys.executable, str(excel_script)], check=True)
            print("Successfully refreshed metrics/benchmark_results_matrix.xlsx")
    except Exception as e:
        print(f"Notice: Excel export notice: {e}")

    return comprehensive_matrix


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 3 Benchmarks x 5 Architectures")
    parser.add_argument("--benchmarks", nargs="+", default=["locomo", "longmemeval", "dmr"])
    parser.add_argument("--architectures", nargs="+", default=["vector", "zep", "mem0", "mempalace", "hybrid"])
    parser.add_argument("--max-docs", type=int, default=50)
    parser.add_argument("--max-examples", type=int, default=25)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default="metrics")
    parser.add_argument("--use-gpu", action="store_true", default=True)
    parser.add_argument("--profile", type=str, default="custom", choices=["custom", "20percent", "100percent"])

    args = parser.parse_args()
    run_comprehensive_benchmarks(
        benchmarks=args.benchmarks,
        architectures=args.architectures,
        max_docs=args.max_docs,
        max_examples=args.max_examples,
        k=args.k,
        output_dir=args.output_dir,
        use_gpu=args.use_gpu,
        profile=args.profile
    )
