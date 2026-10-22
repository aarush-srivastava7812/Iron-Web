"""Real FalkorDB integration checks for publication, rollback and shared clients."""

from concurrent.futures import ThreadPoolExecutor
import pytest
from memory.engine import LegacyMemoryEngine as MemoryEngine
from memory.graph import FalkorDBGraphStore
from memory.models import EngineStorageError
from tests.fixtures.graph import graph_name_for


def test_multiline_quoted_text_is_preserved(tmp_path):
    text = 'first\n second\t"quoted"\\literal\r end'
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_entity("quoted'", 'a "name"', "Concept", description=text)
        graph.upsert_observation("observation", "quoted'", text)
        assert graph.get_entity("quoted'")["description"] == text
        assert graph.get_observation("observation")["content"] == text
        assert graph.get_node_counts()["Entity"] == 1


def test_live_graph_does_not_expose_staging_writes(tmp_path):
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_entity("one", "original", "Concept")
        with graph.write_lock:
            graph.begin()
            graph.upsert_entity("one", "changed", "Concept")
            live = graph.db.select_graph(graph.graph_name)
            assert live.query("MATCH(n:Entity) RETURN n.name").result_set == [
                ["original"]
            ]
            graph.commit()
            assert live.query("MATCH(n:Entity) RETURN n.name").result_set == [
                ["changed"]
            ]
            graph.finish()


def test_lost_publication_response_restores_both_stores(tmp_path, monkeypatch):
    with MemoryEngine(
        config={},
        qdrant_path=str(tmp_path / "vectors"),
        graph_name=graph_name_for(tmp_path),
    ) as engine:
        engine.add("original", memory_id="one", entity_ids=["topic"])
        original = engine.graph_store.redis.eval
        failed = False

        def lost_response(script, *args):
            nonlocal failed
            result = original(script, *args)
            if not failed and "Staging graph is missing" in script:
                failed = True
                raise ConnectionError("Injected lost publication response")
            return result

        monkeypatch.setattr(engine.graph_store.redis, "eval", lost_response)
        with pytest.raises(EngineStorageError) as error:
            engine.add("replacement", memory_id="one", entity_ids=["different"])
        assert error.value.rolled_back
        assert engine.get("one").content == "original"
        assert (
            engine.graph_store.get_memory_observations("one")[0]["content"]
            == "original"
        )
        assert engine.graph_store.get_entity("different") is None


