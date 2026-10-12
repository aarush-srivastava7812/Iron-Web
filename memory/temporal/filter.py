"""
Temporal filtering utilities for time-aware memory retrieval.
Handles valid_from/valid_until bitemporal logic.
"""
from typing import List, Dict, Any, Optional
import time


def filter_by_time(
    candidates: List[Dict[str, Any]],
    query_time: int,
    mode: str = "now"  # "now", "historical", "all"
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
    candidate: Dict[str, Any],
    query_time: int,
    half_life_days: float = 90.0
) -> float:
    """
    Compute temporal relevance weight based on recency.
    
    Uses exponential decay with configurable half-life.
    Weight = exp(-age_days / half_life_days)
    """
    payload = candidate.get("payload", {})
    timestamp = payload.get("timestamp", query_time)
    
    age_seconds = query_time - timestamp
    age_days = age_seconds / 86400.0
    
    if age_days < 0:
        age_days = 0
    
    return float(2 ** (-age_days / half_life_days))


def get_historical_relevance(
    candidate: Dict[str, Any],
    query_time: int,
    query_entities: List[str]
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
    entity_match = len(set(query_entities) & set(entity_ids)) / max(len(query_entities), 1)
    
    if is_historical:
        return 0.5 + 0.5 * entity_match
    else:
        return 0.1 * entity_match  # Small bonus for entity match in current memories


def resolve_temporal_conflicts(
    candidates: List[Dict[str, Any]],
    query_time: int
) -> List[Dict[str, Any]]:
    """
    Resolve temporal conflicts (same entity, overlapping validity).
    
    For each entity, keep the most relevant valid memory at query_time.
    """
    # Group by entity
    entity_groups = {}
    for cand in candidates:
        payload = cand.get("payload", {})
        entity_ids = payload.get("entity_ids", [])
        for eid in entity_ids:
            if eid not in entity_groups:
                entity_groups[eid] = []
            entity_groups[eid].append(cand)
    
    resolved = []
    seen_ids = set()
    
    for eid, group in entity_groups.items():
        # Filter to valid at query_time
        valid_now = [c for c in group if filter_by_time([c], query_time, "now")]
        valid_hist = [c for c in group if filter_by_time([c], query_time, "historical")]
        
        # Prefer current valid memory
        if valid_now:
            best = max(valid_now, key=lambda x: x.get("final_score", x.get("score", 0)))
            if best.get("memory_id") not in seen_ids:
                resolved.append(best)
                seen_ids.add(best.get("memory_id"))
        elif valid_hist:
            # For historical queries, keep the most recent historical
            best = max(valid_hist, key=lambda x: x.get("payload", {}).get("valid_until", 0))
            if best.get("memory_id") not in seen_ids:
                resolved.append(best)
                seen_ids.add(best.get("memory_id"))
    
    # Add candidates without entity_ids
    for cand in candidates:
        mem_id = cand.get("memory_id")
        if mem_id and mem_id not in seen_ids:
            payload = cand.get("payload", {})
            if not payload.get("entity_ids"):
                resolved.append(cand)
                seen_ids.add(mem_id)
    
    return resolved


class TemporalFilter:
    """
    Temporal filter class for time-aware retrieval.
    Wraps the functional API for object-oriented usage.
    """
    
    def __init__(
        self,
        half_life_days: float = 90.0,
        default_mode: str = "now"
    ):
        self.half_life_days = half_life_days
        self.default_mode = default_mode
    
    def filter(self, candidates: List[Dict[str, Any]], query_time: int, mode: str = None) -> List[Dict[str, Any]]:
        """Filter candidates by temporal validity."""
        return filter_by_time(candidates, query_time, mode or self.default_mode)
    
    def weight(self, candidate: Dict[str, Any], query_time: int) -> float:
        """Compute temporal weight for a candidate."""
        return get_temporal_weight(candidate, query_time, self.half_life_days)
    
    def historical_relevance(self, candidate: Dict[str, Any], query_time: int, query_entities: List[str]) -> float:
        """Compute historical relevance."""
        return get_historical_relevance(candidate, query_time, query_entities)
    
    def resolve_conflicts(self, candidates: List[Dict[str, Any]], query_time: int) -> List[Dict[str, Any]]:
        """Resolve temporal conflicts."""
        return resolve_temporal_conflicts(candidates, query_time)