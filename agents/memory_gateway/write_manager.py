"""Controlled, duplicate-safe memory writes through the MemoryEngine."""
from __future__ import annotations

import hashlib
import time

from agents.config import settings
from agents.schemas import MemoryWriteProposal, WriteResult
from memory.models import EngineStorageError

from .policies import scope_metadata, write_worthy


def _dedupe_key(proposal: MemoryWriteProposal) -> str:
    digest = hashlib.sha1(
        f"{proposal.user_id}|{proposal.agent_id}|{proposal.content.strip().lower()}".encode()
    ).hexdigest()[:16]
    return f"mem_{digest}"


class WriteManager:
    """Applies write policies and stores approved proposals via engine.add.

    Deterministic memory ids (content + user + agent) make retries safe: a
    repeated proposal resolves to the same record instead of a duplicate.
    """

    def __init__(self, engine) -> None:
        self.engine = engine

    def propose_write(self, proposal: MemoryWriteProposal) -> WriteResult:
        reason = write_worthy(proposal)
        if reason:
            return WriteResult(status="rejected", reason=reason)

        memory_id = _dedupe_key(proposal)
        existing = self._get_existing(memory_id)
        if existing is not None:
            if proposal.replaces_memory_id and proposal.replaces_memory_id != memory_id:
                return self._store(proposal, memory_id)
            return WriteResult(status="duplicate", memory_id=memory_id,
                               reason="identical memory already stored")

        # Near-duplicate guard: same user + kind with very similar text.
        if self._near_duplicate(proposal):
            return WriteResult(status="duplicate",
                               reason="a very similar memory already exists")

        return self._store(proposal, memory_id)

    # ------------------------------------------------------------------
    def _get_existing(self, memory_id: str):
        try:
            return self.engine.get(memory_id)
        except Exception:
            return None

    def _near_duplicate(self, proposal: MemoryWriteProposal) -> bool:
        try:
            hits = self.engine.search(
                proposal.content[:200], k=settings.retrieval_overfetch,
                retrieval_mode="vector",
            )
        except Exception:
            return False
        normalized = proposal.content.strip().lower()
        for hit in hits:
            metadata = getattr(hit, "metadata", None) or (
                hit.get("metadata") if isinstance(hit, dict) else {}
            )
            if not isinstance(metadata, dict) or metadata.get("user_id") != proposal.user_id:
                continue
            if metadata.get("kind") != proposal.kind:
                continue
            content = str(getattr(hit, "content", "") or
                          (hit.get("content") if isinstance(hit, dict) else "")).strip().lower()
            if content and _similarity(normalized, content) >= 0.92:
                return True
        return False

    def _store(self, proposal: MemoryWriteProposal, memory_id: str) -> WriteResult:
        now = int(time.time())
        try:
            stored_id = self.engine.add(
                content=proposal.content.strip(),
                metadata=scope_metadata(proposal),
                timestamp=now,
                valid_from=now,
                importance=proposal.importance,
                memory_id=memory_id,
            )
        except EngineStorageError as error:
            # Engine already rolled the cross-store write back; surface it.
            return WriteResult(status="rejected", reason=f"storage error: {error}")
        except (ValueError, TypeError, RuntimeError) as error:
            return WriteResult(status="rejected", reason=str(error))
        return WriteResult(status="stored", memory_id=stored_id)


def _similarity(a: str, b: str) -> float:
    """Cheap token Jaccard similarity for the near-duplicate guard."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
