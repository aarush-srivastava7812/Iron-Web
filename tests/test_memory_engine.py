"""
Unit and integration tests for MemoryEngine (Phase 2).
Verifies:
1. Unified CRUD operations (add, get, search, update, delete).
2. Consistent cross-store memory IDs between Qdrant and FalkorDB.
3. Partial write failure and compensating rollback on add.
4. Partial write failure and compensating rollback on update.
5. Preservation of shared graph entities across memory deletions.
6. Local persistence across engine close and reopen.
7. Device status, VRAM telemetry, and CPU fallback reporting.
8. Safe batch ingestion.
"""

from tests.fixtures.graph import graph_name_for

import pytest

# Retained pre-migration engine contracts; native application checks live in main.py.
from memory.engine import LegacyMemoryEngine as MemoryEngine
from memory.models import EngineStorageError, MemoryRecord, MemorySearchResult


def test_engine_add_get_and_search(tmp_path):
    """Verify add, get, and search in both vector and hybrid retrieval modes."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    ) as engine:
        mem_id = engine.add(
            content="I use Java for Data Structures and Algorithms",
            metadata={"session_id": "sess_101", "source": "chat"},
            entity_ids=["java", "dsa"],
            valid_from=1000,
            valid_until=9000,
            importance=0.95,
        )
        assert mem_id.startswith("mem_")

        # 1. Test get
        record = engine.get(mem_id)
        assert record is not None
        assert isinstance(record, MemoryRecord)
        assert record.memory_id == mem_id
        assert record.content == "I use Java for Data Structures and Algorithms"
        assert record.entity_ids == ["java", "dsa"]
        assert record.importance == 0.95
        assert record.metadata.get("session_id") == "sess_101"
        assert record.vector_stored is True
        assert record.graph_stored is True

        # 2. Test vector search
        v_results = engine.search(
            "Which programming language for DSA?", k=3, retrieval_mode="vector"
        )
        assert len(v_results) >= 1
        assert isinstance(v_results[0], MemorySearchResult)
        assert v_results[0].memory_id == mem_id
        assert v_results[0].retrieval_method == "vector"
        assert v_results[0].score > 0.0

        # 3. Test hybrid search
        h_results = engine.search(
            "Which programming language for DSA?", k=3, retrieval_mode="hybrid"
        )
        assert len(h_results) >= 1
        assert isinstance(h_results[0], MemorySearchResult)
        assert h_results[0].memory_id == mem_id


def test_engine_update_and_reopen_persistence(tmp_path):
    """Verify memory updates and disk persistence across engine close and reopen."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    # Session 1: Ingest memory
    engine1 = MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    )
    mem_id = engine1.add(
        content="Initial belief: Python is fast enough for low-level systems programming",
        entity_ids=["python", "systems"],
        importance=0.6,
    )
    engine1.close()

    # Session 2: Reopen from disk, verify, update
    engine2 = MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    )
    loaded = engine2.get(mem_id)
    assert loaded is not None
    assert "Initial belief" in loaded.content

    # Perform update
    updated = engine2.update(
        memory_id=mem_id,
        content="Updated belief: Rust is preferred for low-level systems programming",
        importance=0.99,
    )
    assert updated is True

    rec_updated = engine2.get(mem_id)
    assert "Rust is preferred" in rec_updated.content
    assert rec_updated.importance == 0.99
    engine2.close()

    # Session 3: Reopen again to confirm update persisted to disk
    engine3 = MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    )
    rec_persisted = engine3.get(mem_id)
    assert rec_persisted is not None
    assert "Rust is preferred" in rec_persisted.content
    assert rec_persisted.importance == 0.99
    engine3.close()


