"""
Evaluation metrics: Recall@K, Precision@K, MRR, NDCG, Answer Quality.
"""

from typing import List, Dict, Any
import numpy as np


from memory.evaluation.retrieval_metrics import (
    recall_at_k,
    precision_at_k,
    mrr,
    ndcg_at_k,
    average_precision,
)


def map_score(results: List[Dict], relevant_map: Dict[str, List[str]]) -> float:
    """Mean Average Precision across queries."""
    aps = []
    for r in results:
        scenario_id = r.get("query_id", r.get("scenario_id", ""))
        relevant = r.get("ground_truth_ids", relevant_map.get(scenario_id, []))
        ap = average_precision(r["retrieved_ids"], relevant)
        aps.append(ap)
    return np.mean(aps) if aps else 0.0


def compute_all_metrics(
    retrieved: List[str], relevant: List[str], k_values: List[int] = None
) -> Dict[str, float]:
    """Compute all metrics for one query."""
    k_values = k_values or [1, 3, 5, 10]

    metrics = {}
    for k in k_values:
        metrics[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
        metrics[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)

    metrics["mrr"] = mrr(retrieved, relevant)
    metrics["ap"] = average_precision(retrieved, relevant)

    return metrics


def evaluate_retrieval(results: List[Dict[str, Any]], k: int = 10) -> Dict[str, float]:
    """
    Evaluate retrieval results across multiple queries.

    Args:
        results: List of dicts with 'retrieved_ids' and 'ground_truth_ids'
        k: Top-K for evaluation

    Returns:
        Dict of aggregated metrics
    """
    if not results:
        return {}

    all_recalls = []
    all_precisions = []
    all_f1s = []
    all_mrrs = []
    all_ndcgs = []

    for r in results:
        retrieved = r.get("retrieved_ids", [])
        relevant = r.get("ground_truth_ids", [])

        recall = recall_at_k(retrieved, relevant, k)
        precision = precision_at_k(retrieved, relevant, k)

        if recall + precision > 0:
            f1 = 2 * recall * precision / (recall + precision)
        else:
            f1 = 0.0

        all_recalls.append(recall)
        all_precisions.append(precision)
        all_f1s.append(f1)
        all_mrrs.append(mrr(retrieved, relevant))
        all_ndcgs.append(ndcg_at_k(retrieved, relevant, k))

    # MAP
    map_val = map_score(
        results,
        {
            r.get("query_id", str(i)): r.get("ground_truth_ids", [])
            for i, r in enumerate(results)
        },
    )

    return {
        f"recall@{k}": float(np.mean(all_recalls)),
        f"precision@{k}": float(np.mean(all_precisions)),
        f"f1@{k}": float(np.mean(all_f1s)),
        "mrr": float(np.mean(all_mrrs)),
        f"ndcg@{k}": float(np.mean(all_ndcgs)),
        "map": float(map_val),
    }


def aggregate_metrics(metrics_list: List[Dict[str, float]]) -> Dict[str, float]:
    """Aggregate metrics from multiple runs."""
    if not metrics_list:
        return {}

    aggregated = {}
    for key in metrics_list[0].keys():
        values = [m.get(key, 0) for m in metrics_list]
        aggregated[f"{key}_mean"] = float(np.mean(values))
        aggregated[f"{key}_std"] = float(np.std(values))
        aggregated[f"{key}_min"] = float(np.min(values))
        aggregated[f"{key}_max"] = float(np.max(values))

    return aggregated
