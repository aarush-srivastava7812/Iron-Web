"""
Ingestion pipeline: text -> embeddings + graph extraction -> vector store + graph store.
"""
from typing import List, Dict, Any, Optional
import time
import uuid
from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph import KuzuGraphStore, GraphStore
from memory.ingestion.nim_extractor import NIMExtractor
from memory.contradiction.detector import ContradictionDetector


class IngestionPipeline:
    """
    Full ingestion pipeline:
    1. Text preprocessing
    2. Embedding generation (FastEmbed)
    3. NIM extraction (entities, relations, temporal, importance)
    4. Vector store upsert (Qdrant)
    5. Graph store upsert (Kuzu or Neo4j)
    6. Contradiction detection
    """
    
    def __init__(
        self,
        embedder: Embedder,
        vector_store: QdrantVectorStore,
        graph_store: GraphStore,
        extractor: NIMExtractor,
        contradiction_detector: Optional[ContradictionDetector] = None
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.extractor = extractor
        self.contradiction_detector = contradiction_detector
    
    def ingest_text(
        self,
        text: str,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None
    ) -> str:
        """
        Ingest a single text into memory.
        
        Returns:
            memory_id of created memory
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        if memory_id is None:
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        
        # Step 1: Generate embedding
        embedding = self.embedder.embed_single(text)
        
        # Step 2: NIM extraction
        extraction = self.extractor.extract_entities_and_relations(text)
        
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])
        temporal = extraction.get("temporal", {})
        importance = extraction.get("importance", 0.5)
        
        valid_from = temporal.get("valid_from", 0)
        valid_until = temporal.get("valid_until", 2**31 - 1)
        
        # Step 3: Collect entity IDs
        entity_ids = [e["id"] for e in entities]
        
        # Step 4: Upsert to vector store
        self.vector_store.upsert_memory(
            memory_id=memory_id,
            text=text,
            embedding=embedding,
            entity_ids=entity_ids,
            valid_from=valid_from,
            valid_until=valid_until,
            importance=importance,
            memory_type="semantic",
            metadata=metadata,
            timestamp=timestamp
        )
        
        # Step 5: Upsert entities to graph
        for entity in entities:
            self.graph_store.upsert_entity(
                entity_id=entity["id"],
                name=entity["name"],
                entity_type=entity["type"],
                description=entity.get("description", ""),
                importance=importance,
                timestamp=timestamp
            )
        
        # Step 6: Upsert relations to graph
        for rel in relations:
            self.graph_store.upsert_relation(
                from_id=rel["from"],
                to_id=rel["to"],
                relation_type=rel["type"],
                confidence=rel.get("confidence", 0.5),
                valid_from=valid_from,
                valid_until=valid_until,
                timestamp=timestamp
            )
        
        # Step 7: Create observations for each entity
        for entity in entities:
            obs_id = f"obs_{memory_id}_{entity['id']}"
            self.graph_store.upsert_observation(
                obs_id=obs_id,
                entity_id=entity["id"],
                content=text,
                embedding=embedding.tolist(),
                valid_from=valid_from,
                valid_until=valid_until,
                importance=importance,
                source="ingestion",
                timestamp=timestamp
            )
        
        # Step 8: Contradiction detection
        if self.contradiction_detector and entity_ids:
            # Get existing observations for these entities
            existing_obs_ids = []
            for eid in entity_ids:
                obs_list = self.graph_store.get_observations(eid, valid_at=timestamp, limit=20)
                existing_obs_ids.extend([o["id"] for o in obs_list])
            
            # Remove self
            existing_obs_ids = [oid for oid in existing_obs_ids if oid != memory_id]
            
            if existing_obs_ids:
                contradictions = self.contradiction_detector.detect_contradictions(
                    new_obs_id=memory_id,
                    new_content=text,
                    new_entity_ids=entity_ids,
                    candidate_obs_ids=existing_obs_ids[:50]  # Limit for performance
                )
                
                for contra in contradictions:
                    self.contradiction_detector.store_contradiction(contra)
        
        return memory_id
    
    def ingest_text_with_extraction(
        self,
        text: str,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
        extraction: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Ingest a single text into memory with pre-extracted entities/relations.
        
        Returns:
            memory_id of created memory
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        if memory_id is None:
            memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        
        # Step 1: Generate embedding
        embedding = self.embedder.embed_single(text)
        
        # Step 2: Use pre-extracted or extract
        if extraction is None:
            extraction = self.extractor.extract_entities_and_relations(text)
        
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])
        temporal = extraction.get("temporal", {})
        importance = extraction.get("importance", 0.5)
        
        valid_from = temporal.get("valid_from", 0)
        valid_until = temporal.get("valid_until", 2**31 - 1)
        
        # Step 3: Collect entity IDs
        entity_ids = [e["id"] for e in entities]
        
        # Step 4: Upsert to vector store
        self.vector_store.upsert_memory(
            memory_id=memory_id,
            text=text,
            embedding=embedding,
            entity_ids=entity_ids,
            valid_from=valid_from,
            valid_until=valid_until,
            importance=importance,
            memory_type="semantic",
            metadata=metadata,
            timestamp=timestamp
        )
        
        # Step 5: Upsert entities to graph
        for entity in entities:
            self.graph_store.upsert_entity(
                entity_id=entity["id"],
                name=entity["name"],
                entity_type=entity["type"],
                description=entity.get("description", ""),
                importance=importance,
                timestamp=timestamp
            )
        
        # Step 6: Upsert relations to graph
        for rel in relations:
            self.graph_store.upsert_relation(
                from_id=rel["from"],
                to_id=rel["to"],
                relation_type=rel["type"],
                confidence=rel.get("confidence", 0.5),
                valid_from=valid_from,
                valid_until=valid_until,
                timestamp=timestamp
            )
        
        # Step 7: Create observations for each entity
        for entity in entities:
            obs_id = f"obs_{memory_id}_{entity['id']}"
            self.graph_store.upsert_observation(
                obs_id=obs_id,
                entity_id=entity["id"],
                content=text,
                embedding=embedding.tolist(),
                valid_from=valid_from,
                valid_until=valid_until,
                importance=importance,
                source="ingestion",
                timestamp=timestamp
            )
        
        # Step 8: Contradiction detection
        if self.contradiction_detector and entity_ids:
            # Get existing observations for these entities
            existing_obs_ids = []
            for eid in entity_ids:
                obs_list = self.graph_store.get_observations(eid, valid_at=timestamp, limit=20)
                existing_obs_ids.extend([o["id"] for o in obs_list])
            
            # Remove self
            existing_obs_ids = [oid for oid in existing_obs_ids if oid != memory_id]
            
            if existing_obs_ids:
                contradictions = self.contradiction_detector.detect_contradictions(
                    new_obs_id=memory_id,
                    new_content=text,
                    new_entity_ids=entity_ids,
                    candidate_obs_ids=existing_obs_ids[:50]  # Limit for performance
                )
                
                for contra in contradictions:
                    self.contradiction_detector.store_contradiction(contra)
        
        return memory_id
    
    def ingest_batch(
        self,
        texts: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[int] = None
    ) -> List[str]:
        """Ingest multiple texts."""
        if metadata_list is None:
            metadata_list = [None] * len(texts)
        
        memory_ids = []
        for text, metadata in zip(texts, metadata_list):
            mem_id = self.ingest_text(text, metadata=metadata, timestamp=timestamp)
            memory_ids.append(mem_id)
        
        return memory_ids
    
    def ingest_from_file(
        self,
        file_path: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[str]:
        """Ingest text from file with chunking."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Simple chunking (can be enhanced with langchain text splitter)
        chunks = self._chunk_text(content, chunk_size, chunk_overlap)
        
        return self.ingest_batch(chunks)
    
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Simple text chunking."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period > start:
                    end = last_period + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks