"""Integration seam for the external long-term memory system (owned by the project author).

Intentionally NOT wired into any route yet. Implement `MemoryProvider` against your system
and inject it where the assistant endpoint is added later.
"""
from typing import Any, Protocol


class MemoryProvider(Protocol):
    def append(self, user_id: str, session_id: str, event: dict[str, Any]) -> None: ...
    def recall(self, user_id: str, query: str, k: int = 8) -> list[dict[str, Any]]: ...
    def profile(self, user_id: str) -> dict[str, Any]: ...
    def forget(self, user_id: str, item_id: str) -> None: ...


class NullMemoryProvider:
    def append(self, user_id, session_id, event): pass
    def recall(self, user_id, query, k=8): return []
    def profile(self, user_id): return {}
    def forget(self, user_id, item_id): pass
