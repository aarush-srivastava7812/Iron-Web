import pytest
from concurrent.futures import ThreadPoolExecutor
from memory.engine import MemoryEngine
from memory.models import EngineStorageError
from memory.ingestion.pipeline import IngestionPipeline
from memory.graph import KuzuGraphStore


@pytest.fixture
def engine(tmp_path):
    with MemoryEngine(
        config={},
        qdrant_path=str(tmp_path / "vectors"),
        kuzu_path=str(tmp_path / "graph.db"),
    ) as instance:
        yield instance


def test_batch_validates_later_items_before_first_write(engine):
    with pytest.raises(ValueError):
        engine.add_batch(["valid", " "])
    assert engine.vector_store.count() == 0
    with pytest.raises(ValueError):
        engine.add_batch([], metadatas=[{}])


def test_graph_only_get_recovers_entity_observations(engine):
    engine.add("fact", memory_id="one", entity_ids=["topic"])
    engine.vector_store.delete_memory("one")
    record = engine.get("one")
    assert record.content == "fact" and not record.vector_stored and record.graph_stored


def test_borrowed_stores_remain_open_after_adapter_close(engine):
    borrowed = MemoryEngine(
        config={}, vector_store=engine.vector_store, graph_store=engine.graph_store
    )
    borrowed.close()
    engine.add("still open", memory_id="one", entity_ids=[])
    assert engine.get("one")


def test_enrichment_failure_rolls_back_ingestion(engine):
    class FailingDetector:
        def detect_contradictions(self, *args, **kwargs):
            raise RuntimeError("injected enrichment failure")

    pipeline = IngestionPipeline(
        engine.embedder,
        engine.vector_store,
        engine.graph_store,
        extractor=engine.extractor,
        contradiction_detector=FailingDetector(),
    )
    with pytest.raises(EngineStorageError) as error:
        pipeline.ingest_text("python fact", memory_id="one")
    assert error.value.rolled_back and engine.get("one") is None


def test_threaded_writes_share_store_lock(engine):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda i: engine.add(
                    f"fact {i}", memory_id=f"record_{i}", entity_ids=["topic"]
                ),
                range(12),
            )
        )
    assert engine.vector_store.count() == 12
    assert engine.graph_store.get_node_counts()["Observation"] == 12


def test_relationship_versions_and_owner_deletion(engine):
    for eid in ("one", "two"):
        engine.graph_store.upsert_entity(eid, eid, "Concept")
    graph = engine.graph_store
    graph.upsert_relation(
        "one",
        "two",
        "RELATED_TO",
        valid_from=0,
        valid_until=99,
        metadata={"source_memory_id": "old"},
    )
    graph.upsert_relation(
        "one",
        "two",
        "RELATED_TO",
        valid_from=100,
        valid_until=200,
        metadata={"source_memory_id": "new"},
    )
    assert len(graph.get_relations("one", valid_at=50)) == 1
    assert len(graph.get_relations("one", valid_at=150)) == 1
    assert graph.get_edge_counts()["RELATES"] == 2
    graph.delete_memory("old")
    assert graph.get_edge_counts()["RELATES"] == 1
    assert len(graph.get_relations("one", valid_at=150)) == 1


def test_metadata_is_not_a_live_reference(engine):
    metadata = {"nested": {"value": "original"}}
    engine.add("fact", memory_id="one", entity_ids=[], metadata=metadata)
    metadata["nested"]["value"] = "changed"
    record = engine.get("one")
    record.metadata["nested"]["value"] = "changed again"
    assert engine.get("one").metadata["nested"]["value"] == "original"


def test_legacy_observation_schema_is_migrated(tmp_path):
    import kuzu

    path = str(tmp_path / "legacy.db")
    database = kuzu.Database(path)
    connection = kuzu.Connection(database)
    connection.execute(
        "CREATE NODE TABLE Observation(id STRING, entity_id STRING, content STRING, embedding STRING, valid_from INT64, valid_until INT64, importance DOUBLE, source STRING, created_at INT64, PRIMARY KEY(id))"
    )
    connection.close()
    database.close()
    with KuzuGraphStore(path) as graph:
        graph.upsert_observation(
            "obs_one_topic", "topic", "fact", source_memory_id="one"
        )
        assert graph.get_memory_observations("one")[0]["source_memory_id"] == "one"


def test_preview_does_not_load_models(engine, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Preview initialized a model")

    monkeypatch.setattr("memory.engine.get_embedder", fail)
    assert engine.run_maintenance(tasks=[], dry_run=True) == {}
    assert engine.run_maintenance(dry_run=True)["consolidate"]["patterns_stored"] == 0


def test_episodes_and_separate_users_survive_deduplication(engine):
    for i in range(2):
        engine.add(
            "episode",
            memory_id=f"episode_{i}",
            entity_ids=[],
            metadata={"memory_type": "episodic"},
        )
        engine.add(
            "fact", memory_id=f"user_{i}", entity_ids=[], metadata={"user_id": str(i)}
        )
    assert engine.deduplicate_memories()["merged"] == 0
