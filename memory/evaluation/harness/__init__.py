"""
Benchmark Harness Package.
Provides unified, decoupled evaluation adapters and orchestrators for:
- LongMemEval
- LoCoMo
- DMR (Multi-Session Chat)
"""
from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
    EvaluationResult,
    compute_exact_match,
    compute_token_f1,
    compute_substring_match,
    compute_retrieval_metrics,
)
from memory.evaluation.harness.longmemeval_adapter import LongMemEvalAdapter
from memory.evaluation.harness.locomo_adapter import LoCoMoAdapter
from memory.evaluation.harness.dmr_adapter import DMRAdapter
from memory.evaluation.harness.evaluator import BenchmarkEvaluator
from memory.evaluation.harness.runner import BenchmarkRunner

__all__ = [
    "BenchmarkAdapter",
    "BenchmarkDocument",
    "BenchmarkExample",
    "EvaluationResult",
    "LongMemEvalAdapter",
    "LoCoMoAdapter",
    "DMRAdapter",
    "BenchmarkEvaluator",
    "BenchmarkRunner",
    "compute_exact_match",
    "compute_token_f1",
    "compute_substring_match",
    "compute_retrieval_metrics",
]
