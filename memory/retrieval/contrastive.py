"""
Contrastive retrieval: adds hard negative candidates for discriminative reranking.
Uses offset-based sampling from vector search results.
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import time

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore, create_temporal_filter
from memory.ranking.scorer import RetrievalConfig


class ContrastiveRetriever:
    """
    Contrastive retrieval for discriminative reranking.
    
    Strategy:
    1. Get top-K positive candidates (standard vector search)
    2. Get contrastive candidates from offset (e.g., 100-200) as hard negatives
    3. Combine for cross-encoder reranking which learns to discriminate
    """
    
    def __init__(
        self,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        config: RetrievalConfig
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.config = config
        self.contrastive_ratio = config.contrastive_ratio
        self.contrastive_offset = config.contrastive_offset
        self.vector_candidates = config.vector_candidates
    
    def retrieve_contrastive(
        self,
        query: str,
        query_time: Optional[int] = None,
        temporal_mode: str = "auto"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retrieve both positive and contrastive candidates.
        
        Returns:
            (contrastive_candidates, contrastive_info)
        """
        if query_time is None:
            query_time = self.config.default_query_time or int(time.time())
        
        if self.contrastive_ratio <= 0:
            return [], {"ratio": 0, "positive_count": 0, "contrastive_count": 0}
        
        # Build temporal filter
        filter_condition = None
        if self.config.use_temporal_filter:
            filter_condition = create_temporal_filter(query_time, temporal_mode)
        
        query_embedding = self.embedder.embed_single(query)
        
        # Calculate counts
        positive_k = self.vector_candidates
        contrastive_k = int(positive_k * self.contrastive_ratio)
        
        # Get positive candidates (top-K)
        positive_results = self.vector_store.search(
            query_embedding=query_embedding,
            k=positive_k,
            filter_condition=filter_condition
        )
        
        # Get contrastive candidates (offset range)
        # Search with larger limit, then slice
        total_k = positive_k + self.contrastive_offset + contrastive_k
        all_results = self.vector_store.search(
            query_embedding=query_embedding,
            k=total_k,
            filter_condition=filter_condition
        )
        
        # Slice contrastive from offset
        contrastive_results = all_results[
            self.contrastive_offset : self.contrastive_offset + contrastive_k
        ]
        
        # Format contrastive candidates
        formatted_contrastive = []
        for i, r in enumerate(contrastive_results):
            formatted_contrastive.append({
                "memory_id": r["payload"].get("memory_id", r["id"]),
                "score": r["score"],
                "text": r["payload"].get("text", ""),
                "payload": r["payload"],
                "retrieval_method": "contrastive",
                "is_contrastive": True,
                "contrastive_rank": self.contrastive_offset + i + 1
            })
        
        contrastive_info = {
            "ratio": self.contrastive_ratio,
            "positive_count": len(positive_results),
            "contrastive_count": len(contrastive_results),
            "offset": self.contrastive_offset
        }
        
        return formatted_contrastive, contrastive_info
    
    def compute_contrastive_margin(
        self,
        query: str,
        positive_candidates: List[Dict],
        contrastive_candidates: List[Dict]
    ) -> Dict[str, float]:
        """
        Compute contrastive margin scores for positive candidates.
        
        Margin = min(similarity_to_positive) - max(similarity_to_contrastive)
        Higher margin = more discriminative.
        """
        if not positive_candidates or not contrastive_candidates:
            return {}
        
        # Embed all texts
        pos_texts = [c.get("text", "") for c in positive_candidates]
        cont_texts = [c.get("text", "") for c in contrastive_candidates]
        
        pos_embeddings = self.embedder.embed(pos_texts)
        cont_embeddings = self.embedder.embed(cont_texts)
        query_embedding = self.embedder.embed_single(query)
        
        margins = {}
        for i, pos_emb in enumerate(pos_embeddings):
            # Similarity to query
            sim_to_query = np.dot(pos_emb, query_embedding) / (
                np.linalg.norm(pos_emb) * np.linalg.norm(query_embedding) + 1e-8
            )
            
            # Max similarity to contrastive
            max_cont_sim = 0
            for cont_emb in cont_embeddings:
                sim = np.dot(pos_emb, cont_emb) / (
                    np.linalg.norm(pos_emb) * np.linalg.norm(cont_emb) + 1e-8
                )
                max_cont_sim = max(max_cont_sim, sim)
            
            margin = sim_to_query - max_cont_sim
            mem_id = positive_candidates[i].get("memory_id")
            margins[mem_id] = float(margin)
        
        return margins

    def retrieve(
        self,
        query: str,
        k: int = 10,
        query_time: Optional[int] = None,
        temporal_mode: str = "auto"
    ) -> List[Dict[str, Any]]:
        """
        Full retrieval with contrastive candidates for evaluation.
        Returns top-k combined positive + contrastive candidates after reranking.
        """
        import time
        if query_time is None:
            query_time = self.config.default_query_time or int(time.time())
        
        # Get positive candidates
        filter_condition = None
        if self.config.use_temporal_filter:
            filter_condition = create_temporal_filter(query_time, temporal_mode)
        
        query_embedding = self.embedder.embed_single(query)
        positive_results = self.vector_store.search(
            query_embedding=query_embedding,
            k=self.vector_candidates,
            filter_condition=filter_condition
        )
        
        # Format positive
        positive = []
        for r in positive_results:
            positive.append({
                "memory_id": r["payload"].get("memory_id", r["id"]),
                "score": r["score"],
                "text": r["payload"].get("text", ""),
                "payload": r["payload"],
                "retrieval_method": "vector"
            })
        
        # Get contrastive candidates
        contrastive, _ = self.retrieve_contrastive(query, query_time, temporal_mode)
        
        # Combine
        combined = positive + contrastive
        
        # Rerank if configured
        if self.config.use_reranker:
            from memory.ranking.reranker import get_reranker
            reranker = get_reranker()
            combined = reranker.rerank(query, combined, top_k=min(len(combined), 50))
        
        return combined[:k]