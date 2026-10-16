"""One-off cleanup: remove orphaned test observations from the shared graph.

Gateway writes during development/tests went to a temp Qdrant but, while
FalkorDB was live, their graph side-effects landed in the shared ``iron_web``
graph. This script deletes graph observations whose source memory id does not
exist in the real Qdrant collection (i.e. orphans), plus any leftover
``agents_test_*`` graphs. Run once: python agents/scripts/cleanup_shared_graph.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from memory.engine import MemoryEngine  # noqa: E402
from memory.graph.falkordb_store import FalkorDBGraphStore  # noqa: E402


def main() -> None:
    real_engine = MemoryEngine()
    real_ids = set(real_engine.memory_ids())
    print(f"real qdrant memories: {len(real_ids)}")

    graph = real_engine.graph_store
    if not isinstance(graph, FalkorDBGraphStore):
        print("graph store is not FalkorDB; nothing to clean")
        return

    result = graph.execute(
        "MATCH (o:Observation) WHERE o.source_memory_id IS NOT NULL "
        "RETURN DISTINCT o.source_memory_id"
    )
    orphan_ids = []
    while result.has_next():
        mid = result.get_next()[0]
        if mid and mid not in real_ids and mid.startswith("mem_"):
            orphan_ids.append(mid)
    print(f"orphaned graph memories to delete: {len(orphan_ids)}")
    for mid in orphan_ids:
        graph.delete_memory(mid, clean_orphaned_entities=True)
    print("cleanup complete")
    real_engine.close()


if __name__ == "__main__":
    main()
