"""Correctness cases reproduced before changing the implementation."""
import pytest
from memory.engine import MemoryEngine
from memory.models import EngineStorageError
from memory.evaluation.harness.base import ndcg_at_k, recall_at_k


@pytest.fixture
def engine(tmp_path):
    with MemoryEngine(qdrant_path=str(tmp_path / "qdrant"), kuzu_path=str(tmp_path / "graph.db"), use_gpu=False) as instance:
        yield instance


def test_delete_owns_exact_memory(engine):
    engine.add("first", memory_id="a", entity_ids=["topic"])
    engine.add("second", memory_id="a_b", entity_ids=["topic"])
    engine.delete("a")
    assert engine.get("a_b") is not None
    assert engine.graph_store.get_observation("obs_a_b_topic") is not None


def test_metadata_cannot_overwrite_record_fields(engine):
    with pytest.raises(ValueError):
        engine.add("original", memory_id="record", entity_ids=["topic"], metadata={"text": "other"})


def test_failed_replace_restores_previous_memory(engine, monkeypatch):
    engine.add("original", memory_id="record", entity_ids=["topic"])
    def fail(*args, **kwargs):
        raise RuntimeError("injected graph failure")
    monkeypatch.setattr(engine.graph_store, "upsert_observation", fail)
    with pytest.raises(EngineStorageError):
        engine.add("changed", memory_id="record", entity_ids=["topic"])
    assert engine.get("record").content == "original"
    assert engine.graph_store.get_observation("obs_record_topic")["content"] == "original"


def test_failed_partial_update_restores_entire_state(engine, monkeypatch):
    engine.add("original", memory_id="record", entity_ids=["one", "two"], metadata={"note": "old", "source": "chat"})
    original = engine.graph_store.upsert_observation
    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected second observation failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(engine.graph_store, "upsert_observation", fail_second)
    with pytest.raises(EngineStorageError):
        engine.update("record", content="changed", metadata={"note": "new"})
    assert engine.get("record").metadata["note"] == "old"
    for eid in ["one", "two"]:
        assert engine.graph_store.get_observation(f"obs_record_{eid}")["content"] == "original"


def test_update_preserves_graph_provenance(engine):
    engine.add("original", memory_id="record", entity_ids=["topic"], metadata={"source": "chat"})
    engine.update("record", metadata={"note": "new"})
    observation = engine.graph_store.get_observation("obs_record_topic")
    assert observation["source"] == "chat"
    assert observation["source_memory_id"] == "record"


def test_batch_lengths_are_checked(engine):
    with pytest.raises(ValueError):
        engine.add_batch(["one", "two"], metadatas=[{}])
    assert engine.vector_store.count() == 0


def test_failed_delete_restores_both_stores(engine, monkeypatch):
    engine.add("original", memory_id="record", entity_ids=["topic"])
    original = engine.graph_store.delete_memory
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected deletion failure")
    monkeypatch.setattr(engine.graph_store, "delete_memory", fail)
    with pytest.raises(EngineStorageError) as error:
        engine.delete("record")
    assert error.value.rolled_back
    assert engine.get("record").content == "original"
    assert engine.graph_store.get_observation("obs_record_topic") is not None


def test_failed_rollback_is_reported(engine, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("injected failure")
    monkeypatch.setattr(engine.graph_store, "upsert_observation", fail)
    monkeypatch.setattr(engine.vector_store, "restore_memory", fail)
    with pytest.raises(EngineStorageError) as error:
        engine.add("original", memory_id="record", entity_ids=["topic"])
    assert error.value.rolled_back is False


def test_vector_time_filter_is_per_request(engine):
    engine.add("expired fact", memory_id="expired", entity_ids=["topic"], valid_until=100)
    assert engine.search("fact", retrieval_mode="vector", query_time=200)
    assert engine.search("fact", retrieval_mode="vector", temporal_mode="now", query_time=200) == []


def test_repeated_document_is_not_extra_evidence():
    assert ndcg_at_k(["doc", "doc"], ["doc"], 2) <= 1.0


def test_empty_evidence_is_not_perfect_recall():
    assert recall_at_k([], [], 10) == 0.0
