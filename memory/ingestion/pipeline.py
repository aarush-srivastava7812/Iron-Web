"""Compatibility ingestion adapter; all storage writes go through MemoryEngine."""

from pathlib import Path


class IngestionPipeline:
    def __init__(
        self,
        embedder,
        vector_store,
        graph_store,
        extractor=None,
        contradiction_detector=None,
    ):
        # This adapter coordinates explicitly injected legacy stores. Native
        # application ingestion uses ApplicationMemoryEngine.add directly.
        from memory.engine import LegacyMemoryEngine as MemoryEngine

        self.engine = MemoryEngine(
            config={"extraction_policy": "none"},
            embedder=embedder,
            vector_store=vector_store,
            graph_store=graph_store,
            extractor=extractor,
        )
        self.contradiction_detector = contradiction_detector

    def ingest_text(self, text, memory_id=None, metadata=None, timestamp=None):
        return self.ingest_text_with_extraction(text, memory_id, metadata, timestamp)

    def ingest_text_with_extraction(
        self, text, memory_id=None, metadata=None, timestamp=None, extraction=None
    ):
        def enrich(mid):
            own = self.engine.graph_store.get_memory_observations(mid)
            own_ids = {o["id"] for o in own}
            for observation in own:
                candidates = self.engine.graph_store.get_observations(
                    observation["entity_id"], valid_at=timestamp
                )
                conflicts = self.contradiction_detector.detect_contradictions(
                    observation["id"],
                    text,
                    [observation["entity_id"]],
                    [o["id"] for o in candidates if o["id"] not in own_ids],
                )
                for conflict in conflicts:
                    self.contradiction_detector.store_contradiction(conflict)

        return self.engine.add(
            text,
            memory_id=memory_id,
            metadata=metadata,
            timestamp=timestamp,
            extraction=extraction,
            enrich_graph=enrich if self.contradiction_detector else None,
        )

    def ingest_batch(self, texts, metadata_list=None, timestamp=None):
        if metadata_list is not None and len(metadata_list) != len(texts):
            raise ValueError("Content and metadata lengths differ.")
        return self.engine.add_batch(
            texts, metadatas=metadata_list, timestamps=[timestamp] * len(texts)
        )

    def ingest_from_file(self, file_path, chunk_size=1000, chunk_overlap=200):
        return self.ingest_batch(
            self._chunk_text(
                Path(file_path).read_text(encoding="utf-8"), chunk_size, chunk_overlap
            )
        )

    @staticmethod
    def _chunk_text(text, chunk_size, overlap):
        if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                "Chunk size must be positive, with overlap smaller than the chunk."
            )
        chunks, start = [], 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = end - overlap
        return chunks
