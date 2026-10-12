"""
Automated tests for Phase 1: Storage foundation stabilization.
Tests verify:
1. Qdrant local persistence across close and reopen.
2. Kuzu local persistence across close and reopen.
3. Kuzu observation lookup and deletion with referential integrity.
4. Kuzu memory deletion and orphaned entity cleanup.
5. Shared identifier alignment across Qdrant and Kuzu.
"""
import numpy as np
import pytest

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph.kuzu_store import KuzuGraphStore
from memory.contradiction.detector import ContradictionDetector


def test_qdrant_write_close_reopen(tmp_path):
    """Qdrant local storage must persist points, payload, and vectors across store reopen."""
    qdrant_dir = str(tmp_path / "qdrant_db")
    dim = 4

    # 1. Write data
    store1 = QdrantVectorStore(
        path=qdrant_dir,
        collection_name="test_memories",
        dimension=dim,
        distance="Cosine",
        quantization=False,
    )
    vec1 = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    vec2 = np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float32)

    store1.upsert_memory(
        memory_id="mem_001",
        text="I use Java for DSA",
        embedding=vec1,
        entity_ids=["java", "dsa"],
        valid_from=1000,
        valid_until=2000,
        importance=0.9,
    )
    store1.upsert_memory(
        memory_id="mem_002",
        text="I use Python for ML",
        embedding=vec2,
        entity_ids=["python", "ml"],
        valid_from=1500,
        valid_until=3000,
        importance=0.8,
    )
    assert store1.count() == 2
    store1.close()

    # 2. Reopen store from same directory
    store2 = QdrantVectorStore(
        path=qdrant_dir,
        collection_name="test_memories",
        dimension=dim,
        distance="Cosine",
        quantization=False,
    )
    assert store2.count() == 2

    mem1 = store2.get_memory("mem_001")
    assert mem1 is not None
    assert mem1["payload"]["memory_id"] == "mem_001"
    assert mem1["payload"]["text"] == "I use Java for DSA"
    assert mem1["payload"]["entity_ids"] == ["java", "dsa"]
    assert mem1["payload"]["importance"] == 0.9

    # Test search on reopened store
    search_hits = store2.search(query_embedding=vec1, k=1)
    assert len(search_hits) == 1
    assert search_hits[0]["payload"]["memory_id"] == "mem_001"

    # Test delete on reopened store
    assert store2.delete_memory("mem_001") is True
    assert store2.count() == 1
    assert store2.get_memory("mem_001") is None
    assert store2.get_memory("mem_002") is not None

    store2.close()


def test_kuzu_write_close_reopen(tmp_path):
    """Kuzu local storage must persist entities, relations, and observations across reopen."""
    kuzu_path = str(tmp_path / "kuzu.db")

    # 1. Write entities, relations, observations
    store1 = KuzuGraphStore(db_path=kuzu_path)
    store1.upsert_entity(
        entity_id="java",
        name="Java",
        entity_type="Technology",
        description="Programming Language",
        importance=0.95,
        timestamp=1000,
    )
    store1.upsert_entity(
        entity_id="dsa",
        name="DSA",
        entity_type="Topic",
        description="Data Structures and Algorithms",
        importance=0.9,
        timestamp=1000,
    )
    store1.upsert_relation(
        from_id="java",
        to_id="dsa",
        relation_type="USED_FOR",
        confidence=0.98,
        valid_from=1000,
        valid_until=5000,
        timestamp=1000,
    )
    store1.upsert_observation(
        obs_id="obs_001",
        entity_id="java",
        content="User uses Java for DSA",
        embedding=[0.1, 0.2, 0.3],
        valid_from=1000,
        valid_until=5000,
        importance=0.9,
        source="unit_test",
        timestamp=1000,
    )

    counts1 = store1.get_node_counts()
    assert counts1["Entity"] == 2
    assert counts1["Observation"] == 1
    store1.close()

    # 2. Reopen store from same database file
    store2 = KuzuGraphStore(db_path=kuzu_path)
    counts2 = store2.get_node_counts()
    assert counts2["Entity"] == 2
    assert counts2["Observation"] == 1

    # Verify entity retrieval
    entity = store2.get_entity("java")
    assert entity is not None
    assert entity["id"] == "java"
    assert entity["name"] == "Java"
    assert entity["importance"] == 0.95

    # Verify relation retrieval
    relations = store2.get_relations("java", valid_at=2000)
    assert len(relations) >= 1
    assert relations[0]["from_id"] == "java"
    assert relations[0]["to_id"] == "dsa"
    assert relations[0]["relation_type"] == "USED_FOR"

    # Verify observation retrieval via new get_observation method
    obs = store2.get_observation("obs_001")
    assert obs is not None
    assert obs["id"] == "obs_001"
    assert obs["entity_id"] == "java"
    assert obs["content"] == "User uses Java for DSA"
    assert obs["embedding"] == [0.1, 0.2, 0.3]
    assert obs["valid_from"] == 1000
    assert obs["valid_until"] == 5000

    store2.close()


