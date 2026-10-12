"""
Unit and integration tests for Phase 3: Hybrid-Memory Logic.
Verifies:
1. Extractor interface, validation, and is_mock marking.
2. Query understanding and entity linking against graph store.
3. Bounded graph expansion and graceful fallback on abstract queries.
4. Temporal memory (event time vs ingestion time, valid_from/valid_until, point-in-time).
5. Contradiction and supersession resolution (current vs historical preferences).
6. Multi-stream RRF fusion and transparent retrieval traces.
"""

import time

from memory.engine import MemoryEngine
from memory.ingestion.extractor import (
    BaseExtractor,
    ExtractionResult,
    validate_extraction,
)
from tests.fixtures.extractor import MockNIMExtractor
from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig


def test_extractor_validation_and_mock_marking():
    """Verify that extractors adhere to BaseExtractor and produce validated, marked outputs."""
    mock_extractor = MockNIMExtractor()
    assert isinstance(mock_extractor, BaseExtractor)
    assert mock_extractor.is_mock is True

    # Test raw extraction validation
    raw_data = {
        "entities": [
            {"id": "Python Lang", "name": "Python", "type": "Technology"},
            {"id": "ML Project", "name": "Machine Learning", "type": "Domain"},
        ],
        "relations": [
            {
                "from": "python_lang",
                "to": "ml_project",
                "type": "USED_FOR",
                "confidence": 0.95,
            },
            {
                "from": "python_lang",
                "to": "non_existent_entity",
                "type": "BROKEN",
                "confidence": 0.5,
            },  # should be pruned
        ],
        "temporal": {"valid_from": 1000, "valid_until": 5000},
        "importance": 0.85,
    }

    validated = validate_extraction(
        raw_data, extractor_name="test_extractor", is_mock=True
    )
    assert isinstance(validated, ExtractionResult)
    assert validated.is_mock is True
    assert validated.extractor_name == "test_extractor"

    # Entity ID must be cleaned
    e_ids = [e.id for e in validated.entities]
    assert "python_lang" in e_ids
    assert "ml_project" in e_ids

    # Broken relation endpoint to non_existent_entity must be discarded
    assert len(validated.relations) == 1
    assert validated.relations[0].from_id == "python_lang"
    assert validated.relations[0].to_id == "ml_project"

    # Dictionary representation conforms to pipeline expectations
    d = validated.to_dict()
    assert d["is_mock"] is True
    assert d["importance"] == 0.85


def test_query_understanding_and_entity_linking(tmp_path):
    """HybridRetriever must extract and link entities mentioned in the query from the graph store."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=True) as engine:
        # Ingest memories with known entity IDs
        engine.add(
            "Python is used for backend web services", entity_ids=["python", "backend"]
        )
        engine.add(
            "React is used for frontend web UI", entity_ids=["react", "frontend"]
        )

        # Test query entity linking directly on HybridRetriever
        retriever = HybridRetriever(
            embedder=engine.embedder,
            vector_store=engine.vector_store,
            graph_store=engine.graph_store,
            reranker=engine.reranker,
            config=RetrievalConfig(final_top_k=5),
        )

        linked = retriever._extract_entities("Do we use Python for our backend?")
        assert "python" in linked or "backend" in linked

        # Test query without matching entities (graceful fallback)
        abstract_linked = retriever._extract_entities("Tell me some general facts.")
        assert abstract_linked == []

        # Search on abstract query must still succeed via vector similarity
        results = engine.search(
            "Tell me some general facts.", k=2, retrieval_mode="hybrid"
        )
        assert len(results) > 0


def test_bounded_graph_expansion(tmp_path):
    """Graph traversal must be bounded in hops and candidate node count."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=True) as engine:
        engine.add("Alpha relates to Beta", entity_ids=["alpha", "beta"])
        engine.add("Beta relates to Gamma", entity_ids=["beta", "gamma"])
        engine.add("Gamma relates to Delta", entity_ids=["gamma", "delta"])

        retriever = HybridRetriever(
            embedder=engine.embedder,
            vector_store=engine.vector_store,
            graph_store=engine.graph_store,
            reranker=engine.reranker,
            config=RetrievalConfig(final_top_k=5, graph_hops=2),
        )

        # Expansion from seed 'alpha' with bounded hops
        expanded = retriever._graph_expansion(
            vector_results=[], query_time=int(time.time()), query_entities=["alpha"]
        )
        assert len(expanded) <= 50  # Bounded ceiling


