"""
Maintenance operations: decay, deduplication, consolidation.
Production-ready background jobs for memory health, idempotency, and cross-store consistency.
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import numpy as np
import time
import uuid
from sklearn.cluster import DBSCAN

from memory.embeddings.embedder import Embedder
from memory.vector_store.qdrant_store import QdrantVectorStore
from memory.graph import KuzuGraphStore, GraphStore


class MemoryDecay:
    """
    Importance decay over time.
    Calculates age-based exponential decay and synchronizes importance across
    Qdrant points and Kùzu graph observations.
    """
    
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: GraphStore,
        half_life_days: float = 90.0,
        min_importance: float = 0.1
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.half_life_days = half_life_days
        self.min_importance = min_importance
    
    def compute_decayed_importance(
        self,
        initial_importance: float,
        timestamp: int,
        current_time: Optional[int] = None
    ) -> float:
        """
        Compute decayed importance based on memory creation timestamp and half-life.
        Idempotent: consistently computed from creation timestamp.
        """
        if current_time is None:
            current_time = int(time.time())
        
        age_seconds = current_time - timestamp
        age_days = max(0.0, age_seconds / 86400.0)
        
        decay_factor = float(np.exp(-age_days / self.half_life_days))
        decayed = initial_importance * decay_factor
        return float(max(decayed, self.min_importance))
    
    def apply_decay(
        self,
        batch_size: int = 100,
        current_time: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Apply decay to all stored memories in Qdrant and Kùzu.
        
        Returns:
            Real telemetry statistics about processed, decayed, and skipped memories.
        """
        now = int(time.time()) if current_time is None else current_time
        stats = {
            "processed": 0,
            "decayed": 0,
            "unchanged": 0,
            "errors": 0,
            "dry_run": dry_run,
            "avg_importance_before": 0.0,
            "avg_importance_after": 0.0
        }
        
        # 1. Scroll through all points in vector store
        records = []
        offset = None
        while True:
            batch, next_offset = self.vector_store.scroll(
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True
            )
            records.extend(batch)
            if next_offset is None or len(batch) == 0:
                break
            offset = next_offset
            
        if not records:
            return stats
            
        stats["processed"] = len(records)
        importances_before = []
        importances_after = []
        
        for record in records:
            payload = record.payload or {}
            mem_id = payload.get("memory_id")
            if not mem_id:
                continue
                
            current_importance = float(payload.get("importance", 1.0))
            importances_before.append(current_importance)
            
            # Idempotency safeguard: read initial_importance if recorded, else treat current as baseline
            initial_importance = float(payload.get("initial_importance", current_importance))
            ts = int(payload.get("timestamp", now))
            
            new_importance = self.compute_decayed_importance(
                initial_importance=initial_importance,
                timestamp=ts,
                current_time=now
            )
            importances_after.append(new_importance)
            
            if abs(new_importance - current_importance) > 1e-4:
                stats["decayed"] += 1
                if not dry_run:
                    try:
                        # Update Qdrant
                        updated_payload = dict(payload)
                        updated_payload["importance"] = new_importance
                        updated_payload["initial_importance"] = initial_importance
                        updated_payload["last_decay_time"] = now
                        
                        self.vector_store.upsert_memory(
                            memory_id=mem_id,
                            text=payload.get("text", ""),
                            embedding=np.array(record.vector, dtype=np.float32) if record.vector is not None else None,
                            entity_ids=payload.get("entity_ids", []),
                            valid_from=payload.get("valid_from", 0),
                            valid_until=payload.get("valid_until", 2**31 - 1),
                            importance=new_importance,
                            metadata={k: v for k, v in updated_payload.items() if k not in {
                                "text", "memory_id", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"
                            }},
                            timestamp=ts
                        )
                        
                        # Update corresponding observations in Kùzu
                        entity_ids = payload.get("entity_ids", [])
                        if entity_ids:
                            for eid in entity_ids:
                                obs_id = f"obs_{mem_id}_{eid}"
                                self.graph_store.upsert_observation(
                                    obs_id=obs_id,
                                    entity_id=eid,
                                    content=payload.get("text", ""),
                                    valid_from=payload.get("valid_from", 0),
                                    valid_until=payload.get("valid_until", 2**31 - 1),
                                    importance=new_importance,
                                    timestamp=ts
                                )
                        else:
                            self.graph_store.upsert_observation(
                                obs_id=f"obs_{mem_id}",
                                entity_id=mem_id,
                                content=payload.get("text", ""),
                                valid_from=payload.get("valid_from", 0),
                                valid_until=payload.get("valid_until", 2**31 - 1),
                                importance=new_importance,
                                timestamp=ts
                            )
                    except Exception:
                        stats["errors"] += 1
            else:
                stats["unchanged"] += 1
                
        if importances_before:
            stats["avg_importance_before"] = float(np.mean(importances_before))
            stats["avg_importance_after"] = float(np.mean(importances_after))
            
        return stats


