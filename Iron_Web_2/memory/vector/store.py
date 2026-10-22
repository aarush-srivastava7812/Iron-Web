"""Native FalkorDB vectors; one graph per caller-bound private owner."""

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from threading import RLock
import time
import unicodedata
from uuid import uuid4

from falkordb import FalkorDB
from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
import onnxruntime as ort
from tokenizers import Tokenizer


MODEL = "intfloat/multilingual-e5-small-fp32"
DIMENSION = 384
MAX_CANDIDATES = 1000


def checked_text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Text must be a nonempty string.")
    if "\x00" in value or len(value) > 32000:
        raise ValueError("Text contains a null byte or exceeds 32000 characters.")
    return unicodedata.normalize("NFC", value.strip())


class Embeddings:
    """GPU-first local inference; CPU execution must be explicitly requested."""

    def __init__(self, cache_dir=None, *, device="cuda", profile=False):
        if device not in {"cuda", "cpu"}:
            raise ValueError("Device must be cuda or cpu.")
        if device == "cuda":
            ort.preload_dlls()
            if "CUDAExecutionProvider" not in ort.get_available_providers():
                raise RuntimeError(
                    "CUDA is unavailable. Use the Iron_Web_2 GPU environment or explicitly select CPU."
                )
        if not any(m["model"] == MODEL for m in TextEmbedding.list_supported_models()):
            TextEmbedding.add_custom_model(
                model=MODEL,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf="intfloat/multilingual-e5-small"),
                dim=DIMENSION,
                model_file="onnx/model.onnx",
                description="Multilingual E5 small FP32, mean pooling, query/passage prefixes",
                license="mit",
            )
        self.model = TextEmbedding(
            model_name=MODEL,
            cache_dir=str(cache_dir) if cache_dir else None,
            providers=[
                (
                    "CUDAExecutionProvider",
                    {
                        "gpu_mem_limit": 1024 * 1024 * 1024,
                        "arena_extend_strategy": "kSameAsRequested",
                    },
                )
            ]
            if device == "cuda"
            else ["CPUExecutionProvider"],
            threads=2,
        )
        self.session = self.model.model.model
        if (
            device == "cuda"
            and self.session.get_providers()[0] != "CUDAExecutionProvider"
        ):
            raise RuntimeError(
                "CUDA initialization failed; refusing silent CPU fallback."
            )
        self.device = device
        # Profiling uses the same model/providers as inference, so main.py can inspect kernel placement.
        if profile:
            options = ort.SessionOptions()
            options.enable_profiling = True
            options.profile_file_prefix = str(Path(cache_dir) / "gpu_profile")
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
        # Count without the inference tokenizer's truncation so data isn't silently lost.
        self.tokenizer = Tokenizer.from_str(self.model.model.tokenizer.to_str())
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.lock = RLock()
        self._cached = lru_cache(maxsize=128)(self._embed)

    def _embed(self, text, query):
        with self.lock:
            # Leave room for the model's retrieval instruction and special tokens.
            if len(self.tokenizer.encode(text).ids) > 450:
                raise ValueError(
                    "Text exceeds 450 tokens; split it into smaller memories."
                )
            # E5 requires these English prefixes even for Hindi or mixed-language text.
            prepared = ("query: " if query else "passage: ") + text
            values = next(self.model.embed([prepared]))
        result = tuple(float(v) for v in values)
        if len(result) != DIMENSION or not all(math.isfinite(v) for v in result):
            raise ValueError("The embedding model returned an invalid vector.")
        return result

    def encode(self, text, *, query=False):
        return list(self._cached(checked_text(text), query))

    def cache_info(self):
        return self._cached.cache_info()._asdict()

    def clear(self):
        self._cached.cache_clear()