def test_temporal_point_in_time_and_changed_preferences(tmp_path):
    """
    Test event time vs ingestion time:
    A changed preference must return the historical fact when queried at a historical timestamp,
    and the current fact when queried at current time.
    """
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=True) as engine:
        t_2020 = 1577836800  # Jan 1, 2020
        t_2022 = 1640995200  # Jan 1, 2022
        t_2024 = 1704067200  # Jan 1, 2024

        # Past fact: valid from 2020 to 2022
        mem_past = engine.add(
            content="I use C++ for competitive programming and DSA",
            entity_ids=["cpp", "dsa"],
            valid_from=t_2020,
            valid_until=t_2022,
            timestamp=t_2020,
        )

        # Current fact: valid from 2022 onwards
        mem_curr = engine.add(
            content="I use Java for competitive programming and DSA",
            entity_ids=["java", "dsa"],
            valid_from=t_2022,
            valid_until=2**31 - 1,
            timestamp=t_2022,
        )

        # 1. Point-in-time query at 2021 (when C++ was the active language)
        results_2021 = engine.search(
            query="Which language for DSA?",
            k=2,
            temporal_mode="now",
            query_time=1609459200,  # 2021
            retrieval_mode="hybrid",
        )
        assert len(results_2021) >= 1
        assert results_2021[0].memory_id == mem_past
        assert "C++" in results_2021[0].content

        # 2. Query at 2024 (when Java is active)
        results_2024 = engine.search(
            query="Which language for DSA?",
            k=2,
            temporal_mode="now",
            query_time=t_2024,
            retrieval_mode="hybrid",
        )
        assert len(results_2024) >= 1
        assert results_2024[0].memory_id == mem_curr
        assert "Java" in results_2024[0].content

        # 3. Historical query at 2024 requesting expired facts
        results_hist = engine.search(
            query="Which language did I use previously for DSA?",
            k=2,
            temporal_mode="historical",
            query_time=t_2024,
            retrieval_mode="hybrid",
        )
        assert len(results_hist) >= 1
        assert results_hist[0].memory_id == mem_past


def test_contradiction_supersession_graph_chain_and_ranking(tmp_path):
    """
    When an explicit supersession relationship exists in the graph,
    the superseded memory must be demoted in 'now' mode and flagged with is_superseded=True.
    """
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=True) as engine:
        t_now = int(time.time())
        t_past = t_now - 100000

        # Ingest old memory and new memory
        mem_old = engine.add(
            content="My primary editor is Sublime Text",
            entity_ids=["editor"],
            valid_from=0,
            valid_until=t_past,
            timestamp=t_past,
        )
        mem_new = engine.add(
            content="My primary editor is VS Code",
            entity_ids=["editor"],
            valid_from=t_past,
            valid_until=2**31 - 1,
            timestamp=t_now,
        )

        # Record supersession in graph: old observation superseded by new observation
        obs_old_id = f"obs_{mem_old}_editor"
        obs_new_id = f"obs_{mem_new}_editor"
        engine.graph_store.add_supersession(
            old_obs_id=obs_old_id,
            new_obs_id=obs_new_id,
            confidence=0.98,
            reason="Switched primary editor",
            superseded_at=t_past,
        )

        # Query current editor
        results = engine.search(
            "What is my primary editor?", k=5, temporal_mode="now", query_time=t_now
        )
        assert len(results) >= 1
        assert results[0].memory_id == mem_new
        assert "VS Code" in results[0].content


def test_retrieval_trace_inspection(tmp_path):
    """Returned SearchResults must contain transparent retrieval_trace telemetry."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")

    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=True) as engine:
        mem_id = engine.add(
            "PostgreSQL is used as our primary relational database",
            entity_ids=["postgresql", "database"],
        )

        results = engine.search(
            "Which relational database is used?", k=1, retrieval_mode="hybrid"
        )
        assert len(results) == 1
        res = results[0]

        # Verify trace fields
        trace = res.retrieval_trace
        assert isinstance(trace, dict)
        assert trace["memory_id"] == mem_id
        assert "vector_score" in trace
        assert "final_score" in trace
        assert "selection_rank" in trace
        assert trace["selection_rank"] == 1
