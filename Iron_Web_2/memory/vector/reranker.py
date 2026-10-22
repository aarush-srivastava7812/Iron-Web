"""Small GPU cross-encoder using the existing FastEmbed/ONNX runtime."""

from functools import lru_cache
import math
from pathlib import Path
from threading import RLock

from fastembed.rerank.cross_encoder import TextCrossEncoder
from fastembed.common.model_description import ModelSource
import onnxruntime as ort
from tokenizers import Tokenizer

from .store import MAX_CANDIDATES, checked_text


RERANKER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1-fp32"


class Reranker:
    def __init__(self, cache_dir=None, *, device="cuda", profile=False):
        if device not in {"cuda", "cpu"}:
            raise ValueError("Device must be cuda or cpu.")
        cache_dir = cache_dir or Path(__file__).resolve().parents[2] / "data" / "models"
        if not any(
            m["model"] == RERANKER_MODEL
            for m in TextCrossEncoder.list_supported_models()
        ):
            TextCrossEncoder.add_custom_model(
                model=RERANKER_MODEL,
                sources=ModelSource(hf="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"),
                model_file="onnx/model.onnx",
                license="apache-2.0",
                description="Multilingual mMARCO MiniLMv2 cross-encoder FP32",
            )
        if device == "cuda":
            ort.preload_dlls()
            if "CUDAExecutionProvider" not in ort.get_available_providers():
                raise RuntimeError(
                    "Reranking requires CUDA; CPU must be explicitly selected."
                )
        self.model = TextCrossEncoder(
            RERANKER_MODEL,
            cache_dir=str(cache_dir),
            threads=2,
            providers=[
                (
                    "CUDAExecutionProvider",
                    {
                        "gpu_mem_limit": 2 * 1024**3,
                        "arena_extend_strategy": "kSameAsRequested",
                    },
                )
            ]
            if device == "cuda"
            else ["CPUExecutionProvider"],
        )
        self.session = self.model.model.model
        if (
            device == "cuda"
            and self.session.get_providers()[0] != "CUDAExecutionProvider"
        ):
            raise RuntimeError(
                "Reranker CUDA initialization failed; refusing CPU fallback."
            )
        if profile:
            options = ort.SessionOptions()
            options.enable_profiling = True
            options.profile_file_prefix = str(Path(cache_dir) / "reranker_gpu_profile")
            self.session = ort.InferenceSession(
                self.session._model_path,
                sess_options=options,
                providers=self.session.get_providers(),
                provider_options=[
                    self.session.get_provider_options()[p]
                    for p in self.session.get_providers()
                ],
            )
            self.model.model.model = self.session
        self.session.disable_fallback()
        self.tokenizer = Tokenizer.from_str(self.model.model.tokenizer.to_str())
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.lock = RLock()
        self.device = device
        self.model_name = RERANKER_MODEL
        # Keep attention buffers bounded on the local 6-GB GPU, including long chunks.
        self.batch_size = 4
        self.calls = self.pairs = 0

    def score(self, query, documents):
        query = checked_text(query)
        documents = [checked_text(d) for d in documents]
        if len(documents) > MAX_CANDIDATES:
            raise ValueError("Reranking is bounded to 1000 candidates.")
        if not documents:
            return []
        with self.lock:
            if any(
                len(pair.ids) > 512
                for pair in self.tokenizer.encode_batch(
                    [(query, text) for text in documents]
                )
            ):
                raise ValueError(
                    "Query and memory exceed the reranker's 512-token window; split the memory or shorten the query."
                )
            scores = list(
                self.model.rerank(query, documents, batch_size=self.batch_size)
            )
            if len(scores) != len(documents) or not all(
                math.isfinite(s) for s in scores
            ):
                raise ValueError("Reranker returned invalid scores.")
            self.calls += 1
            self.pairs += len(documents)
            return scores


@lru_cache(maxsize=2)
def default_reranker(device="cuda"):
    """Share a model session across owners, never their memories or scores."""
    return Reranker(device=device)
