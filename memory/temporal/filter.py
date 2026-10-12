"""
Temporal filtering utilities for time-aware memory retrieval.
Applies explicit fact-validity intervals independently of record creation time.
"""

from typing import List, Dict, Any


def filter_by_time(
    candidates: List[Dict[str, Any]],
    query_time: int,
    mode: str = "now",  # "now", "historical", "all"
) -> List[Dict[str, Any]]:
    """
    Filter candidates by temporal validity.

    Args:
        candidates: List of candidate memories with payload
        query_time: Unix timestamp of query
        mode: "now" (valid at query_time), "historical" (expired), "all" (no filter)

    Returns:
        Filtered candidates
    """
    if mode not in {"now", "historical", "auto", "all"}:
        raise ValueError("Unknown temporal mode.")
    if mode in {"all", "auto"}:
        return candidates

    filtered = []
    for cand in candidates:
        payload = cand.get("payload", {})
        valid_from = payload.get("valid_from", 0)
        valid_until = payload.get("valid_until", 2**63 - 1)

        if mode == "now":
            if valid_from <= query_time <= valid_until:
                filtered.append(cand)
        elif mode == "historical":
            if valid_until < query_time:
                filtered.append(cand)

    return filtered


def get_temporal_weight(
    candidate: Dict[str, Any], query_time: int, half_life_days: float = 90.0
) -> float:
    """
    Compute temporal relevance weight based on recency.

    Uses exponential decay with configurable half-life.
    Weight = 2 ** (-age_days / half_life_days)
    """
    payload = candidate.get("payload", {})
    timestamp = payload.get("timestamp", query_time)

    age_seconds = query_time - timestamp
    age_days = age_seconds / 86400.0

    if age_days < 0:
        age_days = 0

    return float(2 ** (-age_days / half_life_days))


def get_historical_relevance(
    candidate: Dict[str, Any], query_time: int, query_entities: List[str]
) -> float:
    """
    Compute historical relevance for temporal queries.

    High if:
    - Memory is expired (valid_until < query_time) AND query is historical
    - Memory entity matches query entities
    """
    payload = candidate.get("payload", {})
    valid_until = payload.get("valid_until", 2**63 - 1)
    entity_ids = payload.get("entity_ids", [])

    is_historical = valid_until < query_time
    entity_match = len(set(query_entities) & set(entity_ids)) / max(
        len(query_entities), 1
    )

    if is_historical:
        return 0.5 + 0.5 * entity_match
    else:
        return 0.1 * entity_match  # Small bonus for entity match in current memories


def resolve_temporal_conflicts(
    candidates: List[Dict[str, Any]], query_time: int
) -> List[Dict[str, Any]]:
    """Keep valid memories and deduplicate IDs; a shared entity does not imply a conflict."""
    valid = filter_by_time(candidates, query_time, "now")
    unique = {}
    for candidate in valid:
        mid = candidate.get("memory_id")
        if mid and (
            mid not in unique
            or candidate.get("final_score", candidate.get("score", 0))
            > unique[mid].get("final_score", unique[mid].get("score", 0))
        ):
            unique[mid] = candidate
    return list(unique.values())


class TemporalFilter:
    """
    Temporal filter class for time-aware retrieval.
    Wraps the functional API for object-oriented usage.
    """

    def __init__(self, half_life_days: float = 90.0, default_mode: str = "now"):
        self.half_life_days = half_life_days
        self.default_mode = default_mode

    def filter(
        self, candidates: List[Dict[str, Any]], query_time: int, mode: str = None
    ) -> List[Dict[str, Any]]:
        """Filter candidates by temporal validity."""
        return filter_by_time(candidates, query_time, mode or self.default_mode)

    def weight(self, candidate: Dict[str, Any], query_time: int) -> float:
        """Compute temporal weight for a candidate."""
        return get_temporal_weight(candidate, query_time, self.half_life_days)

    def historical_relevance(
        self, candidate: Dict[str, Any], query_time: int, query_entities: List[str]
    ) -> float:
        """Compute historical relevance."""
        return get_historical_relevance(candidate, query_time, query_entities)

    def resolve_conflicts(
        self, candidates: List[Dict[str, Any]], query_time: int
    ) -> List[Dict[str, Any]]:
        """Resolve temporal conflicts."""
        return resolve_temporal_conflicts(candidates, query_time)