def test_engine_shared_entity_preservation_on_delete(tmp_path):
    """Deleting one memory must not destroy shared graph entities still referenced by other memories."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    ) as engine:
        # Both memories share entity 'python'
        mem_A = engine.add("I write data pipelines in Python", entity_ids=["python"])
        mem_B = engine.add("I write ML models in Python", entity_ids=["python"])

        # Verify entity exists
        ent = engine.graph_store.get_entity("python")
        assert ent is not None

        # Delete Memory A
        assert engine.delete(mem_A, clean_orphaned_entities=False) is True
        assert engine.get(mem_A) is None

        # Entity 'python' must still exist because Memory B references it
        assert engine.graph_store.get_entity("python") is not None
        assert engine.get(mem_B) is not None

        # Delete Memory B with orphan cleanup
        assert engine.delete(mem_B, clean_orphaned_entities=True) is True
        assert engine.get(mem_B) is None

        # Now python has no remaining observations and is cleaned up
        assert engine.graph_store.get_entity("python") is None


def test_engine_compensating_rollback_on_add_failure(tmp_path, monkeypatch):
    """If graph store write fails halfway during add(), vector store write must be rolled back."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    ) as engine:
        # Simulate catastrophic graph store crash during observation write
        def broken_upsert_observation(*args, **kwargs):
            raise RuntimeError("Simulated FalkorDB disk I/O failure")

        monkeypatch.setattr(
            engine.graph_store, "upsert_observation", broken_upsert_observation
        )

        # Attempt add()
        with pytest.raises(EngineStorageError) as exc_info:
            engine.add("This memory should be rolled back", entity_ids=["failure_test"])

        assert exc_info.value.rolled_back is True
        failed_id = exc_info.value.memory_id

        # Ensure compensating rollback removed the record from Qdrant
        assert engine.vector_store.count() == 0
        assert engine.vector_store.get_memory(failed_id) is None


def test_engine_compensating_rollback_on_update_failure(tmp_path, monkeypatch):
    """If graph observation update fails during update(), Qdrant point must be restored to original state."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    ) as engine:
        mem_id = engine.add("Original stable memory content", entity_ids=["test_topic"])

        # Simulate failure during graph observation update
        def broken_upsert_observation(*args, **kwargs):
            raise RuntimeError("Simulated FalkorDB connection timeout")

        monkeypatch.setattr(
            engine.graph_store, "upsert_observation", broken_upsert_observation
        )

        with pytest.raises(EngineStorageError) as exc_info:
            engine.update(mem_id, content="New corrupted content")

        assert exc_info.value.rolled_back is True

        # Verify Qdrant was restored to original content
        point = engine.vector_store.get_memory(mem_id)
        assert point["payload"]["text"] == "Original stable memory content"


def test_engine_device_status_and_telemetry(tmp_path):
    """Engine must report transparent hardware, provider, and VRAM telemetry."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    ) as engine:
        status_initial = engine.get_device_status()

        assert status_initial.gpu_enabled_requested is True
        assert (
            status_initial.safety_buffer_mb == 1024.0
        )  # 1.0 GB reserved safety buffer
        assert status_initial.vram_budget_mb <= 5120.0  # 5.0 GB maximum budget
        assert status_initial.embedder_provider == "Uninitialized"
        # Reranker should be Uninitialized initially to preserve memory / VRAM
        assert status_initial.reranker_provider == "Uninitialized"
        assert status_initial.execution_mode == "Uninitialized"
        assert len(status_initial.status_notes) > 0

        # Access reranker property to trigger lazy loading
        _ = engine.reranker
        status_loaded = engine.get_device_status()
        assert status_loaded.reranker_provider in [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]


def test_engine_batch_ingest(tmp_path):
    """Engine must support safe batch ingestion of multiple texts."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=True
    ) as engine:
        texts = [
            "Episode 1: Started learning Python basics",
            "Episode 2: Built a web scraper with Beautiful Soup",
            "Episode 3: Trained a decision tree with scikit-learn",
        ]
        metas = [{"episode": 1}, {"episode": 2}, {"episode": 3}]

        ids = engine.add_batch(contents=texts, metadatas=metas)
        assert len(ids) == 3
        assert len(set(ids)) == 3

        for mid in ids:
            rec = engine.get(mid)
            assert rec is not None
            assert rec.vector_stored is True