def test_shared_clients_refresh_entity_lookup_and_keep_unique_ids(tmp_path):
    name = graph_name_for(tmp_path)
    with FalkorDBGraphStore(name) as first, FalkorDBGraphStore(name) as second:
        assert first.get_entity_name_index() == []
        second.upsert_entity("one", "new name", "Concept")
        assert first.get_entity_name_index() == [("one", "new name")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(
                pool.map(
                    lambda graph: graph.upsert_entity("shared", "same", "Concept"),
                    [first, second],
                )
            )
        assert first.get_node_counts()["Entity"] == 2


def test_graph_lease_loss_rejects_publication(tmp_path):
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        with graph.write_lock:
            graph.begin()
            graph.upsert_entity("one", "unpublished", "Concept")
            graph.write_lock.failed = ConnectionError("injected renewal failure")
            with pytest.raises(RuntimeError, match="lease was lost"):
                graph.commit()
            graph.rollback()
            graph.write_lock.failed = None
        assert graph.get_node_counts()["Entity"] == 0


def test_native_identifier_constraints_reject_duplicate_nodes(tmp_path):
    from redis.exceptions import ResponseError

    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_entity("one", "original", "Concept")
        with pytest.raises(ResponseError):
            graph.execute("CREATE (:Entity {id:'one',name:'duplicate'})")
        with pytest.raises(ResponseError):
            graph.execute("CREATE (:Observation {content:'missing ID'})")
        assert graph.get_node_counts() == {"Entity": 1, "Observation": 0}


def test_capped_results_are_rejected_instead_of_silently_accepted(tmp_path):
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_entity("one", "first", "Concept")
        graph.upsert_entity("two", "second", "Concept")
        graph.result_limit = 1
        with pytest.raises(RuntimeError, match="complete results cannot be verified"):
            graph.get_entity_name_index()


def test_batched_seeds_preserve_order_missing_ids_and_node_limit(tmp_path, monkeypatch):
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        for eid in ("one", "two", "three"):
            graph.upsert_entity(eid, eid, "Concept")
        assert graph.get_entities(["two", "missing", "one", "two"]) == [
            graph.get_entity("two"),
            graph.get_entity("one"),
        ]
        monkeypatch.setattr(
            graph, "get_entity", lambda *args: pytest.fail("individual seed read")
        )
        entities, _ = graph.expand_graph(["two", "one", "three"], max_nodes=2)
        assert [e["id"] for e in entities] == ["two", "one"]


def test_conflict_cache_refreshes_across_clients_and_does_not_leak_mutations(
    tmp_path, monkeypatch
):
    name = graph_name_for(tmp_path)
    with FalkorDBGraphStore(name) as first, FalkorDBGraphStore(name) as second:
        first.upsert_observation("older", "", "old", source_memory_id="memory")
        first.upsert_observation("newer", "", "new", source_memory_id="replacement")
        assert first.get_relationship_conflicts_batch(["memory"]) == {"memory": []}
        second.add_supersession("older", "newer", 0.9, superseded_at=50)
        original = first.get_relationship_conflicts_batch(["memory", "older"])
        assert original["memory"][0]["direction"] == "outgoing"
        assert original["memory"][0]["effective_at"] == 50
        assert original["older"] == original["memory"]
        original["memory"][0]["direction"] = "corrupted"
        execute = first.conn.execute
        monkeypatch.setattr(
            first.conn, "execute", lambda *args: pytest.fail("cache reread")
        )
        assert (
            first.get_relationship_conflicts_batch(["memory"])["memory"][0]["direction"]
            == "outgoing"
        )
        monkeypatch.setattr(first.conn, "execute", execute)
        second.delete_memory("replacement")
        assert first.get_relationship_conflicts_batch(["memory"]) == {"memory": []}


def test_conflict_cache_tracks_staging_publication_and_rollback(tmp_path):
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_observation("older", "", "old", source_memory_id="memory")
        graph.upsert_observation("newer", "", "new", source_memory_id="replacement")
        assert graph.get_relationship_conflicts_batch(["memory"])["memory"] == []
        with graph.write_lock:
            graph.begin()
            graph.add_supersession("older", "newer", 0.9, superseded_at=50)
            assert (
                len(graph.get_relationship_conflicts_batch(["memory"])["memory"]) == 1
            )
            graph.rollback()
        assert graph.get_relationship_conflicts_batch(["memory"])["memory"] == []
        graph.add_supersession("older", "newer", 0.9, superseded_at=50)
        assert (
            len(graph.get_relationship_conflicts_batch(["replacement"])["replacement"])
            == 1
        )


def test_graph_copy_retries_only_explicit_background_fork_collision(
    tmp_path, monkeypatch
):
    from redis.exceptions import ResponseError

    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_entity("one", "original", "Concept")
        copy = graph.graph.copy
        calls = []

        def collide_once(destination):
            calls.append(destination)
            if len(calls) == 1:
                raise ResponseError("GRAPH.COPY failed, could not fork")
            return copy(destination)

        monkeypatch.setattr(graph.graph, "copy", collide_once)
        with graph.write_lock:
            graph.begin()
            assert len(calls) == 2
            graph.upsert_entity("one", "changed", "Concept")
            graph.rollback()
        assert graph.get_entity("one")["name"] == "original"


def test_graph_copy_does_not_retry_ambiguous_failure(tmp_path, monkeypatch):
    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        calls = []

        def lost_response(destination):
            calls.append(destination)
            raise ConnectionError("ambiguous copy response")

        monkeypatch.setattr(graph.graph, "copy", lost_response)
        with graph.write_lock:
            with pytest.raises(ConnectionError):
                graph.begin()
        assert len(calls) == 1
        assert graph._staging is None


def test_graph_copy_retry_is_bounded(tmp_path, monkeypatch):
    from redis.exceptions import ResponseError

    with FalkorDBGraphStore(graph_name_for(tmp_path)) as graph:
        graph.upsert_entity("one", "original", "Concept")
        calls = []

        def blocked(destination):
            calls.append(destination)
            raise ResponseError("GRAPH.COPY failed, could not fork")

        monkeypatch.setattr(graph.graph, "copy", blocked)
        graph.socket_timeout = 0.001
        with graph.write_lock:
            with pytest.raises(ResponseError):
                graph.begin()
        assert graph._staging is None
        assert graph.get_entity("one")["name"] == "original"
        assert len(calls) <= 2
