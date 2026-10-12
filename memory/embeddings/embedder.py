"""
Embedder module using FastEmbed (ONNX Runtime).
Supports CPU (default) and GPU (CUDAExecutionProvider) paths.
"""
import os
from typing import List, Optional
import numpy as np

from memory.device import ensure_cuda_dlls_loaded
ensure_cuda_dlls_loaded()
from fastembed import TextEmbedding

# Global config flag
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"

# Default model: BAAI/bge-small-en-v1.5 (384-dim, fast, good quality)
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class Embedder:
    """
    FastEmbed-based text embedder with optional GPU acceleration.
    
    When USE_GPU=true: uses CUDAExecutionProvider (falls back to CPU if unavailable)
    When USE_GPU=false (default): uses CPUExecutionProvider only
    """
    
    def __init__(
        self, 
        model_name: str = DEFAULT_MODEL,
        use_gpu: Optional[bool] = None,
        quantize: bool = True,  # INT8 quantization for speed/memory
        cache_dir: Optional[str] = None
    ):
        """
        Initialize embedder.
        
        Args:
            model_name: FastEmbed model identifier
            use_gpu: Override global USE_GPU flag. If None, uses env var.
            quantize: Enable INT8 quantization (4x memory reduction, <2% recall loss)
            cache_dir: Model cache directory
        """
        self.model_name = model_name
        self.quantize = quantize
        self.cache_dir = cache_dir
        
        # Resolve GPU flag: explicit arg > env var > default false
        self.use_gpu = use_gpu if use_gpu is not None else USE_GPU
        
        # Configure ONNX Runtime providers
        self._providers = self._get_providers()
        
        # Initialize FastEmbed model
        self._model = None
        self._init_model()
        
        # Embedding dimension (fixed for bge-small-en-v1.5)
        self.dimension = 384
    
    def _get_providers(self) -> List[str]:
        """Get ONNX Runtime execution providers based on GPU flag."""
        if self.use_gpu:
            try:
                import onnxruntime as ort
                avail = ort.get_available_providers()
                candidates = ["CUDAExecutionProvider", "DmlExecutionProvider"]
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
    
    def _init_model(self):
        """Initialize FastEmbed TextEmbedding model."""
        try:
            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=self.cache_dir,
                providers=self._providers,
                quantize=self.quantize
            )
            provider_str = ", ".join(self._providers)
            print(f"Embedder initialized: {self.model_name} (providers: {provider_str})")
        except Exception as e:
            if self.use_gpu and ("CUDA" in str(e) or "Dml" in str(e)):
                # Fallback to CPU if GPU fails
                print(f"GPU initialization failed, falling back to CPU: {e}")
                self.use_gpu = False
                self._providers = ["CPUExecutionProvider"]
                self._model = TextEmbedding(
                    model_name=self.model_name,
                    cache_dir=self.cache_dir,
                    providers=self._providers,
                    quantize=self.quantize
                )
            else:
                raise
    
    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of texts.
        
        Args:
            texts: List of strings to embed
            
        Returns:
            numpy array of shape (len(texts), dimension)
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        
        # FastEmbed returns generator, convert to list then array
        embeddings = list(self._model.embed(texts))
        return np.array(embeddings, dtype=np.float32)
    
    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        return self.embed([text])[0]
    
    def __call__(self, texts: List[str]) -> np.ndarray:
        """Callable interface."""
        return self.embed(texts)


def get_embedder(
    model_name: str = DEFAULT_MODEL,
    providers: Optional[List[str]] = None,
    batch_size: int = 32,
    use_gpu: Optional[bool] = None,
    quantize: bool = True,
    cache_dir: Optional[str] = None
) -> Embedder:
    """
    Factory function to create an Embedder instance.
    
    Args:
        model_name: FastEmbed model identifier
        providers: ONNX Runtime providers (overrides use_gpu if provided)
        batch_size: Batch size for embedding (not used by FastEmbed directly)
        use_gpu: Override global USE_GPU flag
        quantize: Enable INT8 quantization
        cache_dir: Model cache directory
        
    Returns:
        Embedder instance
    """
    if providers is not None:
        # If providers explicitly provided, determine use_gpu from it
        use_gpu = "CUDAExecutionProvider" in providers
    
    return Embedder(
        model_name=model_name,
        use_gpu=use_gpu,
        quantize=quantize,
        cache_dir=cache_dir
    )
