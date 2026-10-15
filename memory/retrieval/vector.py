"""
Vector-only retriever (Baseline A).
Simple semantic similarity search using Qdrant.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import numpy as np
from memory.embeddings.embedder import Embedder
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.vector_store.qdrant_store import QdrantVectorStore


class VectorRetriever:
    """
    Baseline A: Pure vector similarity retrieval.
    No graph, no reranker, no contrastive, no temporal filtering (optional).
    """

    def __init__(
        self,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        use_temporal_filter: bool = False,
        default_top_k: int = 10,
        lifecycle=None,
    ):
        """
        Initialize vector retriever.

        Args:
            embedder: Embedder instance
            vector_store: Qdrant vector store
            use_temporal_filter: Enable temporal filtering (valid_from/valid_until)
            default_top_k: Default number of results
        """
        self.embedder = embedder
        self.vector_store = vector_store
        self.use_temporal_filter = use_temporal_filter
        self.default_top_k = default_top_k
        self.lifecycle = lifecycle

    def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        query_time: Optional[int] = None,
        temporal_mode: str = "auto",
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories using vector similarity.

        Args:
            query: Query text
            k: Number of results (default: default_top_k)
            query_time: Unix timestamp for temporal filtering
            temporal_mode: "now", "historical", "auto"

        Returns:
            List of result dicts with memory_id, score, text, payload
        """
        if k is None:
            k = self.default_top_k

        # Embed query
        query_embedding = self.embedder.embed_single(query)

        # Build temporal filter if enabled
        filter_condition = None
        from memory.vector_store.qdrant_store import create_search_filter
        import time

        query_time = int(time.time()) if query_time is None else query_time
        filter_condition = create_search_filter(
            query_time,
            temporal_mode,
            document_ids,
            include_versioned=self.lifecycle is not None,
        )

        # Search
        results = self.vector_store.search(
            query_embedding=query_embedding, k=k, filter_condition=filter_condition
        )

        # Format results
        formatted = []
        for r in results:
            formatted.append(
                {
                    "memory_id": r["payload"].get("memory_id", r["id"]),
                    "score": r["score"],
                    "text": r["payload"].get("text", ""),
                    "payload": r["payload"],
                    "retrieval_method": "vector",
                }
            )

        if self.lifecycle is not None:
            formatted = self.lifecycle.reconcile(
                formatted,
                query,
                query_time,
                temporal_mode,
                document_ids,
                query_embedding,
            )
            for candidate in formatted:
                if "lifecycle_trace" in candidate:
                    candidate["final_score"] = candidate["score"] + candidate.get(
                        "reliability_boost", 0
                    )
                    candidate["retrieval_trace"] = {
                        "lifecycle": candidate["lifecycle_trace"],
                        "vector_score": candidate["score"],
                    }
            formatted = sorted(
                formatted,
                key=lambda c: (-c.get("final_score", c["score"]), c["memory_id"]),
            )[:k]
        return formatted

    def retrieve_with_embedding(
        self,
        query_embedding: np.ndarray,
        k: Optional[int] = None,
        query_time: Optional[int] = None,
        temporal_mode: str = "auto",
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve using pre-computed embedding."""
        if k is None:
            k = self.default_top_k

        filter_condition = None
        from memory.vector_store.qdrant_store import create_search_filter
        import time

        query_time = int(time.time()) if query_time is None else query_time
        filter_condition = create_search_filter(
            query_time,
            temporal_mode,
            document_ids,
            include_versioned=self.lifecycle is not None,
        )

        results = self.vector_store.search(
            query_embedding=query_embedding, k=k, filter_condition=filter_condition
        )

        formatted = []
        for r in results:
            formatted.append(
                {
                    "memory_id": r["payload"].get("memory_id", r["id"]),
                    "score": r["score"],
                    "text": r["payload"].get("text", ""),
                    "payload": r["payload"],
                    "retrieval_method": "vector",
                }
            )

        if self.lifecycle is not None:
            formatted = self.lifecycle.reconcile(
                formatted, "", query_time, temporal_mode, document_ids, query_embedding
            )
            for candidate in formatted:
                if "lifecycle_trace" in candidate:
                    candidate["final_score"] = candidate["score"] + candidate.get(
                        "reliability_boost", 0
                    )
            formatted = sorted(
                formatted,
                key=lambda c: (-c.get("final_score", c["score"]), c["memory_id"]),
            )[:k]
        return formatted


class BaselineA_Retriever(VectorRetriever):
    """Alias for Baseline A (vector only)."""

    pass
