"""
Embedder module using FastEmbed (ONNX Runtime).
Supports CPU (default) and GPU (CUDAExecutionProvider) paths.
"""

import os
from threading import RLock
from typing import List, Optional
import numpy as np

from memory.device import ensure_cuda_dlls_loaded


# Default model: BAAI/bge-small-en-v1.5 (384-dim, fast, good quality)
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_instances = {}
_instances_lock = RLock()


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
        cache_dir: Optional[str] = None,
        batch_size: int = 32,
    ):
        """
        Initialize embedder.

        Args:
            model_name: FastEmbed model identifier
            use_gpu: Override global USE_GPU flag. If None, uses env var.
            cache_dir: Model cache directory
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.batch_size = batch_size
        self._inference_lock = RLock()

        # Resolve GPU flag: explicit arg > env var > default false
        self.use_gpu = (
            use_gpu
            if use_gpu is not None
            else os.getenv("USE_GPU", "false").lower() == "true"
        )

        if self.use_gpu:
            ensure_cuda_dlls_loaded()

        # Configure ONNX Runtime providers
        self._providers = self._get_providers()

        # Initialize FastEmbed model
        self._model = None
        self._init_model()

        # Embedding dimension (fixed for bge-small-en-v1.5)
        from fastembed import TextEmbedding

        self.dimension = next(
            m["dim"]
            for m in TextEmbedding.list_supported_models()
            if m["model"] == self.model_name
        )

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
        from fastembed import TextEmbedding

        try:
            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=self.cache_dir,
                providers=self._providers,
                threads=int(os.getenv("EMBEDDING_THREADS", "2")),
            )
            provider_str = ", ".join(self._providers)
            print(
                f"Embedder initialized: {self.model_name} (providers: {provider_str})"
            )
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
                    threads=int(os.getenv("EMBEDDING_THREADS", "2")),
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
        with self._inference_lock:
            embeddings = list(self._model.embed(texts, batch_size=self.batch_size))
        return np.array(embeddings, dtype=np.float32)

    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        return self.embed([text])[0]

    def __call__(self, texts: List[str]) -> np.ndarray:
        """Callable interface."""
        return self.embed(texts)


def get_embedder(
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 32,
    use_gpu: Optional[bool] = None,
    cache_dir: Optional[str] = None,
) -> Embedder:
    """
    Factory function to create an Embedder instance.

    Args:
        model_name: FastEmbed model identifier
        batch_size: Batch size passed to FastEmbed
        use_gpu: Override global USE_GPU flag
        cache_dir: Model cache directory

    Returns:
        Embedder instance
    """
    # Only model resources are shared. Graphs, vectors and journals remain scoped
    # to their authenticated traveler. Serialize creation to avoid duplicate ONNX
    # sessions when two travelers first use memory at the same time.
    gpu = use_gpu if use_gpu is not None else os.getenv("USE_GPU", "false").lower() == "true"
    key = (model_name, batch_size, gpu, cache_dir, os.getenv("EMBEDDING_THREADS", "2"))
    with _instances_lock:
        if key not in _instances:
            _instances[key] = Embedder(model_name=model_name, use_gpu=gpu,
                                       cache_dir=cache_dir, batch_size=batch_size)
        return _instances[key]
