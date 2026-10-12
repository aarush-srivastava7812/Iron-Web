"""
Hybrid Long-Term AI Memory System

A production-ready hybrid memory architecture combining:
- Episodic memory (LangGraph checkpointer)
- Semantic memory (Qdrant + FastEmbed)
- Procedural memory (Kuzu graph)
- Hybrid retrieval (Vector + Graph + Reranker)
- Contrastive retrieval
- Temporal filtering
- Contradiction detection
- Maintenance (decay, dedup, consolidation)
"""
from memory.embeddings.embedder import Embedder, get_embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph import KuzuGraphStore, create_graph_store, RelationType, GraphStore
from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig
from memory.retrieval.contrastive import ContrastiveRetriever
from memory.ranking.reranker import Reranker, get_reranker
from memory.ranking.scorer import ScoringWeights, RetrievalConfig
from memory.temporal.filter import TemporalFilter
from memory.contradiction.detector import ContradictionDetector
from memory.maintenance.maintenance import MaintenanceManager
from memory.ingestion.pipeline import IngestionPipeline
from memory.ingestion.nim_extractor import NIMExtractor
from memory.models import (
    MemoryRecord,
    MemorySearchResult,
    MemoryMetadata,
    SearchFilter,
    DeviceStatus,
    EngineStorageError,
)
from memory.engine import MemoryEngine

__version__ = "1.0.0"
__all__ = [
    "MemoryEngine",
    "MemoryRecord",
    "MemorySearchResult",
    "MemoryMetadata",
    "SearchFilter",
    "DeviceStatus",
    "EngineStorageError",
    "Embedder",
    "get_embedder",
    "QdrantVectorStore",
    "KuzuGraphStore",
    "create_graph_store",
    "RelationType",
    "GraphStore",
    "HybridRetriever",
    "RetrievalConfig",
    "ContrastiveRetriever",
    "Reranker",
    "get_reranker",
    "ScoringWeights",
    "TemporalFilter",
    "ContradictionDetector",
    "MaintenanceManager",
    "IngestionPipeline",
    "NIMExtractor",
]