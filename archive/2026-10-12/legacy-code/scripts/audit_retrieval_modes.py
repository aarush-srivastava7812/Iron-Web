"""Read-only execution audit proving each benchmark retriever's active path."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.engine import MemoryEngine


def main() -> None:
    query = "What is Caroline connected to through project dependencies?"
    with MemoryEngine(
        qdrant_path=str(ROOT / "data" / "benchmark_runs_competitors" / "qdrant_locomo_hybrid"),
        kuzu_path=str(ROOT / "data" / "benchmark_runs_competitors" / "kuzu.db_locomo_hybrid.db"),
        use_gpu=False,
    ) as engine:
        audit = {}
        for mode in ("vector", "zep", "mem0", "mempalace", "hybrid"):
            results = engine.search(query, k=10, retrieval_mode=mode)
            audit[mode] = {
                "count": len(results),
                "methods": sorted({item.retrieval_method for item in results}),
                "ids": [item.memory_id for item in results],
                "hybrid_route": results[0].retrieval_trace.get("route") if mode == "hybrid" and results else None,
                "hybrid_stage_ms": results[0].retrieval_trace.get("stage_ms") if mode == "hybrid" and results else None,
            }
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
