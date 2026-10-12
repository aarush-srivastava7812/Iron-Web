"""Validated, effective application settings. Credentials come from the environment."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from memory.ranking.scorer import ScoringWeights


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VectorSettings(Settings):
    path: str = "./data/qdrant"
    collection_name: str = "semantic_memory"
    vector_size: int = Field(default=384, ge=1)


class GraphSettings(Settings):
    path: str = "./data/kuzu/memory.db"


class EmbeddingSettings(Settings):
    model: str = "BAAI/bge-small-en-v1.5"
    batch_size: int = Field(default=32, ge=1, le=128)
    cache_dir: str | None = None


class RerankerSettings(Settings):
    model: str = "BAAI/bge-reranker-base"
    batch_size: int = Field(default=16, ge=1, le=64)
    cache_dir: str | None = None
    prefer_tensorrt: bool = False
    tensorrt_cache_path: str = "./data/tensorrt_cache"


class RetrievalSettings(Settings):
    reranker_enabled: bool = False
    vector_candidates: int = Field(default=100, ge=1, le=1000)
    graph_hops: int = Field(default=2, ge=1, le=2)
    graph_max_nodes: int = Field(default=50, ge=1, le=100)
    entity_lookup_cache: bool = True
    weights: ScoringWeights = Field(default_factory=ScoringWeights)


class NIMSettings(Settings):
    base_url: str = "https://integrate.api.nvidia.com/v1"
    extractor_model: str = "meta/llama-3.2-11b-vision-instruct"
    cache_dir: str = "./data/extraction_cache"


class EngineSettings(Settings):
    USE_GPU: bool = False
    extraction_policy: Literal["none", "nim"] = "none"
    qdrant: VectorSettings = Field(default_factory=VectorSettings)
    kuzu: GraphSettings = Field(default_factory=GraphSettings)
    embeddings: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    reranker: RerankerSettings = Field(default_factory=RerankerSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    nim: NIMSettings = Field(default_factory=NIMSettings)
