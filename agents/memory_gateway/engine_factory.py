"""Build the shared MemoryEngine without duplicating Iron Web.

The real MemoryEngine requires both Qdrant (local path) and FalkorDB. When
FalkorDB is unreachable we fall back to a vector-primary engine using a
minimal in-process graph stub so the coordinated-write path still runs; such
an engine is clearly labeled ``graph_live=False`` by the gateway.
"""
from __future__ import annotations

import threading
from typing import Any

from memory.engine import MemoryEngine


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class StubGraphStore:
    """In-process FalkorDBGraphStore stand-in for offline development.

    It keeps the engine's coordinated-write flow operational (entities,
    relations and observations are accepted and tracked in memory) and always
    reports empty graph expansion. Never used when FalkorDB is reachable.
    """

    def __init__(self) -> None:
        self.write_lock = _NullLock()
        self._observations: dict[str, list[dict[str, Any]]] = {}

    # -- writes -------------------------------------------------------------
    def upsert_entity(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return {"id": kwargs.get("entity_id") or (args[0] if args else None), "stub": True}

    def upsert_relation(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return {"stub": True}

    def upsert_observation(self, observation=None, **kwargs):  # noqa: ANN002, ANN003
        record = dict(observation or {})
        owner = record.get("source_memory_id") or kwargs.get("source_memory_id")
        if owner:
            self._observations.setdefault(owner, []).append(record)
        return record

    # -- reads --------------------------------------------------------------
    def get_memory_observations(self, memory_id):  # noqa: ANN001
        return list(self._observations.get(memory_id, []))

    def get_memory_relations(self, memory_id):  # noqa: ANN001
        return []

    def expand_graph(self, seed_entity_ids, *args, **kwargs):  # noqa: ANN002, ANN003
        return [], []

    def get_relationship_conflicts_batch(self, memory_ids):  # noqa: ANN001
        return {memory_id: [] for memory_id in memory_ids}

    def find_entities_by_name(self, name, limit=10):  # noqa: ANN001, ANN002
        return []

    def get_entity(self, entity_id):  # noqa: ANN001
        return None

    def get_contradictions(self, obs_id):  # noqa: ANN001
        return []

    def get_supersessions(self, obs_id):  # noqa: ANN001
        return []

    def add_contradiction(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return {"stub": True}

    def add_supersession(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return {"stub": True}

    # -- maintenance ---------------------------------------------------------
    def delete_memory(self, memory_id, clean_orphaned_entities=False):  # noqa: ANN001, ANN003
        self._observations.pop(memory_id, None)
        return True

    def get_node_counts(self):
        return 0

    def get_edge_counts(self):
        return 0

    def close(self):
        return None


_engine_lock = threading.Lock()
_shared_engine: MemoryEngine | None = None
_shared_graph_live = False


def build_engine(
    config: dict[str, Any] | None = None,
    *,
    vector_only: bool = False,
    graph_name: str | None = None,
):
    """Return ``(engine, graph_live)``. ``vector_only`` skips FalkorDB entirely.

    ``graph_name`` isolates a run's graph data (used by tests) without touching
    the shared ``iron_web`` graph.
    """
    if vector_only:
        return MemoryEngine(config=config, graph_store=StubGraphStore()), False
    try:
        return MemoryEngine(config=config, graph_name=graph_name), True
    except Exception:
        return MemoryEngine(config=config, graph_store=StubGraphStore()), False


def get_shared_engine(
    *, vector_only: bool = False, config: dict[str, Any] | None = None,
    graph_name: str | None = None,
):
    """Process-wide engine so all agents share one embedder/model load."""
    global _shared_engine, _shared_graph_live
    with _engine_lock:
        if _shared_engine is None:
            _shared_engine, _shared_graph_live = build_engine(
                config=config, vector_only=vector_only, graph_name=graph_name,
            )
        return _shared_engine, _shared_graph_live


def reset_shared_engine() -> None:
    """Test helper: drop the cached engine (closing it first)."""
    global _shared_engine, _shared_graph_live
    with _engine_lock:
        if _shared_engine is not None:
            try:
                _shared_engine.close()
            except Exception:
                pass
        _shared_engine = None
        _shared_graph_live = False
