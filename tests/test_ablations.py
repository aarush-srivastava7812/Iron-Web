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
import pytest
import time

from memory.engine import MemoryEngine


def test_baseline_a_no_memory(tmp_path):
    """Baseline A: no_memory returns an empty list immediately without touching stores."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("Python is a high-level language", entity_ids=["python"])
        results = engine.search("What is Python?", retrieval_mode="no_memory")
        assert results == []


def test_baseline_b_vector_only(tmp_path):
    """Baseline B: vector returns results retrieved purely via vector search."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("FastAPI is an async Python web framework", entity_ids=["fastapi"])
        results = engine.search("Which web framework is async?", retrieval_mode="vector")
        assert len(results) >= 1
        assert results[0].retrieval_method == "vector"
        assert "FastAPI" in results[0].content


def test_baseline_c_graph_only(tmp_path):
    """Baseline C: graph-only retrieves candidates strictly via graph store without vector search."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("Neo4j and Kùzu are graph database management systems", entity_ids=["kuzu", "graph_db"])
        results = engine.search("Tell me about Kùzu graph database", retrieval_mode="graph")
        assert len(results) >= 1
        assert "Kùzu" in results[0].content


def test_variant_d_hybrid_no_rerank(tmp_path):
    """Variant D: hybrid_no_rerank combines vector and graph but disables cross-encoder reranker."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("PyTorch supports GPU acceleration on CUDA devices", entity_ids=["pytorch", "cuda"])
        results = engine.search("Does PyTorch use CUDA?", retrieval_mode="hybrid_no_rerank")
        assert len(results) >= 1
        assert "PyTorch" in results[0].content


def test_variant_e_full_hybrid(tmp_path):
    """Variant E: full hybrid proposed architecture incorporates all components."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("TensorFlow and PyTorch are popular deep learning frameworks", entity_ids=["deep_learning"])
        results = engine.search("Deep learning frameworks", retrieval_mode="hybrid")
        assert len(results) >= 1
        assert "retrieval_trace" in dir(results[0]) or hasattr(results[0], "retrieval_trace")


def test_component_ablations(tmp_path):
    """Verifies that hybrid_no_graph and hybrid_no_temporal execute cleanly."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("Bitemporal modeling records assertion time and event time", entity_ids=["bitemporal"])
        res_no_graph = engine.search("bitemporal modeling", retrieval_mode="hybrid_no_graph")
        assert len(res_no_graph) >= 1
        
        res_no_temp = engine.search("bitemporal modeling", retrieval_mode="hybrid_no_temporal")
        assert len(res_no_temp) >= 1


def test_competitor_retrieval_modes(tmp_path):
    """Verifies that mem0, zep, and mempalace retrieval modes execute and return results."""
    q_dir = str(tmp_path / "qdrant_db")
    k_file = str(tmp_path / "kuzu.db")
    
    with MemoryEngine(qdrant_path=q_dir, kuzu_path=k_file, use_gpu=False) as engine:
        engine.add("LangGraph is a library for building stateful multi-actor applications with LLMs", entity_ids=["langgraph", "llm"])
        engine.add("Mem0 provides personalized memory for AI applications", entity_ids=["mem0"])
        
        # 1. Mem0 Mode
        res_mem0 = engine.search("Tell me about Mem0 memory", retrieval_mode="mem0")
        assert len(res_mem0) >= 1
        assert res_mem0[0].retrieval_method == "mem0"
        
        # 2. Zep Mode
        res_zep = engine.search("building stateful multi-actor applications with LangGraph", retrieval_mode="zep")
        assert len(res_zep) >= 1
        assert res_zep[0].retrieval_method == "zep"
        
        # 3. MemPalace Mode
        res_palace = engine.search("stateful applications", retrieval_mode="mempalace")
        assert len(res_palace) >= 1
        assert res_palace[0].retrieval_method == "mempalace"

