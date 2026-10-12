"""Evaluation bookkeeping checks use declared fixture data, not model-quality claims."""
import json
import pytest
from memory.engine import MemoryEngine
from memory.evaluation.harness.base import BenchmarkAdapter, BenchmarkDocument, BenchmarkExample, EvaluationResult
from memory.evaluation.harness.evaluator import BenchmarkEvaluator
from memory.evaluation.harness.runner import BenchmarkRunner
from memory.evaluation.harness.dates import parse_timestamp
from memory.evaluation.retrieval_metrics import compute_retrieval_metrics, average_precision


class FixtureAdapter(BenchmarkAdapter):
    benchmark_name = "fixture"

    def load_documents(self, limit=None):
        return [BenchmarkDocument("doc", "known answer", timestamp=100)][:limit]

    def load_examples(self, limit=None):
        return [BenchmarkExample("one", "known", ["doc"], "known answer"),
                BenchmarkExample("two", "answer", ["doc"], "known answer")][:limit]


@pytest.fixture
def setup_run(tmp_path):
    engine = MemoryEngine(config={}, qdrant_path=str(tmp_path/"vectors"), kuzu_path=str(tmp_path/"graph.db"))
    runner = BenchmarkRunner(str(tmp_path/"results"), "fixture_run")
    yield engine, runner
    engine.close()


def run(setup_run, **options):
    engine, runner = setup_run
    return runner.run_benchmark("fixture", engine, adapter=FixtureAdapter(), is_smoke_test=True, **options)


def test_resume_aggregates_saved_results_without_reingestion(setup_run):
    first = run(setup_run, k=3)
    second = run(setup_run, k=3)
    assert second["evaluation"]["total_examples"] == first["evaluation"]["total_examples"] == 2
    assert second["evaluation"]["retrieval"] == first["evaluation"]["retrieval"]
    assert second["ingestion"]["ingested_ids"] == 0
    assert second["resumed_examples"] == 2


def test_incompatible_resume_is_rejected(setup_run):
    run(setup_run, k=3)
    with pytest.raises(ValueError, match="Resume settings"):
        run(setup_run, k=4)
    with pytest.raises(FileExistsError):
        run(setup_run, k=3, resume=False)


def test_failed_examples_are_retried(setup_run, monkeypatch):
    original = BenchmarkEvaluator.evaluate_example
    def fail(self, example, run_id):
        if example.example_id == "one":
            raise RuntimeError("injected failure")
        return original(self, example, run_id)
    monkeypatch.setattr(BenchmarkEvaluator, "evaluate_example", fail)
    first = run(setup_run)
    assert first["evaluation"]["failed_examples"] == 1
    monkeypatch.setattr(BenchmarkEvaluator, "evaluate_example", original)
    second = run(setup_run)
    assert second["evaluation"]["failed_examples"] == 0
    assert second["evaluation"]["total_examples"] == 2
    assert len(open(second["run_file"], encoding="utf-8").read().splitlines()) == 2


def test_malformed_checkpoint_is_reported(setup_run):
    from pathlib import Path
    result = run(setup_run)
    Path(result["run_file"]).write_text("broken JSON", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        run(setup_run)


def test_missing_evidence_is_declared_and_excluded(setup_run):
    class Partial(FixtureAdapter):
        def load_examples(self, limit=None):
            return [BenchmarkExample("one", "known", ["doc"]), BenchmarkExample("missing", "absent", ["absent"])]
    engine, runner = setup_run
    result = runner.run_benchmark("fixture", engine, adapter=Partial(), is_smoke_test=True)
    assert result["coverage"]["excluded_missing_evidence"] == ["missing"]
    assert result["evaluation"]["total_examples"] == 1


def test_mock_is_rejected_outside_smoke(setup_run):
    engine, runner = setup_run
    with pytest.raises(ValueError, match="Mock extraction"):
        runner.run_benchmark("fixture", engine, adapter=FixtureAdapter())


def test_metrics_do_not_match_ambiguous_suffixes_or_repeat_credit():
    assert compute_retrieval_metrics(["other:doc"], ["doc"])["recall@10"] == 0
    values = compute_retrieval_metrics(["doc", "doc"], ["doc", "doc"], [2])
    assert values["precision@2"] == .5
    assert values["ndcg@2"] == 1
    assert average_precision(["doc", "doc"], ["doc", "doc"]) == 1


def test_actual_dataset_dates_are_utc():
    assert parse_timestamp("2023/05/20 (Sat) 02:21") == parse_timestamp("2023-05-20T02:21:00Z")
    assert parse_timestamp("1:56 pm on 8 May, 2023") == parse_timestamp("2023-05-08T13:56:00Z")
    assert parse_timestamp("") is None
    with pytest.raises(ValueError):
        parse_timestamp("invalid date")


def test_aggregation_uses_all_metric_keys_after_an_error(setup_run):
    engine, _ = setup_run
    evaluator = BenchmarkEvaluator(engine, FixtureAdapter())
    error = EvaluationResult("r", "fixture", "one", "q", [], [], {}, error="failure")
    good = EvaluationResult("r", "fixture", "two", "q", ["doc"], ["doc"], {"recall@10": 1}, answer_metrics={"token_f1": 1})
    metrics = evaluator.aggregate_results([error, good])
    assert metrics["failed_examples"] == 1
    assert metrics["answer"]["token_f1"] == metrics["retrieval"]["recall@10"] == 1
