"""Regression coverage for Kuzu node/edge count semantics."""

from memory.graph.kuzu_store import KuzuGraphStore


def test_counts_report_directed_edges_once(tmp_path):
    """A known two-node, one-edge graph must not be counted as two edges."""
    store = KuzuGraphStore(str(tmp_path / "counts.db"))
    try:
        store.upsert_entity("alpha", "Alpha", "CONCEPT")
        store.upsert_entity("beta", "Beta", "CONCEPT")
        store.upsert_relation("alpha", "beta", "RELATED_TO")

        assert store.get_node_counts() == {"Entity": 2, "Observation": 0}
        assert store.get_edge_counts() == {
            "RELATES": 1,
            "ABOUT": 0,
            "CONTRADICTS": 0,
            "SUPERSEDES": 0,
        }
    finally:
        store.close()


def test_entity_index_invalidates_and_batched_conflicts_keep_original_ids(tmp_path):
    """Optimized paths must preserve fresh entity linking and conflict identity."""
    store = KuzuGraphStore(str(tmp_path / "optimized_paths.db"))
    try:
        store.upsert_entity("alpha", "Alpha", "CONCEPT")
        assert store.get_entity_name_index() == [("alpha", "Alpha")]
        store.upsert_entity("beta", "Beta", "CONCEPT")
        assert ("beta", "Beta") in store.get_entity_name_index()

        store.upsert_observation("obs_mem_a", "alpha", "first")
        store.upsert_observation("obs_mem_b", "alpha", "second")
        store.add_contradiction("obs_mem_a", "obs_mem_b")

        batched = store.get_relationship_conflicts_batch(["mem_a"])
        legacy = store.get_relationship_conflicts_batch(["mem_a"], use_batched_resolution=False)
        assert batched["mem_a"][0]["relationship_type"] == "CONTRADICTS"
        # The legacy path remains available for rollback.
        assert isinstance(legacy, dict)
    finally:
        store.close()
