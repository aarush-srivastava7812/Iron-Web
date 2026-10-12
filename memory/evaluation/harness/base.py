"""
Base classes, data models, and metrics for the benchmark harness.
"""

from __future__ import annotations

import re
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class BenchmarkDocument:
    """A document or conversation session to be ingested into the memory engine."""

    doc_id: str
    text: str
    session_id: Optional[str] = None
    timestamp: Optional[int] = None
    valid_from: int = 0
    valid_until: int = 2**63 - 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkExample:
    """A benchmark evaluation question or query."""

    example_id: str
    query: str
    ground_truth_ids: List[str] = field(default_factory=list)
    gold_answer: Optional[str] = None
    category: Optional[str] = None
    target_date: Optional[str] = None
    query_time: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Individual example result record with full telemetry."""

    run_id: str
    benchmark_name: str
    example_id: str
    query: str
    retrieved_ids: List[str]
    ground_truth_ids: List[str]
    retrieval_metrics: Dict[str, float]
    predicted_answer: Optional[str] = None
    gold_answer: Optional[str] = None
    answer_metrics: Dict[str, float] = field(default_factory=dict)
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    category: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Answer Quality Scoring (Exact Match, Token F1, Normalization)
# =============================================================================


def normalize_answer(s: str) -> str:
    """Normalize text for consistent evaluation (lowercase, punctuation, whitespace)."""
    if not isinstance(s, str):
        s = str(s)

    def remove_articles(text: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text: str) -> str:
        return " ".join(text.split())

    def remove_punc(text: str) -> str:
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text: str) -> str:
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def compute_exact_match(prediction: str, ground_truth: str) -> float:
    """Compute Exact Match (EM) between prediction and ground truth string."""
    return (
        1.0 if normalize_answer(prediction) == normalize_answer(ground_truth) else 0.0
    )


def compute_token_f1(prediction: str, ground_truth: str) -> float:
    """Compute token-level F1 score between prediction and ground truth string."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(ground_truth).split()

    if not pred_tokens or not gold_tokens:
        return 1.0 if pred_tokens == gold_tokens else 0.0

    common = set(pred_tokens) & set(gold_tokens)
    if not common:
        return 0.0

    precision = sum(
        min(pred_tokens.count(w), gold_tokens.count(w)) for w in common
    ) / len(pred_tokens)
    recall = sum(min(pred_tokens.count(w), gold_tokens.count(w)) for w in common) / len(
        gold_tokens
    )

    if precision + recall == 0:
        return 0.0
    return float(2 * (precision * recall) / (precision + recall))


def compute_substring_match(prediction: str, ground_truth: str) -> float:
    """Compute whether normalized ground truth appears inside normalized prediction."""
    norm_gold = normalize_answer(ground_truth)
    norm_pred = normalize_answer(prediction)
    if not norm_gold or not norm_pred:
        return 0.0
    return 1.0 if norm_gold in norm_pred else 0.0


# =============================================================================
# Retrieval Metrics
# =============================================================================

from memory.evaluation.retrieval_metrics import (
    recall_at_k,
    precision_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    compute_retrieval_metrics,
)


# =============================================================================
# Benchmark Adapter Abstract Base Class
# =============================================================================


class BenchmarkAdapter(ABC):
    """
    Abstract adapter interface for benchmark datasets.
    Isolates dataset-specific schema parsing from ingestion, retrieval, and scoring.
    """

    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path

    @property
    @abstractmethod
    def benchmark_name(self) -> str:
        """Name of the benchmark (e.g. 'longmemeval', 'locomo', 'dmr')."""
        pass

    @abstractmethod
    def load_documents(self, limit: Optional[int] = None) -> List[BenchmarkDocument]:
        """Load benchmark corpus documents with timestamps and session boundaries."""
        pass

    @abstractmethod
    def load_examples(self, limit: Optional[int] = None) -> List[BenchmarkExample]:
        """Load benchmark evaluation questions, gold answers, and categories."""
        pass

    def evaluate_answer(self, prediction: str, gold_answer: str) -> Dict[str, float]:
        """Compute answer-level quality metrics for this benchmark."""
        return {
            "exact_match": compute_exact_match(prediction, gold_answer),
            "token_f1": compute_token_f1(prediction, gold_answer),
            "substring_match": compute_substring_match(prediction, gold_answer),
        }


__all__ = [
    "BenchmarkAdapter",
    "BenchmarkDocument",
    "BenchmarkExample",
    "EvaluationResult",
    "normalize_answer",
    "compute_exact_match",
    "compute_token_f1",
    "compute_substring_match",
    "compute_retrieval_metrics",
    "recall_at_k",
    "precision_at_k",
    "mean_reciprocal_rank",
    "ndcg_at_k",
]
