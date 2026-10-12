"""Offline control-flow fixtures. Neural/provider validation is opt-in."""

import hashlib
import re
import numpy as np
import pytest


class FixtureEmbedder:
    dimension = 384
    _providers = ["CPUExecutionProvider"]

    def embed_single(self, text):
        vector = np.zeros(self.dimension, dtype=np.float32)
        for word in re.findall(r"[\w]+", text.lower()):
            index = (
                int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "little")
                % self.dimension
            )
            vector[index] += 1
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def embed(self, texts):
        return np.array([self.embed_single(text) for text in texts], dtype=np.float32)


class FixtureReranker:
    accelerated = False
    _providers = ["CPUExecutionProvider"]

    def rerank(self, query, candidates, top_k=None):
        embedder = FixtureEmbedder()
        query_vector = embedder.embed_single(query)
        for candidate in candidates:
            candidate["rerank_score"] = float(
                np.dot(query_vector, embedder.embed_single(candidate["text"]))
            )
        return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]


@pytest.fixture(autouse=True)
def offline_models(monkeypatch, request):
    if request.node.get_closest_marker("neural"):
        return
    import memory.engine as engine_module
    import memory.vector_store.qdrant_store as store_module
    from tests.fixtures.extractor import MockNIMExtractor

    monkeypatch.setattr(
        engine_module, "get_embedder", lambda **kwargs: FixtureEmbedder()
    )
    monkeypatch.setattr(
        engine_module, "get_reranker", lambda **kwargs: FixtureReranker()
    )
    monkeypatch.setattr(store_module, "Embedder", FixtureEmbedder)
    # Test fixtures must be explicit; never set an application's fallback policy.
    original_init = engine_module.MemoryEngine.__init__

    def init(self, *args, **kwargs):
        if not request.node.get_closest_marker("real_extraction_policy"):
            kwargs.setdefault("extractor", MockNIMExtractor())
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(engine_module.MemoryEngine, "__init__", init)
