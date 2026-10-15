"""Scoring signals that the normal retrieval pipeline actually supplies."""

from dataclasses import dataclass, field, asdict
import math
import time


@dataclass
class ScoringWeights:
    alpha_semantic: float = 1.0
    beta_graph: float = 0.5
    gamma_recency: float = 0.3
    delta_importance: float = 0.2
    epsilon_entity: float = 0.4
    eta_historical: float = 0.2
    theta_contradiction: float = 0.5

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in asdict(self).values()):
            raise ValueError("Scoring weights must be finite and nonnegative.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def uniform(cls):
        return cls(**{key: 1.0 for key in cls.__dataclass_fields__})

    @classmethod
    def defaults(cls):
        return cls()


@dataclass
class RetrievalConfig:
    use_vector: bool = True
    use_graph_expansion: bool = True
    use_reranker: bool = False
    use_temporal_filter: bool = True
    use_entity_lookup_cache: bool = True
    vector_candidates: int = 100
    graph_hops: int = 2
    graph_max_nodes: int = 50
    final_top_k: int = 10
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    default_query_time: int | None = None

    def __post_init__(self):
        if not 1 <= self.final_top_k <= 100 or not 1 <= self.vector_candidates <= 1000:
            raise ValueError("Invalid retrieval candidate or result limit.")
        if self.graph_hops not in (1, 2) or not 1 <= self.graph_max_nodes <= 100:
            raise ValueError("Invalid graph traversal limits.")


class HybridScorer:
    def __init__(self, config):
        self.config, self.weights = config, config.weights

    def score(
        self,
        candidate,
        query,
        query_entities,
        query_time=None,
        graph_context=None,
        contrastive_info=None,
    ):
        now = int(time.time()) if query_time is None else query_time
        payload, w = candidate.get("payload", {}), self.weights
        age = max(0, now - payload.get("timestamp", now)) / 86400
        overlap = len(set(query_entities) & set(payload.get("entity_ids", []))) / max(
            1, len(query_entities)
        )
        return (
            w.alpha_semantic * candidate.get("rerank_score", candidate.get("score", 0))
            + w.beta_graph * candidate.get("graph_relevance", 0)
            + w.gamma_recency * 2 ** (-age / 90)
            + w.delta_importance * payload.get("importance", 1)
            + w.epsilon_entity * overlap
            + w.eta_historical * candidate.get("historical_relevance", 0)
            - w.theta_contradiction * candidate.get("contradiction_penalty", 0)
            + candidate.get("reliability_boost", 0)
        )

    def score_batch(
        self,
        candidates,
        query,
        query_entities,
        query_time=None,
        graph_context=None,
        contrastive_info=None,
    ):
        for candidate in candidates:
            candidate["final_score"] = self.score(
                candidate, query, query_entities, query_time
            )
        return sorted(candidates, key=lambda c: (-c["final_score"], c["memory_id"]))
