"""A real subprocess terminates at controlled service publication boundaries."""

# ruff: noqa: E402
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memory.engine import MemoryEngine
from memory.graph.connection import GraphLease
from memory.shared.service import SharedMemoryService
from tests.conftest import FixtureEmbedder

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
boundary = sys.argv[2]


def factory(path, name):
    engine = MemoryEngine(
        config={"extraction_policy": "none"},
        qdrant_path=str(path),
        graph_name=name,
        embedder=FixtureEmbedder(),
    )
    # Test-specific short lease so a killed owner expires quickly; no server
    # configuration or other graph's lease is modified.
    engine.graph_store.write_lock = GraphLease(
        engine.graph_store.redis,
        engine.graph_store.lock_key,
        lease_seconds=2,
        wait_seconds=10,
    )
    return engine


def fault(stage, row, engine):
    if stage != "prepared":
        return
    if boundary == "vector":
        original = engine.vector_store.upsert_memory

        def insert(*args, **kwargs):
            original(*args, **kwargs)
            os._exit(72)

        engine.vector_store.upsert_memory = insert
    elif boundary in {"graph", "vector_loss"}:
        original = engine.graph_store.commit

        def publish():
            original()
            if boundary == "vector_loss":
                engine.vector_store.delete_memory(row["memory_id"])
            os._exit(72)

        engine.graph_store.commit = publish


service = SharedMemoryService(
    config["root"],
    config["records"],
    namespace=config["namespace"],
    engine_factory=factory,
    autostart=False,
    fault_hook=fault,
)
if boundary == "receipt":
    os._exit(72)
service.process_one()
raise RuntimeError("Expected controlled process termination did not happen")