class VectorMemory:
    """Callable vector API: memory('store'|'search'|'forget', **arguments).

    Owner is bound by the caller when constructing this object, never supplied by
    an agent tool. This is namespace separation, not database authentication.
    Embedding cache is local and disposable; search results are not cached.
    """

    def __init__(
        self,
        owner,
        *,
        embeddings=None,
        namespace="iron_web_2_vector",
        host="127.0.0.1",
        port=6380,
        password=None,
        tls=False,
    ):
        owner = checked_text(owner)
        if not re.fullmatch(r"iron_web_2_[A-Za-z0-9_]{1,80}", namespace):
            raise ValueError("Use a dedicated iron_web_2_ namespace.")
        self.graph_name = (
            namespace + "_" + hashlib.sha256(owner.encode()).hexdigest()[:24]
        )
        self.client = FalkorDB(
            host=host,
            port=port,
            password=password,
            ssl=tls,
            socket_timeout=15,
            socket_connect_timeout=5,
        )
        self.graph = self.client.select_graph(self.graph_name)
        self.embeddings = embeddings
        self.lock = RLock()
        # An explicit contract prevents mixing models even if their dimensions match.
        rows = self.graph.query(
            "MERGE (c:VectorConfiguration {id:'embedding'}) "
            "ON CREATE SET c.model=$model,c.dimension=$dimension "
            "RETURN c.model,c.dimension",
            {"model": MODEL, "dimension": DIMENSION},
        ).result_set
        if rows != [[MODEL, DIMENSION]]:
            raise ValueError(
                "Stored embedding model differs; use a new namespace and re-embed."
            )
        indexes = self.graph.query("CALL db.indexes()").result_set
        vector_index = next(
            (
                r
                for r in indexes
                if r[0] == "VectorMemory" and "VECTOR" in r[2].get("embedding", [])
            ),
            None,
        )
        if vector_index:
            options = vector_index[3]["embedding"]
            if (
                options["dimension"] != DIMENSION
                or options["similarityFunction"] != "cosine"
            ):
                raise ValueError("Existing vector index has incompatible settings.")
        else:
            self.graph.query(
                "CREATE VECTOR INDEX FOR (m:VectorMemory) ON (m.embedding) "
                "OPTIONS {dimension:384,similarityFunction:'cosine'}"
            )
        if not any(
            r[0] == "VectorMemory" and "RANGE" in r[2].get("id", []) for r in indexes
        ):
            self.graph.query("CREATE INDEX FOR (m:VectorMemory) ON (m.id)")

    def _encoder(self):
        if self.embeddings is None:
            self.embeddings = Embeddings(
                Path(__file__).resolve().parents[2] / "data" / "models"
            )
        return self.embeddings

    def __call__(self, operation, **arguments):
        methods = {"store": self.store, "search": self.search, "forget": self.forget}
        if operation not in methods:
            raise ValueError("Supported vector operations: store, search, forget.")
        with self.lock:
            return methods[operation](**arguments)

    def store(self, text, metadata=None, memory_id=None):
        text = checked_text(text)
        memory_id = checked_text(memory_id) if memory_id is not None else uuid4().hex
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("Metadata must be a JSON object.")
        encoded = json.dumps(metadata or {}, ensure_ascii=False, allow_nan=False)
        vector = self._encoder().encode(text)
        result = self.graph.query(
            "MERGE (m:VectorMemory {id:$id}) "
            "ON CREATE SET m.created_at=$now "
            "WITH m WHERE NOT m:Source "
            "SET m.text=$text,m.metadata_json=$metadata,m.embedding=vecf32($vector),"
            "m.updated_at=$now,m.model=$model RETURN m.id",
            {
                "id": memory_id,
                "text": text,
                "metadata": encoded,
                "vector": vector,
                "model": MODEL,
                "now": int(time.time()),
            },
        )
        if not result.result_set:
            raise ValueError(
                "Source evidence is immutable; ingest a new event to correct it."
            )
        return {"memory_id": memory_id, "text": text, "metadata": json.loads(encoded)}

    def search(self, query, limit=5):
        if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
            raise ValueError("Limit must be an integer from 1 to 1000.")
        vector = self._encoder().encode(query, query=True)
        rows = self.graph.query(
            "CALL db.idx.vector.queryNodes('VectorMemory','embedding',$limit,vecf32($vector)) "
            "YIELD node,score RETURN node.id,node.text,node.metadata_json,score "
            "ORDER BY score ASC,node.id",
            {"limit": limit, "vector": vector},
        ).result_set
        return [
            {
                "memory_id": mid,
                "text": text,
                "metadata": json.loads(meta),
                "distance": float(distance),
                "similarity": 1.0 - float(distance),
            }
            for mid, text, meta, distance in rows
        ]

    def forget(self, memory_id):
        if self.graph.query(
            "MATCH (s:Source {id:$id}) RETURN s.id", {"id": memory_id}
        ).result_set:
            raise PermissionError(
                "Delete graph evidence through Memory('forget'), not the vector API."
            )
        rows = self.graph.query(
            "MATCH (m:VectorMemory {id:$id}) DETACH DELETE m RETURN count(m)",
            {"id": checked_text(memory_id)},
        ).result_set
        # Cached vectors retain source text, so forget clears this instance's encoder cache.
        if self.embeddings:
            self.embeddings.clear()
        return {"memory_id": memory_id, "deleted": bool(rows and rows[0][0])}

    def close(self):
        if self.embeddings:
            self.embeddings.clear()
        self.client.connection.close()
