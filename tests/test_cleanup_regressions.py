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


def test_similar_distinct_facts_survive_deduplication(engine):
    engine.add("I drink coffee", memory_id="coffee", entity_ids=["topic"])
    engine.add("I never drink coffee", memory_id="no_coffee", entity_ids=["topic"])
    assert engine.deduplicate_memories(eps=1.0)["merged"] == 0
    assert engine.get("coffee") and engine.get("no_coffee")


def test_no_fabricated_consolidation(engine):
    for i in range(3):
        engine.add(f"episode {i}", metadata={"memory_type": "episodic"})
    assert engine.consolidate_memories()["patterns_stored"] == 0
    assert engine.run_maintenance(tasks=[]) == {}


def test_chunking_terminates_and_validates():
    from memory.ingestion.pipeline import IngestionPipeline
    assert IngestionPipeline._chunk_text("short text", 20, 3) == ["short text"]
    assert IngestionPipeline._chunk_text("abcdefghij", 5, 2) == ["abcde", "defgh", "ghij"]
    with pytest.raises(ValueError):
        IngestionPipeline._chunk_text("text", 5, 5)


def test_incomplete_json_is_rejected():
    from memory.ingestion.nim_extractor import NIMExtractor
    extractor = object.__new__(NIMExtractor)
    with pytest.raises(ValueError):
        extractor._parse_json_from_response('{"entities": [{"name": "Python"}]')


def test_entity_identity_is_cross_document():
    from memory.ingestion.extractor import canonicalize_entities
    first = canonicalize_entities({"entities": [{"id": "ent_1", "name": "Python"}]})
    other = canonicalize_entities({"entities": [{"id": "ent_1", "name": "Java"}]})
    repeat = canonicalize_entities({"entities": [{"id": "ent_2", "name": "Python"}]})
    assert first["entities"][0]["id"] != other["entities"][0]["id"]
    assert first["entities"][0]["id"] == repeat["entities"][0]["id"]


@pytest.mark.real_extraction_policy
def test_default_does_not_select_a_mock(engine):
    assert engine.extractor is None
    engine.add("plain text", memory_id="plain")
    assert engine.get("plain").entity_ids == []
    assert engine.get("plain").metadata["extraction_status"] == "disabled"


def test_extraction_failure_is_reported_before_writes(engine, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("invalid extraction")
    monkeypatch.setattr(engine.extractor, "extract_entities_and_relations", fail)
    with pytest.raises(ValueError):
        engine.add("fact")
    assert engine.vector_store.count() == 0


def test_exact_duplicates_merge_with_graph_and_provenance(engine):
    engine.add("same fact", memory_id="one", entity_ids=["one_topic"], importance=1, metadata={"source": "chat", "note": "one"})
    engine.add("same fact", memory_id="two", entity_ids=["two_topic"], importance=.5, metadata={"source": "file", "note": "two"})
    assert engine.deduplicate_memories(dry_run=True)["merged"] == 1
    assert engine.get("two")
    assert engine.deduplicate_memories()["merged"] == 1
    assert engine.get("two") is None
    assert engine.graph_store.get_observation("obs_one_two_topic")
    assert engine.get("one").metadata["note"] == "one"
    assert engine.get("one").metadata["merged_records"][0]["payload"]["note"] == "two"


def test_duplicate_conflicts_are_checked_for_entity_observations(engine):
    engine.add("same fact", memory_id="one", entity_ids=["topic"])
    engine.add("same fact", memory_id="two", entity_ids=["topic"])
    engine.graph_store.add_contradiction(from_id="one", to_id="two", confidence=1)
    assert engine.deduplicate_memories()["merged"] == 0


def test_failed_deduplication_restores_cluster(engine, monkeypatch):
    engine.add("same fact", memory_id="one", entity_ids=["topic"])
    engine.add("same fact", memory_id="two", entity_ids=["topic"])
    def fail(*args, **kwargs):
        raise RuntimeError("injected observation failure")
    monkeypatch.setattr(engine.graph_store, "upsert_observation", fail)
    with pytest.raises(EngineStorageError):
        engine.deduplicate_memories()
    assert engine.get("one") and engine.get("two")


def test_graph_returns_owner_once_with_metadata(engine):
    engine.add("fact about topic", memory_id="fact", entity_ids=["topic", "other"], metadata={"note": "provenance"})
    results = engine.search("topic", retrieval_mode="graph", k=10)
    assert [r.memory_id for r in results] == ["fact"]
    assert results[0].metadata["note"] == "provenance"


def test_hybrid_returns_more_than_fifteen_results(engine):
    for i in range(20):
        engine.add(f"topic fact {i}", memory_id=f"fact_{i}", entity_ids=["topic"])
    results = engine.search("topic previously", k=20)
    assert len(results) == 20
    assert len({r.memory_id for r in results}) == 20


def test_historical_graph_candidates_stay_historical(engine):
    engine.add("old fact about topic", memory_id="old", entity_ids=["topic"], valid_until=100)
    engine.add("current fact about topic", memory_id="new", entity_ids=["topic"], valid_from=100)
    for mode in ("graph", "hybrid"):
        results = engine.search("topic", temporal_mode="historical", query_time=200, retrieval_mode=mode)
        assert [r.memory_id for r in results] == ["old"]


def test_supersession_direction_and_effective_time(engine):
    engine.add("old topic", memory_id="old", entity_ids=["topic"])
    engine.add("new topic", memory_id="new", entity_ids=["topic"])
    engine.graph_store.add_supersession("old", "new", .9, superseded_at=200)
    before = {r.memory_id: r for r in engine.search("topic", query_time=100)}
    after = {r.memory_id: r for r in engine.search("topic", query_time=300)}
    assert not before["old"].is_superseded
    assert after["old"].is_superseded and not after["new"].is_superseded


def test_cpu_reranking_keeps_complete_candidate_pool(engine):
    for i in range(20):
        engine.add(f"topic {i}", memory_id=f"fact_{i}", entity_ids=["topic"])
    engine.config_data["retrieval"]["reranker_enabled"] = True
    results = engine.search("topic", k=20)
    assert len(results) == 20
    assert all(r.retrieval_trace["rerank_score"] is not None for r in results)


def test_graph_expansion_handles_quotes_and_one_hop(engine):
    engine.add("seed fact", entity_ids=["seed'quoted"])
    engine.add("middle fact", entity_ids=["middle"])
    engine.add("end fact", entity_ids=["end"])
    engine.graph_store.upsert_relation("seed'quoted", "middle", "RELATED_TO")
    engine.graph_store.upsert_relation("middle", "end", "RELATED_TO")
    nodes, _ = engine.graph_store.expand_graph(["seed'quoted"], hops=2)
    assert {n["id"] for n in nodes} == {"seed'quoted", "middle", "end"}


def test_invalid_settings_fail_explicitly():
    from memory.config import EngineSettings
    with pytest.raises(ValueError):
        EngineSettings.model_validate({"imaginary_setting": True})
    with pytest.raises(ValueError):
        EngineSettings.model_validate({"retrieval": {"graph_hops": 3}})
