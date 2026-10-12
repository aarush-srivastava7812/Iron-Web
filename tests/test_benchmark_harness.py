"""
Test suite for Phase 5: Benchmark Harness.
Tests verify:
1. Exact match, token F1, and standard IR retrieval metrics.
2. LongMemEvalAdapter: loads real dataset, preserves types, dates, gold answers, and evidence sessions.
3. LoCoMoAdapter: loads real dataset, preserves 10-conversation multi-session structure, QA categories, and evidence turns.
4. DMRAdapter: loads multi-session chat dialogues and QA queries with gold answers.
5. BenchmarkEvaluator: 4-stage execution (ingest, retrieve, generate, score).
6. BenchmarkRunner: resumability, per-example JSONL streaming, and metadata logging.
"""

import json
from pathlib import Path
import pytest

from memory.engine import MemoryEngine
from memory.evaluation.harness import (
    BenchmarkDocument,
    BenchmarkExample,
    EvaluationResult,
    LongMemEvalAdapter,
    LoCoMoAdapter,
    DMRAdapter,
    BenchmarkEvaluator,
    BenchmarkRunner,
    compute_exact_match,
    compute_token_f1,
    compute_substring_match,
    compute_retrieval_metrics,
)


def test_metrics_calculations():
    """Verify EM, F1, and IR metrics on known cases."""
    # Exact Match & Normalization
    assert (
        compute_exact_match("Business Administration", "business administration") == 1.0
    )
    assert compute_exact_match("The Taylor Swift!", "Taylor Swift") == 1.0
    assert compute_exact_match("Python", "Java") == 0.0

    # Token F1
    assert compute_token_f1("senior software engineer", "software engineer") > 0.7
    assert compute_token_f1("cats and dogs", "dogs and cats") == 1.0
    assert compute_token_f1("apple", "banana") == 0.0

    # Substring Match
    assert compute_substring_match("I have a black lab named Trooper", "Trooper") == 1.0

    # IR Metrics (Recall, Precision, MRR, NDCG)
    retrieved = ["doc_A", "doc_B", "doc_C", "doc_D"]
    relevant = ["doc_B", "doc_X"]

    metrics = compute_retrieval_metrics(retrieved, relevant, k_values=[1, 2, 4])
    # doc_B is at rank 2
    assert metrics["mrr"] == 0.5  # 1/2
    assert metrics["recall@1"] == 0.0
    assert metrics["recall@2"] == 0.5  # 1 out of 2 found
    assert metrics["precision@2"] == 0.5  # 1 hit out of 2 retrieved
    assert metrics["recall@4"] == 0.5


@pytest.mark.dataset
def test_longmemeval_adapter_loading():
    """Verify LongMemEval adapter loads real dataset preserving categories and evidence."""
    adapter = LongMemEvalAdapter()
    assert adapter.benchmark_name == "longmemeval"

    docs = adapter.load_documents(limit=5)
    assert len(docs) == 5
    first_doc = docs[0]
    assert first_doc.doc_id.startswith("longmemeval:")
    assert len(first_doc.text) > 0
    assert "date" in first_doc.metadata

    examples = adapter.load_examples(limit=5)
    assert len(examples) == 5
    first_ex = examples[0]
    assert first_ex.example_id is not None
    assert len(first_ex.query) > 0
    assert first_ex.category is not None
    assert first_ex.gold_answer is not None
    assert len(first_ex.ground_truth_ids) > 0


@pytest.mark.dataset
def test_locomo_adapter_loading():
    """Verify LoCoMo adapter loads real dataset preserving session structure and QA categories."""
    adapter = LoCoMoAdapter()
    assert adapter.benchmark_name == "locomo"

    docs = adapter.load_documents(limit=5)
    assert len(docs) == 5
    first_doc = docs[0]
    assert "session" in first_doc.metadata
    assert len(first_doc.text) > 0

    examples = adapter.load_examples(limit=5)
    assert len(examples) == 5
    first_ex = examples[0]
    assert first_ex.category in [
        "factual",
        "temporal",
        "multi_hop_reasoning",
        "preference",
        "general",
    ]
    assert first_ex.gold_answer is not None


