"""Exact document-ID metrics. Repeated IDs consume ranks but earn no extra credit."""

import math


def recall_at_k(retrieved, relevant, k):
    gold = set(relevant)
    return len(set(retrieved[: max(k, 0)]) & gold) / len(gold) if gold else 0.0


def precision_at_k(retrieved, relevant, k):
    return len(set(retrieved[:k]) & set(relevant)) / k if k > 0 else 0.0


def mrr(retrieved, relevant):
    gold = set(relevant)
    for rank, item in enumerate(retrieved, 1):
        if item in gold:
            return 1.0 / rank
    return 0.0


mean_reciprocal_rank = mrr


def ndcg_at_k(retrieved, relevant, k):
    gold, seen, gain = set(relevant), set(), 0.0
    for rank, item in enumerate(retrieved[: max(k, 0)], 1):
        if item in gold and item not in seen:
            gain += 1.0 / math.log2(rank + 1)
        seen.add(item)
    ideal = sum(
        1.0 / math.log2(rank + 1) for rank in range(1, min(len(gold), max(k, 0)) + 1)
    )
    return gain / ideal if ideal else 0.0


def average_precision(retrieved, relevant):
    gold, seen, hits, total = set(relevant), set(), 0, 0.0
    for rank, item in enumerate(retrieved, 1):
        if item in gold and item not in seen:
            hits += 1
            total += hits / rank
        seen.add(item)
    return total / len(gold) if gold else 0.0


def compute_retrieval_metrics(retrieved, relevant, k_values=None):
    metrics = {"mrr": mrr(retrieved, relevant)}
    for k in [1, 3, 5, 10] if k_values is None else k_values:
        if k < 1:
            raise ValueError("Metric cutoffs must be positive.")
        metrics.update(
            {
                f"recall@{k}": recall_at_k(retrieved, relevant, k),
                f"precision@{k}": precision_at_k(retrieved, relevant, k),
                f"ndcg@{k}": ndcg_at_k(retrieved, relevant, k),
            }
        )
    return metrics