def test_kuzu_referential_integrity_and_deletion(tmp_path):
    """Test deletion semantics: observation deletion and referential-integrity-guarded entity deletion."""
    kuzu_path = str(tmp_path / "integrity.db")
    store = KuzuGraphStore(db_path=kuzu_path)

    store.upsert_entity(entity_id="python", name="Python", entity_type="Technology")
    store.upsert_observation(
        obs_id="obs_py",
        entity_id="python",
        content="I practice Python",
    )

    # 1. Non-existent ID deletion must return False
    assert store.delete_observation("nonexistent_obs") is False
    assert store.delete_entity("nonexistent_ent") is False

    # 2. Deleting an entity referenced by an active observation with force=False must be rejected
    assert store.delete_entity("python", force=False) is False
    assert store.get_entity("python") is not None

    # 3. Deleting observation must succeed
    assert store.delete_observation("obs_py") is True
    assert store.get_observation("obs_py") is None

    # 4. Once observation is removed, safe entity deletion must succeed
    assert store.delete_entity("python", force=False) is True
    assert store.get_entity("python") is None

    # 5. Forced deletion should remove entity regardless
    store.upsert_entity(entity_id="cpp", name="C++", entity_type="Technology")
    store.upsert_observation(obs_id="obs_cpp", entity_id="cpp", content="I used C++")
    assert store.delete_entity("cpp", force=True) is True
    assert store.get_entity("cpp") is None

    store.close()


def test_kuzu_delete_memory(tmp_path):
    """Test delete_memory cleans up all related observations for that memory."""
    kuzu_path = str(tmp_path / "memory_del.db")
    store = KuzuGraphStore(db_path=kuzu_path)

    store.upsert_entity(entity_id="e1", name="Entity 1", entity_type="Concept")
    store.upsert_entity(entity_id="e2", name="Entity 2", entity_type="Concept")

    # Ingestion pipeline names observations obs_{memory_id}_{entity_id}
    store.upsert_observation(
        obs_id="obs_memA_e1",
        entity_id="e1",
        content="Memory A regarding e1",
    )
    store.upsert_observation(
        obs_id="obs_memA_e2",
        entity_id="e2",
        content="Memory A regarding e2",
    )
    store.upsert_observation(
        obs_id="obs_memB_e1",
        entity_id="e1",
        content="Memory B regarding e1",
    )

    # Deleting memory A
    assert store.delete_memory("memA", clean_orphaned_entities=True) is True
    assert store.get_observation("obs_memA_e1") is None
    assert store.get_observation("obs_memA_e2") is None

    # Memory B's observation still exists
    assert store.get_observation("obs_memB_e1") is not None

    # Entity e1 still exists (referenced by memB), but e2 had no other observations so it was cleaned up
    assert store.get_entity("e1") is not None
    assert store.get_entity("e2") is None

    # Deleting non-existent memory returns False
    assert store.delete_memory("mem_nonexistent") is False

    store.close()


def test_shared_identifier_alignment(tmp_path):
    """Verify consistent shared memory_id usage across Qdrant, Kuzu, and ContradictionDetector."""
    qdrant_dir = str(tmp_path / "shared_qdrant")
    kuzu_path = str(tmp_path / "shared_kuzu.db")

    qdrant = QdrantVectorStore(
        path=qdrant_dir,
        collection_name="shared_test",
        dimension=4,
        distance="Cosine",
        quantization=False,
    )
    kuzu = KuzuGraphStore(db_path=kuzu_path)

    memory_id = "mem_shared_123"
    entity_id = "lang_java"

    # Write to Qdrant with memory_id
    qdrant.upsert_memory(
        memory_id=memory_id,
        text="I use Java for DSA",
        embedding=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        entity_ids=[entity_id],
    )

    # Write to Kuzu with aligned entity and observation
    obs_id = f"obs_{memory_id}_{entity_id}"
    kuzu.upsert_entity(entity_id=entity_id, name="Java", entity_type="Technology")
    kuzu.upsert_observation(
        obs_id=obs_id,
        entity_id=entity_id,
        content="I use Java for DSA",
        embedding=[0.1, 0.2, 0.3, 0.4],
    )

    # Verify Qdrant has point by memory_id
    q_mem = qdrant.get_memory(memory_id)
    assert q_mem is not None
    assert q_mem["payload"]["memory_id"] == memory_id

    # Verify Kuzu has observation by obs_id
    k_obs = kuzu.get_observation(obs_id)
    assert k_obs is not None
    assert k_obs["id"] == obs_id
    assert k_obs["entity_id"] == entity_id

    # Verify ContradictionDetector can resolve the observation through Kuzu
    detector = ContradictionDetector(
        embedder=None,  # Not needed for _get_observation test
        graph_store=kuzu,
    )
    resolved_obs = detector._get_observation(obs_id)
    assert resolved_obs is not None
    assert resolved_obs["id"] == obs_id
    assert resolved_obs["entity_ids"] == [entity_id]
    assert resolved_obs["content"] == "I use Java for DSA"

    qdrant.close()
    kuzu.close()
