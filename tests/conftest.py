"""Offline control-flow fixtures. Neural/provider validation is opt-in."""

import hashlib
import re
import numpy as np
import pytest
from tests.fixtures.graph import graph_name_for


@pytest.fixture(autouse=True)
def isolated_graphs(monkeypatch, tmp_path):
    """Use real named FalkorDB graphs; remove only graphs owned by this test."""
    from memory.graph import FalkorDBGraphStore

    original = FalkorDBGraphStore.__init__
    stores = []

    def init(store, *args, **kwargs):
        original(store, *args, **kwargs)
        if not store.graph_name.startswith(("test_", "iron_web_2_test_")):
            store.close()
            raise ValueError("Tests must use an isolated test_ graph.")
        stores.append(store)

    monkeypatch.setattr(FalkorDBGraphStore, "__init__", init)
    yield
    if not stores:
        return
    # Connection close leaves the persistent graph intact. A separate client
    # performs owned test cleanup, never FLUSHDB or removal of application data.
    from falkordb import FalkorDB
    import os

    client = FalkorDB(
        host=os.getenv("FALKORDB_HOST", "127.0.0.1"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
    )
    for name in {store.graph_name for store in stores}:
        if client.connection.exists(name):
            client.select_graph(name).delete()
        client.connection.delete(
            "{" + name + "}:revision",
            "{" + name + "}:lock",
            "{" + name + "}:publication",
        )
    client.close()


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
    for engine_type in (engine_module.MemoryEngine, engine_module.LegacyMemoryEngine):
        original_init = engine_type.__init__

        def init(self, *args, _original_init=original_init, **kwargs):
            kwargs.setdefault(
                "graph_name",
                graph_name_for(
                    request.node.nodeid + str(request.getfixturevalue("tmp_path"))
                ),
            )
            if not request.node.get_closest_marker("real_extraction_policy"):
                kwargs.setdefault("extractor", MockNIMExtractor())
            _original_init(self, *args, **kwargs)

        monkeypatch.setattr(engine_type, "__init__", init)
