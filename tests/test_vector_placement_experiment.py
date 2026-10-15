"""Real-service checks that protect the validity of the placement experiment."""

import uuid

import numpy as np
import pytest
from qdrant_client.models import Filter, FieldCondition, MatchValue

from memory.graph import FalkorDBGraphStore
from memory.vector_store.qdrant_store import QdrantVectorStore, create_search_filter
from scripts.vector_placement.falkor_vector import FalkorVectorExperiment


@pytest.fixture
def pair(tmp_path):
    graph = FalkorDBGraphStore("test_vector_bench_contract_" + uuid.uuid4().hex[:12])
    qdrant = QdrantVectorStore(str(tmp_path / "vectors"), dimension=3)
    falkor = FalkorVectorExperiment(graph, dimension=3)
    try:
        yield qdrant, falkor, graph
    finally:
        qdrant.close()
        graph.graph.delete()
        graph.close()


def add_pair(pair, mid, vector, **kwargs):
    for store in pair[:2]:
        store.upsert_memory(mid, "source " + mid, np.array(vector), timestamp=100, **kwargs)


def ids(hits):
    return [h["payload"]["memory_id"] for h in hits]


def test_cosine_distance_is_converted_and_ranked(pair):
    add_pair(pair, "same", [1, 0, 0])
    add_pair(pair, "orthogonal", [0, 1, 0])
    add_pair(pair, "opposite", [-1, 0, 0])
    outputs = [s.search(np.array([1, 0, 0]), k=3) for s in pair[:2]]
    assert ids(outputs[0]) == ids(outputs[1]) == ["same", "orthogonal", "opposite"]
    assert np.allclose([h["score"] for h in outputs[0]], [h["score"] for h in outputs[1]], atol=1e-6)
    assert ids(pair[1].search(np.array([1, 0, 0]), k=3, score_threshold=.5)) == ["same"]


def test_filtered_results_are_not_lost_outside_initial_top_k(pair):
    for i in range(12):
        add_pair(pair, "distractor_" + str(i), [1, .01*i, 0], valid_until=199)
    add_pair(pair, "current", [.5, .5, 0], valid_from=200)
    filt = create_search_filter(200, "now", ["current"])
    outputs = [s.search(np.array([1, 0, 0]), k=1, filter_condition=filt) for s in pair[:2]]
    assert ids(outputs[0]) == ids(outputs[1]) == ["current"]
    assert pair[1].last_overfetch > 1
    assert not pair[1].search(np.array([1, 0, 0]), filter_condition=create_search_filter(200, "auto", []))
    historic = create_search_filter(200, "historical")
    assert len(pair[1].search(np.array([1, 0, 0]), k=20, filter_condition=historic)) == 12


def test_snapshot_restore_and_payload_parity(pair):
    add_pair(pair, "record", [1, .2, 0], metadata={"source":"contract", "nested":{"a":[1,2]}}, importance=.7)
    snapshots = [s.get_memory("record") for s in pair[:2]]
    assert snapshots[0]["payload"] == snapshots[1]["payload"]
    assert np.allclose(snapshots[0]["vector"], snapshots[1]["vector"], atol=1e-6)
    for store, snapshot in zip(pair[:2], snapshots):
        store.upsert_memory("record", "changed", np.array([0, 1, 0]), timestamp=200)
        store.restore_memory("record", snapshot)
        assert store.get_memory("record")["payload"] == snapshot["payload"]
        store.restore_memory("record", None)
        assert store.get_memory("record") is None
        assert store.count() == 0


def test_unsupported_filter_cannot_silently_change_meaning(pair):
    filt = Filter(must=[FieldCondition(key="source", match=MatchValue(value="other"))])
    with pytest.raises(ValueError, match="Unsupported"):
        pair[1].search(np.array([1, 0, 0]), filter_condition=filt)


def test_guard_rejects_production_graph():
    class Production:
        graph_name = "iron_web"
    with pytest.raises(ValueError, match="isolated"):
        FalkorVectorExperiment(Production(), dimension=3)


def test_engine_coordinated_write_and_failed_write_restore(pair, monkeypatch):
    from memory.engine import MemoryEngine
    from memory.models import EngineStorageError

    class Embedding:
        dimension = 3
        def embed_single(self, text):
            return np.array([1, 0, 0], dtype=np.float32)

    native, graph = pair[1:]
    engine = MemoryEngine(vector_store=native, graph_store=graph, embedder=Embedding(),
                          config={"qdrant":{"vector_size":3},"extraction_policy":"none"})
    try:
        engine.add("Original evidence", memory_id="committed", timestamp=100)
        assert engine.get("committed").content == "Original evidence"
        assert engine.search("Original evidence", retrieval_mode="vector", k=1)[0].memory_id == "committed"
        original = native.get_memory("committed")
        def fail(*args, **kwargs):
            raise RuntimeError("Injected graph write failure")
        monkeypatch.setattr(graph, "upsert_observation", fail)
        with pytest.raises(EngineStorageError):
            engine.add("Changed evidence", memory_id="committed", timestamp=200)
        assert native.get_memory("committed")["payload"] == original["payload"]
        with pytest.raises(EngineStorageError):
            engine.add("New uncommitted evidence", memory_id="failed", timestamp=200)
        assert native.get_memory("failed") is None
        assert native.count() == native._size == 1
    finally:
        engine.close()
