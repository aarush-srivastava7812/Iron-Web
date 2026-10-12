"""
Ablation study configurations and runner.
"""
from dataclasses import dataclass
from typing import Dict, List, Callable
from memory.ranking.scorer import RetrievalConfig, ScoringWeights


@dataclass
class AblationConfig:
    name: str
    description: str
    config_modifier: Callable[[RetrievalConfig], RetrievalConfig]
    expected_impact: str


def full_config() -> RetrievalConfig:
    return RetrievalConfig(
        use_vector=True,
        use_graph_expansion=True,
        use_reranker=True,
        use_contrastive=True,
        use_temporal_filter=True,
        contrastive_ratio=0.1,
        vector_candidates=100,
        graph_hops=2,
        final_top_k=10,
        weights=ScoringWeights()
    )


ABLATIONS = {
    "full": AblationConfig(
        name="Full System",
        description="All components enabled",
        config_modifier=lambda c: c,
        expected_impact="baseline"
    ),
    
    "no_graph": AblationConfig(
        name="No Graph Expansion",
        description="Disable graph expansion (Iron Web layer)",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_graph_expansion": False}
        ),
        expected_impact="high"
    ),
    
    "no_contrastive": AblationConfig(
        name="No Contrastive Retrieval",
        description="Disable contrastive candidates",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_contrastive": False, "contrastive_ratio": 0.0}
        ),
        expected_impact="medium"
    ),
    
    "no_reranker": AblationConfig(
        name="No Cross-Encoder Reranker",
        description="Disable bge-reranker-base reranking",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_reranker": False}
        ),
        expected_impact="high"
    ),
    
    "no_temporal": AblationConfig(
        name="No Temporal Filtering",
        description="Disable valid_from/valid_until filtering",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_temporal_filter": False}
        ),
        expected_impact="high"
    ),
    
    "no_vector": AblationConfig(
        name="No Vector Search (Graph Only)",
        description="Graph-only retrieval (experimental)",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "use_vector": False, "use_graph_expansion": True}
        ),
        expected_impact="very_high"
    ),
    
    "no_weights": AblationConfig(
        name="Uniform Weights (No Learned Scoring)",
        description="All scoring weights = 1.0 (uniform)",
        config_modifier=lambda c: RetrievalConfig(
            **{**c.__dict__, "weights": ScoringWeights(
                alpha_semantic=1.0, beta_graph=1.0, gamma_recency=1.0,
                delta_importance=1.0, epsilon_entity=1.0, zeta_relationship=1.0,
                eta_historical=1.0, theta_contradiction=1.0
            )}
        ),
        expected_impact="medium"
    ),
    
    "vector_only": AblationConfig(
        name="Vector Only (Baseline A)",
        description="Pure vector similarity, no graph, no rerank",
        config_modifier=lambda c: RetrievalConfig(
            use_vector=True,
            use_graph_expansion=False,
            use_reranker=False,
            use_contrastive=False,
            use_temporal_filter=False,
            contrastive_ratio=0.0,
            vector_candidates=100,
            graph_hops=2,
            final_top_k=10,
            weights=ScoringWeights()
        ),
        expected_impact="baseline_a"
    ),
}


def get_ablation_configs() -> Dict[str, AblationConfig]:
    return ABLATIONS


def create_retriever_for_ablation(ablation_name: str, embedder, vector_store, graph_store, reranker):
    """Factory to create retriever with ablation config."""
    from memory.retrieval.hybrid import HybridRetriever
    
    config = ABLATIONS[ablation_name].config_modifier(full_config())
    return HybridRetriever(embedder, vector_store, graph_store, reranker, config)