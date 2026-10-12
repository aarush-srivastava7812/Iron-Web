"""Local vector/graph memory API. Optional models and clients are imported on demand."""

from importlib import import_module

_EXPORTS = {
    "MemoryEngine": ("memory.engine", "MemoryEngine"),
    "MemoryRecord": ("memory.models", "MemoryRecord"),
    "MemorySearchResult": ("memory.models", "MemorySearchResult"),
    "DeviceStatus": ("memory.models", "DeviceStatus"),
    "EngineStorageError": ("memory.models", "EngineStorageError"),
    "MemoryToolAdapter": ("memory.tool_adapter", "MemoryToolAdapter"),
    "QdrantVectorStore": ("memory.vector_store.qdrant_store", "QdrantVectorStore"),
    "KuzuGraphStore": ("memory.graph.kuzu_store", "KuzuGraphStore"),
    "Embedder": ("memory.embeddings.embedder", "Embedder"),
    "get_embedder": ("memory.embeddings.embedder", "get_embedder"),
    "Reranker": ("memory.ranking.reranker", "Reranker"),
    "get_reranker": ("memory.ranking.reranker", "get_reranker"),
    "HybridRetriever": ("memory.retrieval.hybrid", "HybridRetriever"),
    "RetrievalConfig": ("memory.ranking.scorer", "RetrievalConfig"),
    "ScoringWeights": ("memory.ranking.scorer", "ScoringWeights"),
    "IngestionPipeline": ("memory.ingestion.pipeline", "IngestionPipeline"),
    "NIMExtractor": ("memory.ingestion.nim_extractor", "NIMExtractor"),
    "TemporalFilter": ("memory.temporal.filter", "TemporalFilter"),
    "ContradictionDetector": ("memory.contradiction.detector", "ContradictionDetector"),
    "MaintenanceScheduler": ("memory.maintenance.maintenance", "MaintenanceScheduler"),
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
