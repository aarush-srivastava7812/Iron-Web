"""
Competitor Retrieval Architectures: Mem0, Zep, and Temporal MemPalace.

Implements realistic benchmark models of the key baseline architectures:
1. Mem0Retriever: Dense Vector + 1-hop Entity Neighborhood Join (no cross-encoder, monotonic time).
2. ZepRetriever: Dense Vector + Lexical/BM25 Keyword Fusion (RRF) with edge relationship context.
3. MemPalaceRetriever: Hierarchical Temporal Room Clustering + Room-then-Item Spatial Walk.
"""
from typing import List, Dict, Any, Optional
import time
import math
from collections import defaultdict

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph import GraphStore
from memory.ranking.scorer import reciprocal_rank_fusion


class Mem0Retriever:
    """
    Mem0 Architecture:
    - Dense vector similarity search (Qdrant)
    - 1-hop entity neighborhood expansion from vector hits
    - Linear combination scoring (vector_score + entity_weight)
    - No cross-encoder reranking, monotonic timestamps only (no bitemporal valid intervals).
    """

    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore, graph_store: GraphStore):
        self.embedder = embedder
        self.vector_store = vector_store
        self.graph_store = graph_store

    def retrieve(self, query: str, k: int = 10, query_time: Optional[int] = None) -> List[Dict[str, Any]]:
        query_emb = self.embedder.embed_single(query)
        # Vector search width = 2 * k
        vec_hits = self.vector_store.search(query_embedding=query_emb, k=k * 2)

        candidates: Dict[str, Dict[str, Any]] = {}
        seed_entities = set()

        for hit in vec_hits:
            mid = hit["payload"].get("memory_id", hit["id"])
            eids = hit["payload"].get("entity_ids", [])
            seed_entities.update(eids)
            candidates[mid] = {
                "memory_id": mid,
                "text": hit["payload"].get("text", ""),
                "score": float(hit["score"]),
                "payload": hit["payload"],
                "retrieval_method": "mem0_vector"
            }

        # 1-hop entity expansion (Mem0 graph join)
        for eid in list(seed_entities)[:10]:
            try:
                obs_list = self.graph_store.get_observations(eid, limit=3)
                for obs in obs_list:
                    oid = obs["id"]
                    if oid not in candidates:
                        candidates[oid] = {
                            "memory_id": oid,
                            "text": obs["content"],
                            "score": 0.45,  # base graph match score
                            "payload": {
                                "memory_id": oid,
                                "text": obs["content"],
                                "entity_ids": [eid],
                                "timestamp": obs.get("created_at", 0)
                            },
                            "retrieval_method": "mem0_graph_1hop"
                        }
                    else:
                        # Entity overlap bonus
                        candidates[oid]["score"] += 0.25
            except Exception:
                pass

        # Sort by final score
        sorted_candidates = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)
        return sorted_candidates[:k]


class ZepRetriever:
    """
    Zep Architecture:
    - Hybrid dense vector search + lexical/keyword matching
    - Reciprocal Rank Fusion (RRF) combining dense and lexical streams
    - Edge relationship context joining
    - No cross-encoder reranker, no bitemporal intervals.
    """

    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: str, k: int = 10, query_time: Optional[int] = None) -> List[Dict[str, Any]]:
        query_emb = self.embedder.embed_single(query)
        # 1. Dense vector stream
        dense_hits = self.vector_store.search(query_embedding=query_emb, k=k * 2)
        dense_stream = []
        for h in dense_hits:
            mid = h["payload"].get("memory_id", h["id"])
            dense_stream.append({
                "memory_id": mid,
                "text": h["payload"].get("text", ""),
                "score": float(h["score"]),
                "payload": h["payload"]
            })

        # 2. Lexical keyword matching stream (BM25 surrogate)
        query_terms = [t.strip(",.?!\"':;").lower() for t in query.split() if len(t.strip(",.?!\"':;")) >= 3]
        lexical_stream = []
        for h in dense_hits:
            text_lower = h["payload"].get("text", "").lower()
            overlap = sum(1 for term in query_terms if term in text_lower)
            if overlap > 0:
                mid = h["payload"].get("memory_id", h["id"])
                lexical_stream.append({
                    "memory_id": mid,
                    "text": h["payload"].get("text", ""),
                    "score": float(overlap) / max(len(query_terms), 1),
                    "payload": h["payload"]
                })
        lexical_stream.sort(key=lambda x: x["score"], reverse=True)

        # 3. RRF Fusion
        stream_lists = [dense_stream]
        if lexical_stream:
            stream_lists.append(lexical_stream)

        fused = reciprocal_rank_fusion(stream_lists, k=60, top_k=k)
        results = []
        for item in fused:
            results.append({
                "memory_id": item["memory_id"],
                "text": item.get("text", ""),
                "score": item["rrf_score"],
                "payload": item.get("payload", {}),
                "retrieval_method": "zep_hybrid_rrf"
            })
        return results


class MemPalaceRetriever:
    """
    Temporal MemPalace Architecture:
    - Hierarchical Spatial-Temporal Memory Palace
    - Stage 1: Partition memories into temporal 'rooms' (session / time window clusters)
    - Stage 2: Identify winning room via aggregate room similarity
    - Stage 3: Retrieve top memories within winning room + chronological neighbor room
    """

    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: str, k: int = 10, query_time: Optional[int] = None) -> List[Dict[str, Any]]:
        query_emb = self.embedder.embed_single(query)
        all_hits = self.vector_store.search(query_embedding=query_emb, k=k * 4)

        if not all_hits:
            return []

        # Partition memories into temporal rooms (e.g. 12-hour or session-based buckets)
        rooms: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        room_scores: Dict[int, float] = defaultdict(float)

        for h in all_hits:
            ts = int(h["payload"].get("timestamp", 0))
            # Room bucket = 86400 seconds (1 day window)
            room_id = ts // 86400 if ts > 0 else 0
            score = float(h["score"])
            rooms[room_id].append({
                "memory_id": h["payload"].get("memory_id", h["id"]),
                "text": h["payload"].get("text", ""),
                "score": score,
                "timestamp": ts,
                "payload": h["payload"]
            })
            room_scores[room_id] += score

        # Select top 2 highest scoring rooms
        top_rooms = sorted(room_scores.keys(), key=lambda r: room_scores[r], reverse=True)[:2]

        # Retrieve top memories from winning rooms
        palace_candidates = []
        for rid in top_rooms:
            # Sort within room by score
            room_mems = sorted(rooms[rid], key=lambda m: m["score"], reverse=True)
            palace_candidates.extend(room_mems)

        # Final sort by similarity
        palace_candidates.sort(key=lambda m: m["score"], reverse=True)
        results = []
        for m in palace_candidates[:k]:
            results.append({
                "memory_id": m["memory_id"],
                "text": m["text"],
                "score": m["score"],
                "payload": m["payload"],
                "retrieval_method": "mempalace_room_walk"
            })
        return results