class MemoryDeduplication:
    """
    Semantic deduplication using embedding clustering (DBSCAN) with safety
    guards preventing the accidental merging of distinct or contradictory facts.
    """
    
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: GraphStore,
        embedder: Embedder,
        eps: float = 0.15,  # Cosine distance threshold (~0.85 cosine similarity)
        min_samples: int = 2
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.embedder = embedder
        self.eps = eps
        self.min_samples = min_samples
    
    def find_duplicates(
        self,
        memory_ids: List[str],
        embeddings: np.ndarray,
        payloads: Optional[List[Dict[str, Any]]] = None
    ) -> List[List[str]]:
        """
        Find duplicate candidate clusters using DBSCAN with safeguards.
        
        Safeguards:
        1. Temporal disjointness: Memories with non-overlapping validity bounds are distinct facts.
        2. Graph contradictions: Contradictory statements must NOT be merged into a single fact.
        """
        if len(memory_ids) < 2 or len(embeddings) < 2:
            return []
            
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric="cosine"
        ).fit(embeddings)
        
        labels = clustering.labels_
        raw_clusters: Dict[int, List[int]] = {}
        for idx, label in enumerate(labels):
            if label >= 0:
                if label not in raw_clusters:
                    raw_clusters[label] = []
                raw_clusters[label].append(idx)
                
        valid_clusters: List[List[str]] = []
        payload_map = payloads or [{}] * len(memory_ids)
        
        for cluster_indices in raw_clusters.values():
            if len(cluster_indices) < 2:
                continue
                
            # Filter cluster members against safeguards
            safe_members = []
            for i in cluster_indices:
                p_i = payload_map[i]
                vf_i = p_i.get("valid_from", 0)
                vu_i = p_i.get("valid_until", 2**31 - 1)
                
                is_safe = True
                for existing_idx in safe_members:
                    p_e = payload_map[existing_idx]
                    vf_e = p_e.get("valid_from", 0)
                    vu_e = p_e.get("valid_until", 2**31 - 1)
                    
                    # Safeguard 1: Temporal disjointness check
                    if vu_i < vf_e or vu_e < vf_i:
                        # Non-overlapping validity intervals represent distinct historical facts
                        is_safe = False
                        break
                        
                    # Safeguard 2: Explicit contradiction check in graph
                    m_i_id = memory_ids[i]
                    m_e_id = memory_ids[existing_idx]
                    try:
                        p_i_eids = payload_map[i].get("entity_ids", [])
                        p_e_eids = payload_map[existing_idx].get("entity_ids", [])
                        obs_i_candidates = [m_i_id, f"obs_{m_i_id}"] + [f"obs_{m_i_id}_{eid}" for eid in p_i_eids]
                        obs_e_candidates = set([m_e_id, f"obs_{m_e_id}"] + [f"obs_{m_e_id}_{eid}" for eid in p_e_eids])
                        
                        has_contra = False
                        for oid_i in obs_i_candidates:
                            contra = self.graph_store.get_contradictions(oid_i)
                            if any(c.get("id") in obs_e_candidates or m_e_id in str(c.get("id", "")) for c in contra):
                                has_contra = True
                                break
                        if has_contra:
                            is_safe = False
                            break
                    except Exception:
                        pass
                        
                if is_safe:
                    safe_members.append(i)
                    
            if len(safe_members) > 1:
                valid_clusters.append([memory_ids[idx] for idx in safe_members])
                
        return valid_clusters
    
    def merge_duplicates(
        self,
        duplicate_clusters: List[List[str]],
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Merge duplicate memories in each cluster.
        Preserves canonical memory with merged entity IDs and cleans duplicates across stores.
        """
        stats = {
            "clusters_processed": 0,
            "memories_merged": 0,
            "canonical_memories": 0
        }
        
        for cluster in duplicate_clusters:
            stats["clusters_processed"] += 1
            
            # Fetch memories
            memories = []
            for mem_id in cluster:
                point = self.vector_store.get_memory(mem_id)
                if point:
                    memories.append(point)
                    
            if len(memories) < 2:
                continue
                
            # Select canonical: highest importance, then latest timestamp
            canonical = max(
                memories,
                key=lambda m: (m["payload"].get("importance", 0.0), m["payload"].get("timestamp", 0))
            )
            canonical_id = canonical["payload"]["memory_id"]
            
            # Merge entity IDs and metadata
            merged_entity_ids = set()
            merged_meta = {}
            for m in memories:
                merged_entity_ids.update(m["payload"].get("entity_ids", []))
                for k, v in m["payload"].items():
                    if k not in {"text", "memory_id", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"}:
                        merged_meta[k] = v
                        
            merged_meta["merged_from"] = [m["payload"]["memory_id"] for m in memories if m["payload"]["memory_id"] != canonical_id]
            merged_meta["merged_at"] = int(time.time())
            
            if not dry_run:
                # 1. Update canonical memory in Qdrant
                self.vector_store.upsert_memory(
                    memory_id=canonical_id,
                    text=canonical["payload"]["text"],
                    embedding=np.array(canonical["vector"], dtype=np.float32) if canonical.get("vector") is not None else None,
                    entity_ids=list(merged_entity_ids),
                    valid_from=canonical["payload"].get("valid_from", 0),
                    valid_until=canonical["payload"].get("valid_until", 2**31 - 1),
                    importance=canonical["payload"].get("importance", 1.0),
                    metadata=merged_meta,
                    timestamp=canonical["payload"].get("timestamp", int(time.time()))
                )
                
                # 2. Remove duplicate memories across Qdrant and Kùzu
                for m in memories:
                    dup_id = m["payload"]["memory_id"]
                    if dup_id != canonical_id:
                        self.vector_store.delete_memory(dup_id)
                        self.graph_store.delete_memory(dup_id, clean_orphaned_entities=False)
                        stats["memories_merged"] += 1
                        
            stats["canonical_memories"] += 1
            
        return stats
    
    def run_deduplication(
        self,
        limit: int = 1000,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run full deduplication pipeline scanning vector store."""
        records = []
        offset = None
        while len(records) < limit:
            batch, next_offset = self.vector_store.scroll(
                limit=min(100, limit - len(records)),
                offset=offset,
                with_payload=True,
                with_vectors=True
            )
            records.extend(batch)
            if next_offset is None or len(batch) == 0:
                break
            offset = next_offset
            
        stats = {
            "scanned": len(records),
            "clusters_found": 0,
            "merged": 0,
            "dry_run": dry_run
        }
        
        if len(records) < 2:
            return stats
            
        memory_ids = [r.payload.get("memory_id") for r in records if r.payload and r.payload.get("memory_id")]
        embeddings = np.array([r.vector for r in records if r.payload and r.payload.get("memory_id")], dtype=np.float32)
        payloads = [r.payload for r in records if r.payload and r.payload.get("memory_id")]
        
        clusters = self.find_duplicates(memory_ids, embeddings, payloads)
        stats["clusters_found"] = len(clusters)
        
        if clusters:
            merge_stats = self.merge_duplicates(clusters, dry_run=dry_run)
            stats["merged"] = merge_stats["memories_merged"]
            
        return stats


class MemoryConsolidation:
    """
    Procedural consolidation: synthesizes recurring patterns and skills from
    episodic memories with source traceability.
    """
    
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: GraphStore,
        extractor: Optional[Any],
        embedder: Embedder,
        window_days: int = 30,
        min_episodes: int = 3
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.extractor = extractor
        self.embedder = embedder
        self.window_days = window_days
        self.min_episodes = min_episodes
    
    def consolidate_window(
        self,
        start_time: int,
        end_time: int,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Consolidate memories in a time window into procedural patterns with source traceability.
        """
        stats = {
            "episodes_processed": 0,
            "skills_extracted": 0,
            "patterns_stored": 0,
            "dry_run": dry_run
        }
        
        # Scroll memories
        records = []
        offset = None
        while True:
            batch, next_offset = self.vector_store.scroll(limit=100, offset=offset, with_payload=True)
            records.extend(batch)
            if next_offset is None or len(batch) == 0:
                break
            offset = next_offset
            
        # Filter memories in window
        window_episodes = []
        for r in records:
            p = r.payload or {}
            ts = p.get("timestamp", 0)
            if start_time <= ts <= end_time:
                window_episodes.append({
                    "id": p.get("memory_id"),
                    "text": p.get("text", ""),
                    "entity_ids": p.get("entity_ids", [])
                })
                
        stats["episodes_processed"] = len(window_episodes)
        if len(window_episodes) < self.min_episodes:
            return stats
            
        texts = [ep["text"] for ep in window_episodes if ep["text"]]
        skills = self.extract_skill_patterns(texts)
        stats["skills_extracted"] = len(skills)
        
        if not dry_run:
            source_ids = [ep["id"] for ep in window_episodes if ep.get("id")]
            for skill in skills:
                skill["provenance"] = {
                    "source_memory_ids": source_ids,
                    "window_start": start_time,
                    "window_end": end_time,
                    "episode_count": len(window_episodes)
                }
                self.store_skill(skill, dry_run=False)
                stats["patterns_stored"] += 1
                
        return stats
    
    def extract_skill_patterns(self, episode_texts: List[str]) -> List[Dict[str, Any]]:
        """Extract skills using extractor or heuristic keyword analysis."""
        if self.extractor and hasattr(self.extractor, "extract_skills"):
            try:
                res = self.extractor.extract_skills(episode_texts)
                if res:
                    return res
            except Exception:
                pass
                
        # Heuristic procedural pattern extraction fallback
        skills = []
        combined_text = " ".join(episode_texts).lower()
        
        # Detect recurring technology/workflow patterns
        patterns = [
            ("python_development", "Python Development Workflow", ["python", "pip", "pytest", "code"]),
            ("java_dsa", "Java DSA & Algorithms Practice", ["java", "dsa", "algorithm", "data structure"]),
            ("data_pipeline", "Data Pipeline Engineering", ["pipeline", "etl", "data", "processing"]),
            ("web_development", "Web Application Development", ["web", "api", "frontend", "backend"])
        ]
        
        for skill_key, skill_name, triggers in patterns:
            matched_count = sum(1 for trig in triggers if trig in combined_text)
            if matched_count >= 2:
                skills.append({
                    "name": skill_name,
                    "description": f"Consolidated workflow pattern for {skill_name} from {len(episode_texts)} episodes.",
                    "conditions": f"Active work involving {triggers[0]}",
                    "actions": f"Apply standard {skill_name} best practices."
                })
                
        if not skills and episode_texts:
            skills.append({
                "name": "General Workflow Pattern",
                "description": f"Synthesized procedural memory from {len(episode_texts)} recorded interaction episodes.",
                "conditions": "Standard operational context",
                "actions": "Reference episodic history for consistent actions."
            })
            
        return skills
    
    def store_skill(self, skill: Dict[str, Any], dry_run: bool = False) -> str:
        """Store extracted skill as procedural memory with provenance."""
        skill_id = f"skill_{uuid.uuid4().hex[:8]}"
        text = f"Procedural Skill: {skill['name']}. {skill['description']}"
        embedding = self.embedder.embed_single(text)
        
        if not dry_run:
            self.vector_store.upsert_memory(
                memory_id=skill_id,
                text=text,
                embedding=embedding,
                entity_ids=[],
                importance=0.9,
                memory_type="procedural",
                metadata={"skill_data": skill, "provenance": skill.get("provenance", {})}
            )
            
            # Upsert into Kùzu as Entity of type Skill
            self.graph_store.upsert_entity(
                entity_id=skill_id,
                name=skill["name"],
                entity_type="Skill",
                description=skill["description"],
                importance=0.9
            )
            
        return skill_id


class MaintenanceScheduler:
    """Orchestrates all maintenance operations."""
    
    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: GraphStore,
        embedder: Embedder,
        extractor: Optional[Any] = None
    ):
        self.decay = MemoryDecay(vector_store, graph_store)
        self.dedup = MemoryDeduplication(vector_store, graph_store, embedder)
        self.consolidation = MemoryConsolidation(vector_store, graph_store, extractor, embedder)
    
    def run_all(
        self,
        dry_run: bool = False,
        tasks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run requested maintenance tasks."""
        tasks = tasks or ["decay", "dedup", "consolidate"]
        results = {}
        
        if "decay" in tasks:
            results["decay"] = self.decay.apply_decay(dry_run=dry_run)
        
        if "dedup" in tasks:
            results["dedup"] = self.dedup.run_deduplication(dry_run=dry_run)
        
        if "consolidate" in tasks:
            current_time = int(time.time())
            window_start = current_time - (self.consolidation.window_days * 86400)
            results["consolidate"] = self.consolidation.consolidate_window(
                window_start, current_time + 300, dry_run=dry_run
            )
        
        return results


# Backward compatibility alias
MaintenanceManager = MaintenanceScheduler