"""Shared fixtures for agent tests.

Uses the REAL MemoryEngine (temp Qdrant path; FalkorDB from compose when
reachable) so gateway contract tests exercise Iron Web itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.memory_gateway.engine_factory import build_engine  # noqa: E402
from agents.memory_gateway.gateway import MemoryGateway  # noqa: E402
from agents.travel_tools.base import MockTravelBackend, set_backend  # noqa: E402


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    import uuid

    config = {
        "qdrant": {"path": str(tmp_path_factory.mktemp("qdrant") / "qdrant")},
        "retrieval": {"reranker_enabled": False},
    }
    # Isolated FalkorDB graph so tests never touch the shared iron_web graph.
    graph_name = f"agents_test_{uuid.uuid4().hex[:12]}"
    engine, graph_live = build_engine(config=config, graph_name=graph_name)
    yield engine
    try:
        if graph_live:
            engine.graph_store.execute("MATCH (n) DETACH DELETE n")
    except Exception:
        pass
    engine.close()


@pytest.fixture()
def gateway(engine):
    return MemoryGateway(engine=engine)


@pytest.fixture()
def mock_backend():
    """Force deterministic mock travel data; restored after each test."""
    previous = None
    set_backend(MockTravelBackend())
    yield
    from agents.travel_tools.base import reset_backend

    reset_backend()
