"""Adapt package ingestion/search to the shared evaluation runner's backend contract."""

import time
from memory.models import MemorySearchResult, DeviceStatus
from memory.evaluation.harness.persistence import source_fingerprint


class SDKBackend:
    def __init__(self, package, use_gpu=False):
        self.package = package
        self.use_gpu = use_gpu
        self.extractor = None
        self.retrieval_modes = {package.name}
        self.config_data = dict(
            package=package.configuration,
            research_source=source_fingerprint(("research",)),
        )
        self.documents = {}

    def memory_ids(self):
        return set(self.documents)

    def ingest_documents(self, documents, batch_size=20, show_progress=False):
        started = time.perf_counter()
        from dataclasses import asdict

        payload = [asdict(document) for document in documents]
        self.package.setup_and_ingest(payload)
        self.documents = {document.doc_id: document for document in documents}
        return dict(
            num_documents=len(documents),
            ingested_ids=len(documents),
            ingestion_time_sec=time.perf_counter() - started,
            confirmation="verified_by_package_search",
        )

    def search(
        self,
        query,
        k=10,
        temporal_mode="auto",
        query_time=None,
        retrieval_mode=None,
        document_ids=None,
    ):
        if temporal_mode != "auto":
            raise ValueError(
                "This package adapter does not implement temporal validity filtering."
            )
        if document_ids is not None and set(document_ids) != set(self.documents):
            raise ValueError(
                "SDK evaluation requires one complete conversation cohort per namespace."
            )
        ids, contents = self.package.search(query, k)
        if len(ids) != len(contents):
            raise ValueError("SDK result IDs and contents have different lengths.")
        if set(ids) - set(self.documents):
            raise ValueError("SDK returned documents outside the isolated corpus.")
        return [
            MemorySearchResult(
                memory_id=mid,
                content=text,
                score=None,
                retrieval_method=self.package.name,
            )
            for mid, text in zip(ids, contents)
        ]

    def get_device_status(self):
        return DeviceStatus(
            gpu_enabled_requested=self.use_gpu,
            cuda_available=None,
            active_providers=[],
            embedder_provider="Uninspected package",
            reranker_provider="Uninspected package",
            execution_mode="Package-managed execution",
            status_notes="SDK provider status is not exposed by this adapter.",
        )
