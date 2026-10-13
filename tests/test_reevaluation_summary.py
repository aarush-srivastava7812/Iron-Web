"""Historical comparisons use current evidence and metrics without mutating old data."""

import pytest

from memory.evaluation.slices import FrozenSliceAdapter
from scripts.summarize_reevaluation import aggregate


def adapter():
    return FrozenSliceAdapter(
        dict(
            benchmark="fixture",
            documents=[dict(doc_id="doc", text="Paris")],
            examples=[
                dict(
                    example_id="one",
                    query="Capital?",
                    ground_truth_ids=["doc"],
                    gold_answer="Paris",
                    category="factual",
                ),
                dict(
                    example_id="empty",
                    query="Unknown?",
                    ground_truth_ids=[],
                    gold_answer=None,
                ),
            ],
        )
    )


def test_old_predictions_are_rescored_with_current_gold_and_exact_ids():
    old = [
        dict(
            example_id="one",
            query="Capital?",
            retrieved_ids=["other:doc", "doc", "doc"],
            relevant_ids=["other:doc"],
            prediction="Paris",
            latency_ms=12.0,
        )
    ]
    result = aggregate(old, adapter(), historical=True)
    assert result["retrieval"]["recall@1"] == 0
    assert result["retrieval"]["precision@3"] == pytest.approx(1 / 3)
    assert result["retrieval"]["mrr"] == 0.5
    assert result["answer"]["exact_match"] == 1
    assert result["latency"]["p95_retrieval_ms"] == 12
    assert old[0]["relevant_ids"] == ["other:doc"]


def test_unannotated_evidence_does_not_create_a_perfect_score():
    result = aggregate(
        [
            dict(
                example_id="empty",
                query="Unknown?",
                retrieved_ids=[],
                prediction="",
                latency_ms=1,
            )
        ],
        adapter(),
        historical=True,
    )
    assert result["retrieval"] == {}
    assert result["answer"] == {}
    assert result["retrieval_scored_examples"] == 0


def test_historical_query_identity_must_match():
    with pytest.raises(ValueError, match="questions differ"):
        aggregate(
            [dict(example_id="one", query="Different?", retrieved_ids=[])],
            adapter(),
            historical=True,
        )
