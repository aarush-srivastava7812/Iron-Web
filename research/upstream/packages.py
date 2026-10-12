"""Optional genuine SDK adapters. Their response/ingestion failures are not converted into empty results.

These adapters are used with local retrieval metrics, not official benchmark scoring protocols.
"""

import json
import os
import time
from importlib.metadata import version
from pathlib import Path
from memory.evaluation.harness.persistence import fingerprint, write_atomic


def _ids_and_text(hits, text_field):
    ids, texts = [], []
    for hit in hits:
        metadata = hit.get("metadata") or {}
        mid = metadata.get("doc_id")
        if not mid:
            raise ValueError("SDK result has no original document ID.")
        if mid not in ids:
            ids.append(mid)
            texts.append(hit.get(text_field, ""))
    return ids, texts


class Mem0Package:
    name = "sdk_mem0"

    def __init__(self, namespace, directory, use_gpu=False):
        if use_gpu:
            raise ValueError(
                "The GPU flag is implemented only for the MemPalace package adapter."
            )
        from mem0 import Memory

        self.namespace = namespace
        self.configuration = dict(
            package="mem0ai",
            version=version("mem0ai"),
            embedding_model="BAAI/bge-small-en-v1.5",
            infer=False,
        )
        self.memory = Memory.from_config(
            {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": str(directory / "vectors"),
                        "on_disk": True,
                        "embedding_model_dims": 384,
                    },
                },
                "embedder": {
                    "provider": "fastembed",
                    "config": {"model": "BAAI/bge-small-en-v1.5"},
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": "meta/llama-3.1-70b-instruct",
                        "api_key": os.environ.get("NVIDIA_API_KEY"),
                        "openai_base_url": "https://integrate.api.nvidia.com/v1",
                    },
                },
                "version": "v1.1",
            }
        )

    def search(self, query, k):
        response = self.memory.search(
            query, filters={"user_id": self.namespace}, limit=k
        )
        return _ids_and_text(response["results"], "memory")

    def setup_and_ingest(self, documents):
        for document in documents:
            existing, _ = self.search(document["text"], 10)
            if document["doc_id"] not in existing:
                self.memory.add(
                    document["text"],
                    metadata={"doc_id": document["doc_id"]},
                    user_id=self.namespace,
                    infer=False,
                )
            verified, _ = self.search(document["text"], 10)
            if document["doc_id"] not in verified:
                raise RuntimeError(
                    f"Mem0 ingestion could not be verified for {document['doc_id']}."
                )


class ZepPackage:
    name = "sdk_zep"

    def __init__(self, namespace, directory, use_gpu=False):
        if use_gpu:
            raise ValueError(
                "The GPU flag is implemented only for the MemPalace package adapter."
            )
        from zep_cloud.client import Zep

        self.namespace = namespace
        self.configuration = dict(
            package="zep-cloud", version=version("zep-cloud"), scope="episodes"
        )
        self.client = Zep(api_key=os.environ.get("ZEP_API_KEY"))
        try:
            self.client.user.add(user_id=namespace)
        except Exception as error:
            if getattr(error, "status_code", None) != 409:
                raise

    def search(self, query, k):
        response = self.client.graph.search(
            user_id=self.namespace, query=query, scope="episodes", limit=k
        )
        hits = [
            {
                "metadata": dict(
                    ep.metadata or {},
                    doc_id=(ep.metadata or {}).get("doc_id") or ep.document_id,
                ),
                "content": ep.content,
            }
            for ep in (response.episodes or [])
        ]
        return _ids_and_text(hits, "content")

    def setup_and_ingest(self, documents):
        for document in documents:
            existing, _ = self.search(document["text"], 10)
            if document["doc_id"] not in existing:
                self.client.graph.add(
                    user_id=self.namespace,
                    data=document["text"],
                    type="text",
                    document_id=document["doc_id"],
                    metadata={"doc_id": document["doc_id"]},
                )
            for attempt in range(3):
                verified, _ = self.search(document["text"], 10)
                if document["doc_id"] in verified:
                    break
                if attempt < 2:
                    time.sleep(2)
            else:
                raise RuntimeError(
                    f"Zep has not exposed document {document['doc_id']} after ingestion; retry the run."
                )


class MemPalacePackage:
    name = "sdk_mempalace"

    def __init__(self, namespace, directory, use_gpu=False):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.inputs, self.palace = directory / "inputs", directory / "palace"
        self.mapping = {}
        self.configuration = dict(
            package="mempalace",
            version=version("mempalace"),
            requested_device="cuda" if use_gpu else "cpu",
        )
        os.environ["MEMPALACE_EMBEDDING_DEVICE"] = "cuda" if use_gpu else "cpu"
        if use_gpu:
            from memory.device import ensure_cuda_dlls_loaded

            ensure_cuda_dlls_loaded()

    def setup_and_ingest(self, documents):
        from mempalace.miner import mine

        signature = fingerprint(documents)
        manifest_path = self.directory / "input_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["fingerprint"] != signature:
                raise ValueError(
                    "MemPalace input version differs; use a new namespace."
                )
            self.mapping = manifest["mapping"]
        else:
            self.inputs.mkdir(parents=True, exist_ok=True)
            for document in documents:
                filename = fingerprint(document["doc_id"])[:24] + ".txt"
                write_atomic(self.inputs / filename, document["text"])
                self.mapping[filename] = document["doc_id"]
            write_atomic(
                manifest_path,
                json.dumps(dict(fingerprint=signature, mapping=self.mapping), indent=2),
            )
        if not (self.palace / "chroma.sqlite3").exists():
            mine(project_dir=str(self.inputs), palace_path=str(self.palace))
        for document in documents:
            ids, _ = self.search(document["text"], 20)
            if document["doc_id"] not in ids:
                raise RuntimeError(
                    f"MemPalace ingestion could not be verified for {document['doc_id']}."
                )

    def search(self, query, k):
        from mempalace.searcher import search_memories

        response = search_memories(
            query=query, palace_path=str(self.palace), n_results=k
        )
        if response.get("error"):
            raise RuntimeError(response["error"])
        ids, texts = [], []
        for hit in response["results"]:
            mid = self.mapping.get(Path(hit.get("source_file", "")).name)
            if not mid:
                raise ValueError("MemPalace result has an unmapped source file.")
            if mid not in ids:
                ids.append(mid)
                texts.append(hit.get("text", ""))
        return ids, texts


PACKAGES = {"mem0": Mem0Package, "zep": ZepPackage, "mempalace": MemPalacePackage}
