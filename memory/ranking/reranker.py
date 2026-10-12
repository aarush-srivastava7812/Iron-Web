"""
Cross-encoder reranker using FastEmbed's ONNX cross-encoder.
Supports CPU (default) and GPU (CUDAExecutionProvider) paths.
"""
import os
from typing import List, Dict, Any, Optional
import numpy as np

from memory.device import configure_tensorrt_cache, ensure_cuda_dlls_loaded
ensure_cuda_dlls_loaded()
from fastembed.rerank.cross_encoder import TextCrossEncoder

# Global config flag
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

# Default reranker model
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"


class Reranker:
    """
    Cross-encoder reranker using FastEmbed's ONNX implementation.
    
    When USE_GPU=true: uses CUDAExecutionProvider (falls back to CPU if unavailable)
    When USE_GPU=false (default): uses CPUExecutionProvider only
    """
    
    def __init__(
        self,
        model_name: str = DEFAULT_RERANKER_MODEL,
        use_gpu: Optional[bool] = None,
        cache_dir: Optional[str] = None,
        batch_size: int = 16,
        prefer_tensorrt: bool = False,
        tensorrt_cache_path: Optional[str] = None,
    ):
        """
        Initialize reranker.
        
        Args:
            model_name: Cross-encoder model identifier
            use_gpu: Override global USE_GPU flag. If None, uses env var.
            cache_dir: Model cache directory
            batch_size: Batch size for reranking
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        self.prefer_tensorrt = prefer_tensorrt
        self.tensorrt_cache_path = tensorrt_cache_path
        
        # Resolve GPU flag
        self.use_gpu = use_gpu if use_gpu is not None else USE_GPU
        if self.use_gpu and self.prefer_tensorrt and self.tensorrt_cache_path:
            self.tensorrt_cache_path = configure_tensorrt_cache(self.tensorrt_cache_path)
        
        # Configure providers
        self._providers = self._get_providers()
        
        # Initialize model
        self._model = None
        self._init_model()
    
    def _get_providers(self) -> List[str]:
        """Get ONNX Runtime execution providers."""
        if self.use_gpu:
            try:
                import onnxruntime as ort
                avail = ort.get_available_providers()
                candidates = (["TensorrtExecutionProvider"] if self.prefer_tensorrt else [])
                candidates.extend(["CUDAExecutionProvider", "DmlExecutionProvider"])
                chosen = [p for p in candidates if p in avail]
                if not chosen:
                    chosen = ["CPUExecutionProvider"]
                else:
                    chosen.append("CPUExecutionProvider")
                return chosen
            except Exception:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        else:
            return ["CPUExecutionProvider"]

    @property
    def accelerated(self) -> bool:
        """Whether reranking is backed by a hardware accelerator."""
        return any(provider in {"CUDAExecutionProvider", "TensorrtExecutionProvider", "DmlExecutionProvider"} for provider in self._providers)
    
    def _init_model(self):
        """Initialize FastEmbed TextCrossEncoder."""
        try:
            self._model = TextCrossEncoder(
                model_name=self.model_name,
                cache_dir=self.cache_dir,
                providers=self._providers
            )
            # FastEmbed can silently drop an unavailable preferred provider.
            # Record the provider of the live ONNX session for accurate
            # telemetry and accelerator decisions.
            session = self._model.model.model
            if hasattr(session, "get_providers"):
                self._providers = session.get_providers()
            provider_str = ", ".join(self._providers)
            print(f"Reranker initialized: {self.model_name} (providers: {provider_str})")
        except Exception as e:
            if self.use_gpu and ("CUDA" in str(e) or "Dml" in str(e)):
                print(f"GPU initialization failed, falling back to CPU: {e}")
                self.use_gpu = False
                self._providers = ["CPUExecutionProvider"]
                self._model = TextCrossEncoder(
                    model_name=self.model_name,
                    cache_dir=self.cache_dir,
                    providers=self._providers
                )
            else:
                raise
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using cross-encoder.
        
        Args:
            query: Query text
            candidates: List of candidate dicts with 'text' field
            top_k: Number of top results to return (None = all)
            
        Returns:
            Reranked candidates with 'rerank_score' added
        """
        if not candidates:
            return []
        
        # Bound long conversational context before ONNX inference.  This is a
        # token-safe approximation that avoids sending unbounded transcripts.
        max_words = 256
        documents = [" ".join(cand.get("text", "").split()[:max_words]) for cand in candidates]
        
        # Get scores from cross-encoder
        scores = list(self._model.rerank(query, documents, batch_size=self.batch_size))
        
        # Add scores to candidates
        for cand, score in zip(candidates, scores):
            cand["rerank_score"] = float(score)
        
        # Sort by rerank score descending
        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        if top_k:
            candidates = candidates[:top_k]
        
        return candidates
    
    def score_pairs(self, pairs: List[tuple]) -> List[float]:
        """Score query-document pairs directly."""
        return list(self._model.rerank(pairs, batch_size=self.batch_size))


def get_reranker(
    model_name: str = DEFAULT_RERANKER_MODEL,
    providers: Optional[List[str]] = None,
    batch_size: int = 16,
    use_gpu: Optional[bool] = None,
    cache_dir: Optional[str] = None,
    prefer_tensorrt: bool = False,
    tensorrt_cache_path: Optional[str] = None,
) -> Reranker:
    """
    Factory function to create a Reranker instance.
    
    Args:
        model_name: Cross-encoder model identifier
        providers: ONNX Runtime providers (overrides use_gpu if provided)
        batch_size: Batch size for reranking
        use_gpu: Override global USE_GPU flag
        cache_dir: Model cache directory
        
    Returns:
        Reranker instance
    """
    if providers is not None:
        # If providers explicitly provided, determine use_gpu from it
        use_gpu = "CUDAExecutionProvider" in providers
    
    return Reranker(
        model_name=model_name,
        use_gpu=use_gpu,
        cache_dir=cache_dir,
        batch_size=batch_size,
        prefer_tensorrt=prefer_tensorrt,
        tensorrt_cache_path=tensorrt_cache_path,
    )