@pytest.mark.dataset
def test_dmr_adapter_loading():
    """Verify DMR adapter loads multi-session conversation dialogues and QA pairs."""
    adapter = DMRAdapter()
    assert adapter.benchmark_name == "dmr"

    docs = adapter.load_documents(limit=5)
    assert len(docs) == 5
    assert len(docs[0].text) > 0

    examples = adapter.load_examples(limit=5)
    assert len(examples) == 5
    assert len(examples[0].query) > 0
    assert examples[0].gold_answer is not None


def test_benchmark_evaluator_stages(tmp_path):
    """Verify separation of Ingestion, Retrieval, Generation, and Scoring stages."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        from tests.test_evaluation_regressions import FixtureAdapter

        adapter = FixtureAdapter()
        evaluator = BenchmarkEvaluator(engine=engine, adapter=adapter, k=3)

        # 1. Ingestion Stage
        docs = [
            BenchmarkDocument(
                doc_id="longmemeval:sess_01",
                text="Speaker 1: I graduated from Harvard with a degree in Computer Science.\nSpeaker 2: That is great!",
                session_id="sess_01",
                timestamp=1700000000,
            ),
            BenchmarkDocument(
                doc_id="longmemeval:sess_02",
                text="Speaker 1: I bought a blue electric bike for commuting to work.\nSpeaker 2: Sounds eco-friendly.",
                session_id="sess_02",
                timestamp=1700100000,
            ),
        ]
        ingest_res = evaluator.ingest_documents(docs)
        assert ingest_res["num_documents"] == 2
        assert ingest_res["ingested_ids"] == 2

        # 2. Retrieval, Generation & Scoring Stage
        example = BenchmarkExample(
            example_id="q_degree_test",
            query="What degree did I graduate with?",
            ground_truth_ids=["longmemeval:sess_01"],
            gold_answer="Computer Science",
            category="attribute_retrieval",
        )

        res = evaluator.evaluate_example(example, run_id="test_run_01")
        assert isinstance(res, EvaluationResult)
        assert len(res.retrieved_ids) > 0
        assert "longmemeval:sess_01" in res.retrieved_ids
        assert res.retrieval_metrics["recall@3"] == 1.0
        assert res.retrieval_metrics["mrr"] > 0.0
        assert res.predicted_answer is not None
        assert res.answer_metrics["substring_match"] == 1.0


@pytest.mark.dataset
def test_benchmark_runner_and_resumability(tmp_path):
    """Verify BenchmarkRunner persists per-example outputs and supports resuming."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    results_dir = str(tmp_path / "results")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        runner = BenchmarkRunner(output_dir=results_dir, run_id="smoke_test_run")

        # Run small smoke test on DMR
        class CoveredDMRAdapter(DMRAdapter):
            def load_documents(self, limit=None):
                selected = {
                    mid
                    for e in self.load_examples(limit=2)
                    for mid in e.ground_truth_ids
                }
                return [d for d in super().load_documents() if d.doc_id in selected]

        adapter = CoveredDMRAdapter()
        summary = runner.run_benchmark(
            benchmark_name="dmr",
            adapter=adapter,
            engine=engine,
            max_documents=4,
            max_examples=2,
            retrieval_mode="vector",
            k=3,
            resume=True,
            is_smoke_test=True,
        )

        assert summary["benchmark"] == "dmr"
        assert summary["is_smoke_test"] is True
        assert Path(summary["run_file"]).exists()

        # Check JSONL content
        lines = Path(summary["run_file"]).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        first_record = json.loads(lines[0])
        assert "retrieval_metrics" in first_record
        assert "query" in first_record

        # Test Resumability: running again with resume=True should not re-run existing examples
        summary2 = runner.run_benchmark(
            benchmark_name="dmr",
            adapter=adapter,
            engine=engine,
            max_documents=4,
            max_examples=2,
            retrieval_mode="vector",
            k=3,
            resume=True,
            is_smoke_test=True,
        )
        lines2 = Path(summary2["run_file"]).read_text(encoding="utf-8").splitlines()
        # Number of lines must still be 2 (no duplicates appended)
        assert len(lines2) == 2
