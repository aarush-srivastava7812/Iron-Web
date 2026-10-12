"""
Baseline runners for evaluation.
Unified interface for running all baselines on test scenarios.
"""
from typing import List, Dict, Any
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph import KuzuGraphStore, GraphStore
from memory.ranking.reranker import Reranker
from memory.retrieval.vector import VectorRetriever, BaselineA_Retriever
from memory.retrieval.hybrid import (
    BaselineB_Retriever, BaselineC_Retriever, BaselineD_Retriever, FullRetriever
)
from memory.ranking.scorer import RetrievalConfig


class BaselineRunner:
    """Run a single baseline on all scenarios."""
    
    def __init__(self, name: str, retriever_factory):
        self.name = name
        self.retriever_factory = retriever_factory
    
    def run(self, scenario, top_k: int = 10) -> Dict[str, Any]:
        """Run baseline on one scenario."""
        retriever = self.retriever_factory()
        results = retriever.retrieve(scenario.query, k=top_k)
        
        return {
            "scenario_id": scenario.id,
            "query": scenario.query,
            "baseline": self.name,
            "retrieved_ids": [
                r.get("payload", {}).get("memory_id") or r.get("memory_id") or r.get("id") 
                for r in results
            ],
            "retrieved_scores": [
                r.get("final_score") or r.get("hybrid_score") or r.get("rerank_score") or r.get("score", 0) 
                for r in results
            ],
            "raw_results": results
        }


def create_baseline_runners(embedder, vector_store, graph_store: GraphStore, reranker):
    """Factory functions for each baseline."""
    
    config = RetrievalConfig(final_top_k=10)
    
    def make_baseline_a():
        return BaselineA_Retriever(embedder, vector_store)
    
    def make_baseline_b():
        return BaselineB_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    def make_baseline_c():
        return BaselineC_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    def make_baseline_d():
        return BaselineD_Retriever(embedder, vector_store, graph_store, reranker, config)
    
    def make_full():
        return FullRetriever(embedder, vector_store, graph_store, reranker, config)
    
    return {
        "baseline_a": BaselineRunner("Baseline A (Vector)", make_baseline_a),
        "baseline_b": BaselineRunner("Baseline B (Vector+Rerank)", make_baseline_b),
        "baseline_c": BaselineRunner("Baseline C (Vector+Graph+Rerank)", make_baseline_c),
        "baseline_d": BaselineRunner("Baseline D (Vector+Contrastive+Rerank)", make_baseline_d),
        "full": BaselineRunner("Full (Vector+Graph+Contrastive+Rerank)", make_full),
    }


# Dataset loading functions for compatibility
def load_dmr_dataset(datasets_dir: str = "./data/benchmarks") -> List[Dict[str, Any]]:
    """Load DMR dataset from file."""
    from pathlib import Path
    import json
    
    path = Path(datasets_dir) / "dmr" / "dmr.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def load_locomo_dataset(datasets_dir: str = "./data/benchmarks") -> List[Dict[str, Any]]:
    """Load LoCoMo dataset from file."""
    from pathlib import Path
    import json
    
    path = Path(datasets_dir) / "locomo" / "locomo.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def load_longmemeval_dataset(datasets_dir: str = "./data/benchmarks") -> List[Dict[str, Any]]:
    """Load LongMemEval dataset from file."""
    from pathlib import Path
    import json
    
    path = Path(datasets_dir) / "longmemeval" / "longmemeval.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []