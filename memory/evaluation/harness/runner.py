"""
Benchmark Runner.
Orchestrates benchmark execution, logging, resumable run persistence,
and summary report generation.
"""
from __future__ import annotations

import os
import json
import time
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from memory.engine import MemoryEngine
from memory.evaluation.harness.base import BenchmarkAdapter, EvaluationResult
from memory.evaluation.harness.longmemeval_adapter import LongMemEvalAdapter
from memory.evaluation.harness.locomo_adapter import LoCoMoAdapter
from memory.evaluation.harness.dmr_adapter import DMRAdapter
from memory.evaluation.harness.evaluator import BenchmarkEvaluator

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """
    Executes benchmark evaluation with telemetry logging, per-example JSONL streaming,
    and resumable checkpoints.
    """

    ADAPTER_REGISTRY = {
        "longmemeval": LongMemEvalAdapter,
        "locomo": LoCoMoAdapter,
        "dmr": DMRAdapter
    }

    def __init__(
        self,
        output_dir: str = "./data/results",
        run_id: Optional[str] = None
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    def run_benchmark(
        self,
        benchmark_name: str,
        engine: MemoryEngine,
        adapter: Optional[BenchmarkAdapter] = None,
        max_documents: Optional[int] = None,
        max_examples: Optional[int] = None,
        retrieval_mode: str = "hybrid",
        k: int = 10,
        resume: bool = True,
        is_smoke_test: bool = False
    ) -> Dict[str, Any]:
        """
        Run a single benchmark evaluation.
        
        Args:
            benchmark_name: 'longmemeval', 'locomo', or 'dmr'
            engine: MemoryEngine instance
            adapter: Optional explicit adapter instance
            max_documents: Limit on documents ingested (for development/smoke tests)
            max_examples: Limit on queries evaluated (for development/smoke tests)
            retrieval_mode: 'hybrid', 'vector', or 'graph'
            k: Top-k retrieved memories limit
            resume: If True, skip already evaluated examples found in the run file
            is_smoke_test: Flag declaring whether this is a development smoke test
        """
        bench_key = benchmark_name.lower()
        if adapter is None:
            if bench_key not in self.ADAPTER_REGISTRY:
                raise ValueError(f"Unknown benchmark '{benchmark_name}'. Registered: {list(self.ADAPTER_REGISTRY.keys())}")
            adapter = self.ADAPTER_REGISTRY[bench_key]()

        # Output paths
        bench_dir = self.output_dir / bench_key
        bench_dir.mkdir(parents=True, exist_ok=True)
        
        mode_suffix = "smoke" if is_smoke_test else "official"
        run_file = bench_dir / f"{self.run_id}_{retrieval_mode}_{mode_suffix}.jsonl"
        summary_file = bench_dir / f"{self.run_id}_{retrieval_mode}_{mode_suffix}_summary.json"

        # Check existing results if resuming
        processed_ids = set()
        existing_results = []
        if resume and run_file.exists():
            for line in run_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        record = json.loads(line)
                        processed_ids.add(record["example_id"])
                        existing_results.append(record)
                    except Exception:
                        pass
            logger.info(f"Resuming run {self.run_id}: found {len(processed_ids)} previously processed examples.")

        # 1. Ingest Documents
        documents = adapter.load_documents(limit=max_documents)
        evaluator = BenchmarkEvaluator(
            engine=engine,
            adapter=adapter,
            retrieval_mode=retrieval_mode,
            k=k
        )
        
        ingest_stats = evaluator.ingest_documents(documents, show_progress=False)

        # 2. Load and Evaluate Queries
        examples = adapter.load_examples(limit=max_examples)
        results: List[EvaluationResult] = []

        with open(run_file, "a", encoding="utf-8") as f_out:
            for idx, ex in enumerate(examples):
                if ex.example_id in processed_ids:
                    continue
                
                try:
                    res = evaluator.evaluate_example(ex, run_id=self.run_id)
                    results.append(res)
                    f_out.write(json.dumps(res.to_dict(), ensure_ascii=False) + "\n")
                    f_out.flush()
                except Exception as e:
                    logger.error(f"Error evaluating example {ex.example_id}: {e}")
                    err_res = EvaluationResult(
                        run_id=self.run_id,
                        benchmark_name=adapter.benchmark_name,
                        example_id=ex.example_id,
                        query=ex.query,
                        retrieved_ids=[],
                        ground_truth_ids=ex.ground_truth_ids,
                        retrieval_metrics={},
                        error=str(e)
                    )
                    results.append(err_res)
                    f_out.write(json.dumps(err_res.to_dict(), ensure_ascii=False) + "\n")
                    f_out.flush()

        # 3. Aggregate Results
        aggregated = evaluator.aggregate_results(results)
        
        # Metadata header
        dev_status = engine.get_device_status()
        summary = {
            "run_id": self.run_id,
            "benchmark": adapter.benchmark_name,
            "is_smoke_test": is_smoke_test,
            "retrieval_mode": retrieval_mode,
            "k": k,
            "timestamp": int(time.time()),
            "device": {
                "cuda_available": dev_status.cuda_available,
                "execution_providers": dev_status.active_providers,
                "vram_total_mb": dev_status.vram_total_mb,
                "vram_used_mb": dev_status.vram_used_mb
            },
            "ingestion": ingest_stats,
            "evaluation": aggregated,
            "run_file": str(run_file)
        }

        with open(summary_file, "w", encoding="utf-8") as f_sum:
            json.dump(summary, f_sum, indent=2, ensure_ascii=False)

        return summary
