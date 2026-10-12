"""
Qdrant vector store for semantic memory.
Local embedded mode (no Docker/server required).
"""
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition,
    ScalarQuantization, ScalarQuantizationConfig, ScalarType
)
from memory.embeddings.embedder import Embedder

# Namespace for generating deterministic UUIDs from memory IDs
MEMORY_NAMESPACE = uuid.UUID('12345678-1234-5678-1234-567812345678')
RESERVED_FIELDS = {"memory_id", "text", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"}


def validate_metadata(metadata):
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("Metadata must be a dictionary.")
    conflicts = RESERVED_FIELDS.intersection(metadata or {})
    if conflicts:
        raise ValueError(f"Metadata cannot overwrite record fields: {sorted(conflicts)}")


class QdrantVectorStore:
    """
    Qdrant vector store for semantic memory retrieval.
    Uses local embedded mode (file-based, no server).
    """
    
    def __init__(
        self,
        path: str = "./data/qdrant",
        collection_name: str = "memory_semantic",
        embedder: Optional[Embedder] = None,
        dimension: int = 384,
        distance: Distance = Distance.COSINE,
        quantization: bool = True,  # Scalar INT8 quantization
        hnsw_m: int = 16,
        hnsw_ef_construct: int = 100,
    ):
        """
        Initialize Qdrant vector store.
        
        Args:
            path: Local storage path for Qdrant data
            collection_name: Collection name
            embedder: Embedder instance (creates default if None)
            dimension: Vector dimension
            distance: Distance metric
            quantization: Enable scalar INT8 quantization
            hnsw_m: HNSW M parameter (connections per node)
            hnsw_ef_construct: HNSW ef_construct parameter
        """
        self.path = path
        self.collection_name = collection_name
        self.dimension = dimension
        self.distance = distance
        
        # Create directory if needed
        os.makedirs(path, exist_ok=True)
        
        # Initialize Qdrant client (embedded mode)
        self.client = QdrantClient(path=path)
        self._embedder = embedder
        
        # Create collection if not exists
        self._create_collection(quantization, hnsw_m, hnsw_ef_construct)
        
    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder
    
    def _create_collection(self, quantization: bool, hnsw_m: int, hnsw_ef_construct: int):
        """Create Qdrant collection with optimized settings."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            # Quantization config for memory efficiency
            quantization_config = None
            if quantization:
                quantization_config = ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True
                    )
                )
            
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=self.distance,
                    hnsw_config={
                        "m": hnsw_m,
                        "ef_construct": hnsw_ef_construct,
                        "full_scan_threshold": 10000
                    }
                ),
                quantization_config=quantization_config,
            )
            print(f"Created collection: {self.collection_name}")
        else:
            print(f"Collection exists: {self.collection_name}")
    
    def _memory_id_to_uuid(self, memory_id: str) -> str:
        """Convert a memory ID to a deterministic UUID for Qdrant."""
        return str(uuid.uuid5(MEMORY_NAMESPACE, memory_id))
    
    def upsert_memory(
        self,
        memory_id: str,
        text: str,
        embedding: Optional[np.ndarray] = None,
        entity_ids: Optional[List[str]] = None,
        valid_from: int = 0,
        valid_until: int = 2**31 - 1,  # Max int32 = "forever"
        importance: float = 1.0,
        memory_type: str = "semantic",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None
    ) -> str:
        """
        Upsert a memory into the vector store.
        
        Args:
            memory_id: Unique memory identifier
            text: Memory text content
            embedding: Pre-computed embedding (computed if None)
            entity_ids: List of related entity IDs
            valid_from: Unix timestamp when memory becomes valid
            valid_until: Unix timestamp when memory expires
            importance: Importance weight (0-1)
            memory_type: Type of memory (semantic, episodic, procedural)
            metadata: Additional metadata
            timestamp: Creation timestamp
            
        Returns:
            memory_id
        """
        import time
        validate_metadata(metadata)
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("Memory ID must be a nonempty string.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Memory content must be a nonempty string.")
        if valid_from > valid_until:
            raise ValueError("Validity start cannot exceed expiration.")
        if not np.isfinite(importance) or not 0 <= importance <= 1:
            raise ValueError("Importance must be between zero and one.")
        if timestamp is None:
            timestamp = int(time.time())
        
        if embedding is None:
            embedding = self.embedder.embed_single(text)
        embedding = np.asarray(embedding, dtype=np.float32)
        if embedding.shape != (self.dimension,) or not np.isfinite(embedding).all():
            raise ValueError(f"Embedding must contain {self.dimension} finite numbers.")
        
        payload = {
            "memory_id": memory_id,
            "text": text,
            "entity_ids": entity_ids or [],
            "valid_from": valid_from,
            "valid_until": valid_until,
            "importance": importance,
            "memory_type": memory_type,
            "timestamp": timestamp,
        }
        if metadata:
            payload.update(metadata)
        
        point = PointStruct(
            id=self._memory_id_to_uuid(memory_id),
            vector=embedding.tolist(),
            payload=payload
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return memory_id
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter_condition: Optional[Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar memories.
        
        Args:
            query_embedding: Query vector
            k: Number of results
            filter_condition: Qdrant filter for metadata filtering
            score_threshold: Minimum similarity score
            
        Returns:
            List of result dicts with payload and score
        """
        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=k,
            query_filter=filter_condition,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False
        )
        
        results = []
        for hit in search_result.points:
            result = {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload
            }
            results.append(result)
        
        return results
    
    def search_with_text(
        self,
        query_text: str,
        k: int = 10,
        filter_condition: Optional[Filter] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Search using text query (embeds internally)."""
        query_embedding = self.embedder.embed_single(query_text)
        return self.search(query_embedding, k, filter_condition, score_threshold)
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        exists = self.get_memory(memory_id) is not None
        self.client.delete(collection_name=self.collection_name,
                           points_selector=[self._memory_id_to_uuid(memory_id)])
        return exists

    def restore_memory(self, memory_id, snapshot):
        """Restore an exact payload/vector snapshot, then verify the payload."""
        if snapshot is None:
            self.client.delete(collection_name=self.collection_name,
                               points_selector=[self._memory_id_to_uuid(memory_id)])
        else:
            self.client.upsert(collection_name=self.collection_name, points=[
                PointStruct(id=snapshot["id"], vector=snapshot["vector"], payload=snapshot["payload"])
            ])
        restored = self.get_memory(memory_id)
        if snapshot is None:
            if restored is not None:
                raise RuntimeError("Vector rollback did not remove the new record.")
        elif restored is None or restored["payload"] != snapshot["payload"] or not np.allclose(restored["vector"], snapshot["vector"]):
            raise RuntimeError("Vector rollback verification failed.")
    
    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[self._memory_id_to_uuid(memory_id)],
            with_payload=True,
            with_vectors=True
        )
        if points:
            p = points[0]
            return {
                "id": p.id,
                "vector": p.vector,
                "payload": p.payload
            }
        return None
    
    def count(self) -> int:
        """Get collection count."""
        info = self.client.get_collection(self.collection_name)
        return info.points_count
    
    def scroll(
        self,
        limit: int = 100,
        offset: Any = None,
        with_payload: bool = True,
        with_vectors: bool = False
    ) -> Tuple[List[Any], Any]:
        """Scroll points in collection."""
        return self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vectors
        )
    
    def close(self):
        """Close the client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_temporal_filter(
    query_time: int,
    mode: str = "auto"  # "now", "historical", "auto"
) -> Filter:
    """
    Create temporal filter for time-aware retrieval.
    
    Args:
        query_time: Unix timestamp of query
        mode: "now" (valid at query_time), "historical" (expired), "auto" (all)
        
    Returns:
        Qdrant Filter
    """
    if mode == "now":
        return Filter(
            must=[
                FieldCondition(key="valid_from", range={"lte": query_time}),
                FieldCondition(key="valid_until", range={"gte": query_time})
            ]
        )
    elif mode == "historical":
        return Filter(
            must=[
                FieldCondition(key="valid_until", range={"lt": query_time})
            ]
        )
    else:  # auto - no temporal filter
        return None
