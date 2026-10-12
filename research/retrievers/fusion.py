"""Actual reciprocal-rank fusion for the explicit research baseline."""


def reciprocal_rank_fusion(streams, k=60, top_k=10):
    if k < 1 or top_k < 1:
        raise ValueError("Fusion limits must be positive.")
    merged = {}
    for stream in streams:
        seen = set()
        for rank, hit in enumerate(stream, 1):
            mid = hit["memory_id"]
            if mid in seen:
                continue
            seen.add(mid)
            item = merged.setdefault(mid, dict(hit, rrf_score=0.0))
            item["rrf_score"] += 1.0 / (k + rank)
    return sorted(
        merged.values(), key=lambda hit: (-hit["rrf_score"], hit["memory_id"])
    )[:top_k]
