"""Memory Gateway: the single controlled path between agents and Iron Web.

Agents never touch Qdrant or FalkorDB directly. Retrieval is task-specific and
user-scoped; writes go through the policy + duplicate guards in write_manager
and reuse the MemoryEngine's coordinated cross-store write with rollback.
"""
from __future__ import annotations

import logging
import time

from agents.config import settings
from agents.schemas import (
    MemoryContext,
    MemoryWriteProposal,
    WriteResult,
)

from .context_builder import build_context
from .engine_factory import get_shared_engine
from .policies import can_access, retrieval_mode_for
from .write_manager import WriteManager

logger = logging.getLogger(__name__)


class MemoryGateway:
    def __init__(self, engine=None, *, vector_only: bool = False) -> None:
        if engine is None:
            engine, graph_live = get_shared_engine(vector_only=vector_only)
        else:
            graph_live = getattr(engine, "graph_live", False)
        self.engine = engine
        self.graph_live = graph_live
        self.writes = WriteManager(engine)
        self._last_retrieval: tuple[str, str, str] | None = None
        self._last_context: MemoryContext | None = None

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def retrieve(
        self,
        *,
        query: str,
        user_id: str,
        session_id: str | None = None,
        agent_id: str,
        limit: int | None = None,
        temporal_mode: str = "auto",
        retrieval_mode: str | None = None,
        use_cache: bool = True,
    ) -> MemoryContext:
        """Task-scoped retrieval. Cache key = (query, user, agent) to avoid
        redundant repeated retrievals within one workflow run."""
        if not can_access(user_id, agent_id):
            return MemoryContext(query=query, user_id=user_id, agent_id=agent_id)
        cache_key = (query.strip().lower(), user_id, agent_id)
        if use_cache and self._last_retrieval == cache_key and self._last_context:
            return self._last_context

        k = min(max(limit or settings.retrieval_default_k, 1), 20)
        mode = retrieval_mode_for(retrieval_mode, self.graph_live)
        overfetch = k * settings.retrieval_overfetch
        started = time.perf_counter()
        try:
            hits = self.engine.search(
                query,
                k=min(overfetch, 100),
                temporal_mode=temporal_mode if temporal_mode in {"auto", "now", "historical"} else "auto",
                retrieval_mode=mode,
            )
        except Exception as error:  # retrieval must never break the workflow
            logger.warning("Memory retrieval failed for %s/%s: %s", agent_id, user_id, error)
            hits = []
        context = build_context(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            hits=list(hits or []),
            k=k,
            graph_live=self.graph_live,
            retrieval_mode=mode,
        )
        logger.debug("gateway.retrieve agent=%s hits=%d in %.1fms",
                     agent_id, len(context.items), (time.perf_counter() - started) * 1000)
        self._last_retrieval, self._last_context = cache_key, context
        return context

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def propose_write(self, proposal: MemoryWriteProposal) -> WriteResult:
        if not can_access(proposal.user_id, proposal.agent_id):
            return WriteResult(status="rejected", reason="access denied")
        return self.writes.propose_write(proposal)

    def propose_writes(self, proposals: list[MemoryWriteProposal]) -> list[WriteResult]:
        results = []
        for proposal in proposals:
            result = self.propose_write(proposal)
            if result.status == "stored":
                self._last_retrieval = None  # new facts invalidate the retrieval cache
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Introspection used by the resource monitor / dashboard
    # ------------------------------------------------------------------
    def device_status(self):
        try:
            return self.engine.get_device_status()
        except Exception:
            return None

    def close(self) -> None:
        try:
            self.engine.close()
        except Exception:
            pass
