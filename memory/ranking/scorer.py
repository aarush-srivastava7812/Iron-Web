"""
Hybrid scoring formula and retrieval configuration.
Combines multiple signals into final relevance score.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math
import time


@dataclass
class ScoringWeights:
    """
    Weights for the 8-component hybrid scoring formula.
    
    FinalScore = α·SemanticSimilarity + β·GraphRelevance + γ·Recency
               + δ·Importance + ε·EntityMatch + ζ·RelationshipStrength
               + η·HistoricalRelevance − θ·ContradictionPenalty
               + θ_c·ContrastiveMargin
    """
    # Core signals
    alpha_semantic: float = 1.0        # Vector similarity (cosine)
    beta_graph: float = 0.5            # Graph expansion relevance
    gamma_recency: float = 0.3         # Recency decay
    delta_importance: float = 0.2      # Explicit importance weight
    epsilon_entity: float = 0.4        # Entity match bonus
    zeta_relationship: float = 0.3     # Relationship strength
    eta_historical: float = 0.2        # Historical relevance
    theta_contradiction: float = 0.5   # Contradiction penalty (subtracted)
    theta_contrastive: float = 0.2     # Contrastive margin bonus
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "alpha_semantic": self.alpha_semantic,
            "beta_graph": self.beta_graph,
            "gamma_recency": self.gamma_recency,
            "delta_importance": self.delta_importance,
            "epsilon_entity": self.epsilon_entity,
            "zeta_relationship": self.zeta_relationship,
            "eta_historical": self.eta_historical,
            "theta_contradiction": self.theta_contradiction,
            "theta_contrastive": self.theta_contrastive,
        }
    
    @classmethod
    def uniform(cls) -> "ScoringWeights":
        """Uniform weights (all 1.0) for ablation baseline."""
        return cls(
            alpha_semantic=1.0, beta_graph=1.0, gamma_recency=1.0,
            delta_importance=1.0, epsilon_entity=1.0, zeta_relationship=1.0,
            eta_historical=1.0, theta_contradiction=1.0, theta_contrastive=1.0
        )
    
    @classmethod
    def defaults(cls) -> "ScoringWeights":
        """Default optimized weights."""
        return cls()


@dataclass
class RetrievalConfig:
    """Configuration for hybrid retrieval."""
    
    # Component toggles
    use_vector: bool = True
    use_graph_expansion: bool = True
    use_reranker: bool = True
    use_contrastive: bool = True
    use_temporal_filter: bool = True
    # Reversible latency optimizations.  Both preserve the legacy path when
    # disabled, which makes an A/B rollback a configuration change.
    use_entity_lookup_cache: bool = True
    use_batched_conflict_resolution: bool = True
    
    # Retrieval parameters
    contrastive_ratio: float = 0.1      # % of contrastive candidates
    contrastive_offset: int = 100       # Offset for contrastive candidates
    vector_candidates: int = 100        # Initial vector search width
    graph_hops: int = 2                 # Graph expansion hops
    final_top_k: int = 10               # Final results
    
    # Scoring
    weights: ScoringWeights = field(default_factory=ScoringWeights.defaults)
    
    # Temporal
    default_query_time: Optional[int] = None
    
    def __post_init__(self):
        if self.default_query_time is None:
            self.default_query_time = int(time.time())


class HybridScorer:
    """
    Computes hybrid relevance score combining multiple signals.
    """
    
    def __init__(self, config: RetrievalConfig):
        self.config = config
        self.weights = config.weights
    
    def score(
        self,
        candidate: Dict[str, Any],
        query: str,
        query_entities: List[str],
        query_time: Optional[int] = None,
        graph_context: Optional[Dict] = None,
        contrastive_info: Optional[Dict] = None
    ) -> float:
        """
        Compute final hybrid score for a candidate.
        
        Args:
            candidate: Candidate memory with payload
            query: Original query text
            query_entities: Entities extracted from query
            query_time: Query timestamp
            graph_context: Graph expansion context
            contrastive_info: Contrastive retrieval info
            
        Returns:
            Final score (higher = more relevant)
        """
        if query_time is None:
            query_time = self.config.default_query_time or int(time.time())
        
        payload = candidate.get("payload", {})
        score = 0.0
        
        # 1. Semantic similarity (cosine from vector search)
        semantic_sim = candidate.get("score", 0)  # Vector search score
        if "rerank_score" in candidate:
            # Use reranker score if available (0-1 range)
            semantic_sim = candidate["rerank_score"]
        score += self.weights.alpha_semantic * semantic_sim
        
        # 2. Graph relevance
        graph_rel = candidate.get("graph_relevance", 0)
        score += self.weights.beta_graph * graph_rel
        
        # 3. Recency decay
        timestamp = payload.get("timestamp", query_time)
        age_days = (query_time - timestamp) / 86400
        recency = math.exp(-age_days / 90)  # 90-day half-life
        score += self.weights.gamma_recency * recency
        
        # 4. Explicit importance
        importance = payload.get("importance", 1.0)
        score += self.weights.delta_importance * importance
        
        # 5. Entity match
        entity_ids = payload.get("entity_ids", [])
        entity_match = len(set(query_entities) & set(entity_ids)) / max(len(query_entities), 1)
        score += self.weights.epsilon_entity * entity_match
        
        # 6. Relationship strength
        rel_strength = candidate.get("relationship_strength", 0)
        score += self.weights.zeta_relationship * rel_strength
        
        # 7. Historical relevance
        historical_rel = candidate.get("historical_relevance", 0)
        score += self.weights.eta_historical * historical_rel
        
        # 8. Contradiction penalty (subtracted)
        contradiction_penalty = candidate.get("contradiction_penalty", 0)
        score -= self.weights.theta_contradiction * contradiction_penalty
        
        # 9. Contrastive margin bonus
        contrastive_margin = candidate.get("contrastive_margin", 0)
        score += self.weights.theta_contrastive * contrastive_margin
        
        return score
    
    def score_batch(
        self,
        candidates: List[Dict[str, Any]],
        query: str,
        query_entities: List[str],
        query_time: Optional[int] = None,
        graph_context: Optional[Dict] = None,
        contrastive_info: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Score a batch of candidates."""
        for cand in candidates:
            cand["final_score"] = self.score(
                cand, query, query_entities, query_time, graph_context, contrastive_info
            )
        
        # Sort by final score descending
        candidates.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return candidates


def reciprocal_rank_fusion(
    result_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) for combining multiple ranked lists.
    
    Args:
        result_lists: List of ranked result lists
        k: RRF constant (typically 60)
        top_k: Number of final results
        
    Returns:
        Fused and ranked results
    """
    scores = {}
    
    for results in result_lists:
        for rank, result in enumerate(results):
            mem_id = result.get("memory_id") or result.get("id") or result.get("payload", {}).get("memory_id")
            if not mem_id:
                continue
            
            if mem_id not in scores:
                scores[mem_id] = {"rrf_score": 0.0, "result": result}
            
            scores[mem_id]["rrf_score"] += 1.0 / (k + rank + 1)
    
    # Sort by RRF score
    fused = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    
    # Return top-k with fused scores
    output = []
    for item in fused[:top_k]:
        result = item["result"].copy()
        result["rrf_score"] = item["rrf_score"]
        output.append(result)
    
    return output
