"""Retrieval-only latency profiler for an already-ingested benchmark store."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.engine import MemoryEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, nargs="+")
    parser.add_argument("--mode", default="hybrid")
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    with MemoryEngine(
        qdrant_path=str(ROOT / "data" / "benchmark_runs_competitors" / "qdrant_locomo_hybrid"),
        kuzu_path=str(ROOT / "data" / "benchmark_runs_competitors" / "kuzu.db_locomo_hybrid.db"),
        use_gpu=not args.cpu,
    ) as engine:
        samples, results = [], []
        for _ in range(args.repeat):
            start = time.perf_counter()
            results = engine.search(" ".join(args.query), k=10, retrieval_mode=args.mode)
            samples.append((time.perf_counter() - start) * 1000)
    print(json.dumps({
        "mode": args.mode,
        "query_latency_ms": [round(sample, 3) for sample in samples],
        "mean_query_latency_ms": round(sum(samples) / len(samples), 3),
        "result_count": len(results),
        "trace": results[0].retrieval_trace if results else {},
    }, indent=2))


if __name__ == "__main__":
    main()
