"""
Benchmark Evaluator.
Executes evaluation cleanly separated into 4 distinct stages:
1. Ingestion Stage
2. Retrieval Stage
3. Generation Stage
4. Scoring Stage
"""

from __future__ import annotations

import time
import logging
from typing import List, Dict, Any, Optional, Callable
import numpy as np

from memory.engine import MemoryEngine
from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
    EvaluationResult,
    compute_retrieval_metrics,
)

logger = logging.getLogger(__name__)


class BenchmarkEvaluator:
    """
    Coordinates end-to-end evaluation with strict separation of stages.
    """

    def __init__(
        self,
        engine: MemoryEngine,
        adapter: BenchmarkAdapter,
        generator_fn: Optional[Callable[[str, List[str]], str]] = None,
        retrieval_mode: str = "hybrid",
        k: int = 10,
    ):
        self.engine = engine
        self.adapter = adapter
        self.generator_fn = generator_fn or self._default_extractive_generator
        self.retrieval_mode = retrieval_mode
        self.k = k

    # =========================================================================
    # Stage 1: Ingestion Stage
    # =========================================================================

    def ingest_documents(
        self,
        documents: List[BenchmarkDocument],
        batch_size: int = 20,
        show_progress: bool = True,
    ) -> Dict[str, Any]:
        """
        Ingest benchmark documents into the MemoryEngine respecting session boundaries.
        """
        if batch_size < 1:
            raise ValueError("Batch size must be positive.")
        if self.retrieval_mode in {"none", "no_memory"}:
            return dict(
                num_documents=len(documents),
                ingested_ids=0,
                skipped_reason="no_memory_baseline",
                ingestion_time_sec=0.0,
            )
        if hasattr(self.engine, "ingest_documents"):
            return self.engine.ingest_documents(documents, batch_size, show_progress)
        t0 = time.perf_counter()
        ingested_ids = []
        skipped = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            items = []
            for doc in batch:
                existing = self.engine.get(doc.doc_id)
                selected = getattr(self.engine, "extractor", None)
                expected_mock = bool(getattr(selected, "is_mock", False))
                expected_status = "disabled" if selected is None else "completed"
                provenance_matches = (
                    existing
                    and existing.metadata.get("extraction_is_mock", False if getattr(self.engine, "backend", None) == "iron_web_2" else None) is expected_mock
                    and existing.metadata.get("extraction_status", "disabled" if getattr(self.engine, "backend", None) == "iron_web_2" else None) == expected_status
                )
                if (
                    provenance_matches
                    and existing.content == doc.text
                    and (doc.timestamp is None or existing.timestamp == doc.timestamp)
                    and all(
                        existing.metadata.get(key) == value
                        for key, value in doc.metadata.items()
                    )
                    and existing.valid_from == doc.valid_from
                    and existing.valid_until == doc.valid_until
                ):
                    skipped += 1
                    continue
                items.append(
                    {
                        "memory_id": doc.doc_id,
                        "content": doc.text,
                        "timestamp": doc.timestamp,
                        "valid_from": doc.valid_from,
                        "valid_until": doc.valid_until,
                        "metadata": doc.metadata,
                    }
                )
            batch_ids = self.engine.add_batch(items)
            ingested_ids.extend(batch_ids)

            if show_progress and (i + len(batch)) % 100 == 0:
                logger.info(f"Ingested {i + len(batch)} / {len(documents)} documents")

        duration = time.perf_counter() - t0
        return {
            "num_documents": len(documents),
            "ingested_ids": len(ingested_ids),
            "skipped_unchanged": skipped,
            "ingestion_time_sec": duration,
            "docs_per_sec": len(documents) / duration if duration > 0 else 0.0,
        }

    # =========================================================================
    # Stage 2: Retrieval Stage
    # =========================================================================

    def retrieve_for_example(
        self, example: BenchmarkExample
    ) -> tuple[List[str], List[Dict[str, Any]], float]:
        """
        Execute memory retrieval for a single example query.
        Returns:
            (retrieved_ids, retrieved_records, latency_ms)
        """
        t0 = time.perf_counter()

        search_results = self.engine.search(
            query=example.query,
            k=self.k,
            query_time=example.query_time,
            retrieval_mode=self.retrieval_mode,
            document_ids=example.metadata.get("corpus_ids"),
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        retrieved_ids = [r.memory_id for r in search_results]
        retrieved_records = [
            {
                "memory_id": r.memory_id,
                "content": r.content,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in search_results
        ]
        return retrieved_ids, retrieved_records, latency_ms

    # =========================================================================
    # Stage 3: Answer Generation Stage
    # =========================================================================

    def generate_answer(
        self, query: str, retrieved_contents: List[str]
    ) -> tuple[str, float]:
        """
        Generate answer from query and retrieved context using configured generator.
        """
        t0 = time.perf_counter()
        prediction = self.generator_fn(query, retrieved_contents)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return prediction, latency_ms

    def _default_extractive_generator(
        self, query: str, retrieved_contents: List[str]
    ) -> str:
        """
        Default zero-shot extractive generator.
        Picks the most salient sentence from the top retrieved context.
        """
        if not retrieved_contents:
            return ""
        top_text = retrieved_contents[0]
        # Return first non-empty line or first sentence
        for line in top_text.split("\n"):
            line = line.strip()
            if (
                line
                and not line.startswith("speaker:")
                and not line.startswith("Speaker")
            ):
                return line
            elif line:
                # Remove speaker prefix
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        return top_text[:200].strip()

    # =========================================================================
    # Stage 4: Scoring Stage
    # =========================================================================

    def evaluate_example(
        self, example: BenchmarkExample, run_id: str
    ) -> EvaluationResult:
        """
        Execute full pipeline for a single example across retrieval, generation, and scoring.
        """
        # 1. Retrieval
        retrieved_ids, retrieved_records, ret_latency = self.retrieve_for_example(
            example
        )

        # 2. Retrieval Metrics
        ret_metrics = (
            compute_retrieval_metrics(
                retrieved=retrieved_ids,
                relevant=example.ground_truth_ids,
                k_values=[1, 3, 5, self.k],
            )
            if example.ground_truth_ids
            else {}
        )

        # 3. Generation (if gold answer exists)
        prediction = None
        gen_latency = 0.0
        ans_metrics = {}

        if example.gold_answer is not None and example.gold_answer != "":
            contents = [r["content"] for r in retrieved_records]
            prediction, gen_latency = self.generate_answer(example.query, contents)
            ans_metrics = self.adapter.evaluate_answer(prediction, example.gold_answer)

        return EvaluationResult(
            run_id=run_id,
            benchmark_name=self.adapter.benchmark_name,
            example_id=example.example_id,
            query=example.query,
            retrieved_ids=retrieved_ids,
            ground_truth_ids=example.ground_truth_ids,
            retrieval_metrics=ret_metrics,
            predicted_answer=prediction,
            gold_answer=example.gold_answer,
            answer_metrics=ans_metrics,
            retrieval_latency_ms=ret_latency,
            generation_latency_ms=gen_latency,
            total_latency_ms=ret_latency + gen_latency,
            category=example.category,
            metadata=example.metadata,
        )

    def aggregate_results(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Aggregate evaluation results across all examples, including category breakdowns."""
        if not results:
            return {}

        successful = [r for r in results if not r.error]
        ret_metrics_keys = sorted(
            {key for r in successful for key in r.retrieval_metrics}
        )
        ans_metrics_keys = sorted({key for r in successful for key in r.answer_metrics})
        agg = {
            "total_examples": len(results),
            "successful_examples": len(successful),
            "failed_examples": len(results) - len(successful),
            "retrieval_scored_examples": sum(
                bool(r.retrieval_metrics) for r in successful
            ),
            "answer_scored_examples": sum(bool(r.answer_metrics) for r in successful),
            "retrieval": {},
            "answer": {},
            "by_category": {},
            "latency": {
                "mean_retrieval_ms": float(
                    np.mean([r.retrieval_latency_ms for r in successful])
                )
                if successful
                else None,
                "mean_total_ms": float(
                    np.mean([r.total_latency_ms for r in successful])
                )
                if successful
                else None,
            },
        }
        for key in ret_metrics_keys:
            agg["retrieval"][key] = float(
                np.mean(
                    [
                        r.retrieval_metrics[key]
                        for r in successful
                        if key in r.retrieval_metrics
                    ]
                )
            )
        for key in ans_metrics_keys:
            agg["answer"][key] = float(
                np.mean(
                    [
                        r.answer_metrics[key]
                        for r in successful
                        if key in r.answer_metrics
                    ]
                )
            )

        # Category breakdowns
        categories = set(r.category for r in successful if r.category)
        for cat in sorted(categories):
            cat_results = [r for r in successful if r.category == cat]
            agg["by_category"][cat] = {
                "count": len(cat_results),
                "recall@k": float(
                    np.mean(
                        [
                            r.retrieval_metrics.get(f"recall@{self.k}", 0.0)
                            for r in cat_results
                            if r.retrieval_metrics
                        ]
                    )
                )
                if any(r.retrieval_metrics for r in cat_results)
                else None,
                "mrr": float(
                    np.mean(
                        [
                            r.retrieval_metrics.get("mrr", 0.0)
                            for r in cat_results
                            if r.retrieval_metrics
                        ]
                    )
                )
                if any(r.retrieval_metrics for r in cat_results)
                else None,
            }
            if ans_metrics_keys:
                for k in ans_metrics_keys:
                    cat_vals = [
                        r.answer_metrics.get(k, 0.0)
                        for r in cat_results
                        if r.answer_metrics
                    ]
                    if cat_vals:
                        agg["by_category"][cat][k] = float(np.mean(cat_vals))

        return agg
