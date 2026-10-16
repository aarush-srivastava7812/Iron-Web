"""Turn raw MemoryEngine search hits into compact, provenance-carrying context."""
from __future__ import annotations

from agents.config import settings
from agents.schemas import MemoryContext, MemoryItem, MemoryProvenance

_CANDIDATE_FIELDS = ("memory_id", "content", "score", "metadata", "timestamp",
                     "valid_from", "valid_until", "importance", "is_superseded",
                     "retrieval_method")


def _field(hit: object, name: str):
    if isinstance(hit, dict):
        return hit.get(name)
    return getattr(hit, name, None)


def build_context(
    *,
    query: str,
    user_id: str,
    agent_id: str,
    hits: list,
    k: int,
    graph_live: bool,
    retrieval_mode: str,
) -> MemoryContext:
    """Filter to the requesting user, cap size, and keep provenance."""
    items: list[MemoryItem] = []
    for hit in hits:
        metadata = _field(hit, "metadata") or {}
        if not isinstance(metadata, dict):
            continue
        # Ownership boundary: never leak another user's memories.
        if metadata.get("user_id") != user_id:
            continue
        provenance = MemoryProvenance(
            memory_id=str(_field(hit, "memory_id") or ""),
            score=_field(hit, "score"),
            agent_id=metadata.get("agent_id"),
            timestamp=_field(hit, "timestamp"),
            valid_from=_field(hit, "valid_from"),
            valid_until=_field(hit, "valid_until"),
            importance=_field(hit, "importance"),
            is_superseded=bool(_field(hit, "is_superseded") or False),
            retrieval_method=str(_field(hit, "retrieval_method") or retrieval_mode),
        )
        items.append(MemoryItem(content=str(_field(hit, "content") or ""), provenance=provenance))
        if len(items) >= k:
            break
    truncated = len(items) >= k
    # Final size cap keeps agent prompts bounded.
    while items and sum(len(item.content) for item in items) > settings.max_context_chars:
        items.pop()
        truncated = True
    return MemoryContext(
        query=query,
        user_id=user_id,
        agent_id=agent_id,
        items=items,
        truncated=truncated,
        graph_live=graph_live,
        retrieval_mode=retrieval_mode,
    )
