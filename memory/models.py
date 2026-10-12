"""
Data models for the Unified Memory Engine.
Includes typed representations for memory records, search results,
queries, device status, and exceptions.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class MemoryMetadata(BaseModel):
    """Structured or arbitrary metadata attached to a memory."""
    source: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    custom: Dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    """
    Unified representation of an individual memory across vector and graph stores.
    """
    memory_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entity_ids: List[str] = Field(default_factory=list)
    valid_from: int = 0
    valid_until: int = 2**31 - 1
    importance: float = 1.0
    timestamp: int = 0
    created_at: Optional[int] = None
    vector_stored: bool = True
    graph_stored: bool = True


class MemorySearchResult(BaseModel):
    """
    Structured result returned by MemoryEngine.search().
    Contains the content, identifier, relevance scores, and provenance.
    """
    memory_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    entity_ids: List[str] = Field(default_factory=list)
    retrieval_method: str = "vector"  # "hybrid", "vector", "graph", "contrastive"
    timestamp: Optional[int] = None
    valid_from: Optional[int] = None
    valid_until: Optional[int] = None
    importance: Optional[float] = None
    is_superseded: bool = False
    retrieval_trace: Dict[str, Any] = Field(default_factory=dict)


class SearchFilter(BaseModel):
    """Configuration and filters for retrieval operations."""
    k: int = 10
    temporal_mode: str = "auto"  # "auto", "now", "historical"
    query_time: Optional[int] = None
    retrieval_mode: str = "hybrid"  # "hybrid" or "vector"
    score_threshold: Optional[float] = None


class DeviceStatus(BaseModel):
    """
    Observable hardware and execution provider status.
    Tracks GPU acceleration, active ONNX providers, and measurable VRAM usage.
    """
    gpu_enabled_requested: bool
    cuda_available: bool
    active_providers: List[str]
    embedder_provider: str
    reranker_provider: str
    vram_total_mb: Optional[float] = None
    vram_used_mb: Optional[float] = None
    vram_free_mb: Optional[float] = None
    vram_budget_mb: float = 5120.0       # 5.0 GB operational ceiling
    safety_buffer_mb: float = 1024.0     # 1.0 GB reserved for Windows / display
    execution_mode: str                  # "GPU (CUDA)" or "CPU Fallback"
    status_notes: str


class EngineStorageError(RuntimeError):
    """Raised when a cross-store write or update fails and rollback is performed."""
    def __init__(self, message: str, memory_id: str, rolled_back: bool = True):
        super().__init__(message)
        self.memory_id = memory_id
        self.rolled_back = rolled_back
