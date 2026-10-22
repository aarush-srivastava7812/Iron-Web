"""
Tests for Phase 7: Baselines and Ablations.
Verifies that MemoryEngine and HybridRetriever cleanly isolate each component:
- Baseline A: no_memory (empty context)
- Baseline B: vector-only
- Baseline C: graph-only
- Variant D: hybrid_no_rerank (vector + graph without reranker)
- Variant E: full hybrid (proposed architecture)
- Component ablations: hybrid_no_temporal, hybrid_no_graph
"""

from tests.fixtures.graph import graph_name_for

import pytest

# Retained pre-migration engine contracts; native application checks live in main.py.
from memory.engine import LegacyMemoryEngine as MemoryEngine


def test_baseline_a_no_memory(tmp_path):
    """Baseline A: no_memory returns an empty list immediately without touching stores."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        engine.add("Python is a high-level language", entity_ids=["python"])
        results = engine.search("What is Python?", retrieval_mode="no_memory")
        assert results == []


def test_baseline_b_vector_only(tmp_path):
    """Baseline B: vector returns results retrieved purely via vector search."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        engine.add("FastAPI is an async Python web framework", entity_ids=["fastapi"])
        results = engine.search(
            "Which web framework is async?", retrieval_mode="vector"
        )
        assert len(results) >= 1
        assert results[0].retrieval_method == "vector"
        assert "FastAPI" in results[0].content


def test_baseline_c_graph_only(tmp_path):
    """Baseline C: graph-only retrieves candidates strictly via graph store without vector search."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        engine.add(
            "Neo4j and FalkorDB are graph database management systems",
            entity_ids=["falkordb", "graph_db"],
        )
        results = engine.search(
            "Tell me about FalkorDB graph database", retrieval_mode="graph"
        )
        assert len(results) >= 1
        assert "FalkorDB" in results[0].content


def test_variant_d_hybrid_no_rerank(tmp_path):
    """Variant D: hybrid_no_rerank combines vector and graph but disables cross-encoder reranker."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        engine.add(
            "PyTorch supports GPU acceleration on CUDA devices",
            entity_ids=["pytorch", "cuda"],
        )
        results = engine.search(
            "Does PyTorch use CUDA?", retrieval_mode="hybrid_no_rerank"
        )
        assert len(results) >= 1
        assert "PyTorch" in results[0].content


def test_variant_e_full_hybrid(tmp_path):
    """Variant E: full hybrid proposed architecture incorporates all components."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        engine.add(
            "TensorFlow and PyTorch are popular deep learning frameworks",
            entity_ids=["deep_learning"],
        )
        results = engine.search("Deep learning frameworks", retrieval_mode="hybrid")
        assert len(results) >= 1
        assert "retrieval_trace" in dir(results[0]) or hasattr(
            results[0], "retrieval_trace"
        )


def test_component_ablations(tmp_path):
    """Verifies that hybrid_no_graph and hybrid_no_temporal execute cleanly."""
    q_dir = str(tmp_path / "qdrant_db")
    graph_identity = str(tmp_path / "graph")

    with MemoryEngine(
        qdrant_path=q_dir, graph_name=graph_name_for(graph_identity), use_gpu=False
    ) as engine:
        engine.add(
            "Bitemporal modeling records assertion time and event time",
            entity_ids=["bitemporal"],
        )
        res_no_graph = engine.search(
            "bitemporal modeling", retrieval_mode="hybrid_no_graph"
        )
        assert len(res_no_graph) >= 1

        res_no_temp = engine.search(
            "bitemporal modeling", retrieval_mode="hybrid_no_temporal"
        )
        assert len(res_no_temp) >= 1


def test_third_party_brand_names_are_not_application_modes(tmp_path):
    with MemoryEngine(
        config={},
        qdrant_path=str(tmp_path / "vectors"),
        graph_name=graph_name_for(str(tmp_path / "graph.db")),
    ) as engine:
        for mode in ("mem0", "zep", "mempalace"):
            with pytest.raises(ValueError, match="Unknown retrieval mode"):
                engine.search("fact", retrieval_mode=mode)
