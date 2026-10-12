"""Explicit research modes over the normal engine; names describe mechanisms."""

from memory.engine import MemoryEngine, serialized
from research.retrievers.inspired import (
    EntityNeighborhoodRetriever,
    DenseLexicalFusionRetriever,
    TemporalRoomRetriever,
)


class ResearchEngine(MemoryEngine):
    retrieval_modes = MemoryEngine.retrieval_modes | {
        "entity_neighborhood",
        "dense_lexical_fusion",
        "temporal_room",
    }

    @property
    def evaluation_identity(self):
        from memory.evaluation.harness.persistence import source_fingerprint

        return {"research_source": source_fingerprint(("research",))}

    @serialized
    def search(
        self,
        query,
        k=10,
        temporal_mode="auto",
        query_time=None,
        retrieval_mode="hybrid",
        document_ids=None,
    ):
        if retrieval_mode in MemoryEngine.retrieval_modes:
            return super().search(
                query, k, temporal_mode, query_time, retrieval_mode, document_ids
            )
        if (
            retrieval_mode not in self.retrieval_modes
            or not isinstance(query, str)
            or not 1 <= k <= 100
        ):
            raise ValueError("Invalid research retrieval request.")
        retrievers = {
            "entity_neighborhood": lambda: EntityNeighborhoodRetriever(
                self.embedder, self.vector_store, self.graph_store
            ),
            "dense_lexical_fusion": lambda: DenseLexicalFusionRetriever(
                self.embedder, self.vector_store
            ),
            "temporal_room": lambda: TemporalRoomRetriever(
                self.embedder, self.vector_store
            ),
        }
        hits = retrievers[retrieval_mode]().retrieve(
            query, k, query_time, temporal_mode, document_ids
        )
        return [self._search_result(hit, retrieval_mode) for hit in hits]
