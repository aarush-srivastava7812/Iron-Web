"""Access policies for Memory Gateway retrieval and writes."""
from __future__ import annotations

import re

from agents.config import settings
from agents.schemas import MemoryWriteProposal

_NOISE_PATTERNS = [
    re.compile(r"^(?:\b(?:ok|okay|thanks|thank you|hi|hello|hey)\b[.,!\s]*)+$", re.IGNORECASE),
    re.compile(r"\b(api[_ -]?key|password|secret|token|credit card)\b", re.IGNORECASE),
]


def can_access(user_id: str, requesting_agent: str) -> bool:
    """Baseline access control: a valid user and a known agent id are required."""
    return bool(user_id) and bool(requesting_agent) and len(user_id) <= 64


def retrieval_mode_for(requested: str | None, graph_live: bool) -> str:
    """Pick a retrieval mode the current engine actually supports."""
    mode = (requested or "vector").lower()
    if mode in {"hybrid", "graph", "hybrid_no_rerank", "hybrid_no_temporal", "hybrid_no_graph"}:
        return mode if graph_live else "vector"
    return mode if mode in {"vector", "auto"} else "vector"


def is_noise(content: str) -> str | None:
    """Return a rejection reason when content is unsuitable for long-term memory."""
    text = (content or "").strip()
    if len(text) < 8:
        return "too short to be a durable memory"
    for pattern in _NOISE_PATTERNS:
        if pattern.search(text):
            return "credentials or conversational noise are never stored"
    return None


def write_worthy(proposal: MemoryWriteProposal) -> str | None:
    """Policy gate for proposed long-term writes; returns a rejection reason or None."""
    noise = is_noise(proposal.content)
    if noise:
        return noise
    if proposal.importance < settings.min_write_importance:
        return f"importance below policy minimum ({settings.min_write_importance})"
    if proposal.confidence < 0.5:
        return "confidence too low for durable storage"
    return None


def scope_metadata(proposal: MemoryWriteProposal) -> dict[str, object]:
    """Ownership metadata attached to every stored memory record."""
    return {
        "user_id": proposal.user_id,
        "session_id": proposal.session_id,
        "agent_id": proposal.agent_id,
        "task_id": proposal.task_id,
        "kind": proposal.kind,
        "confidence": proposal.confidence,
    }
