"""
Graph store module - Kuzu embedded implementation.
"""
from memory.graph.kuzu_store import KuzuGraphStore, RelationType

# Type alias for backward compatibility
GraphStore = KuzuGraphStore

# Simple factory for backward compatibility
def create_graph_store(store_type: str = "kuzu", **kwargs):
    """Factory to create graph store instance (Kuzu only)."""
    if store_type != "kuzu":
        raise ValueError(f"Only 'kuzu' graph store is supported, got: {store_type}")
    return KuzuGraphStore(**kwargs)

__all__ = [
    "KuzuGraphStore",
    "RelationType",
    "create_graph_store",
    "GraphStore",
]