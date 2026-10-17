"""Workflow checkpointing.

LangGraph's MemorySaver keeps *execution* state (pending tasks, retries) so a
workflow can resume. It is deliberately separate from Iron Web durable memory.
A thread-local saver is shared per process; swap it via ``set_saver`` in tests.
"""
from __future__ import annotations

import threading
from typing import Any


class _MemorySaver:
    """Minimal in-memory checkpointer compatible with LangGraph's interface."""

    def __init__(self) -> None:
        self._store: dict[tuple, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def put(self, config: dict, checkpoint: dict, metadata: dict | None = None) -> None:
        key = self._key(config)
        with self._lock:
            self._store[key] = {"checkpoint": checkpoint, "metadata": metadata or {}}

    def get(self, config: dict) -> dict | None:
        with self._lock:
            entry = self._store.get(self._key(config))
            return entry["checkpoint"] if entry else None

    @staticmethod
    def _key(config: dict) -> tuple:
        configurable = (config or {}).get("configurable", {})
        return (configurable.get("thread_id", ""), configurable.get("checkpoint_ns", ""))

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_saver: Any = None
_lock = threading.Lock()


def get_saver():
    """Prefer LangGraph's MemorySaver; fall back to the local implementation.

    The serializer allowlist includes our own schemas so pydantic state
    round-trips cleanly instead of emitting deprecation warnings.
    """
    global _saver
    with _lock:
        if _saver is None:
            try:
                from langgraph.checkpoint.memory import MemorySaver
                from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
                from agents import schemas

                _saver = MemorySaver(serde=JsonPlusSerializer(
                    allowed_json_modules=[("agents.schemas", name)
                        for name, value in vars(schemas).items()
                        if isinstance(value, type) and value.__module__ == "agents.schemas"]
                ))
            except ImportError:
                _saver = _MemorySaver()
        return _saver


def set_saver(saver: Any) -> None:
    global _saver
    with _lock:
        _saver = saver


class _MemorySaverCompat(_MemorySaver):
    pass
