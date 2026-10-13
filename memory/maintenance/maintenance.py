"""
Maintenance operations: decay, deduplication, consolidation.
Explicit maintenance with verified rollback and source provenance.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import numpy as np
import time
import hashlib
import json
from memory.storage import coordinated_write

from memory.embeddings.embedder import Embedder
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.vector_store.qdrant_store import QdrantVectorStore
    from memory.graph import FalkorDBGraphStore


class MemoryDecay:
    """
    Importance decay over time.
    Calculates age-based exponential decay and synchronizes importance across
    Qdrant points and FalkorDB graph observations.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: FalkorDBGraphStore,
        half_life_days: float = 90.0,
        min_importance: float = 0.1,
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        if half_life_days <= 0 or not 0 <= min_importance <= 1:
            raise ValueError("Invalid decay settings.")
        self.half_life_days = half_life_days
        self.min_importance = min_importance

    def compute_decayed_importance(
        self,
        initial_importance: float,
        timestamp: int,
        current_time: Optional[int] = None,
    ) -> float:
        """
        Compute decayed importance based on memory creation timestamp and half-life.
        Idempotent: consistently computed from creation timestamp.
        """
        if current_time is None:
            current_time = int(time.time())

        age_seconds = current_time - timestamp
        age_days = max(0.0, age_seconds / 86400.0)

        decay_factor = float(2 ** (-age_days / self.half_life_days))
        decayed = initial_importance * decay_factor
        return float(max(decayed, self.min_importance))

    def apply_decay(
        self,
        batch_size: int = 100,
        current_time: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply decay to all stored memories in Qdrant and FalkorDB.

        Returns:
            Real telemetry statistics about processed, decayed, and skipped memories.
        """
        if batch_size < 1:
            raise ValueError("Batch size must be positive.")
        now = int(time.time()) if current_time is None else current_time
        stats = {
            "processed": 0,
            "decayed": 0,
            "unchanged": 0,
            "errors": 0,
            "dry_run": dry_run,
            "avg_importance_before": 0.0,
            "avg_importance_after": 0.0,
        }

        # 1. Scroll through all points in vector store
        records = []
        offset = None
        while True:
            batch, next_offset = self.vector_store.scroll(
                limit=batch_size, offset=offset, with_payload=True, with_vectors=True
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
            initial_importance = float(
                payload.get("initial_importance", current_importance)
            )
            ts = int(payload.get("timestamp", now))

            new_importance = self.compute_decayed_importance(
                initial_importance=initial_importance, timestamp=ts, current_time=now
            )
            importances_after.append(new_importance)

            if abs(new_importance - current_importance) > 1e-4:
                stats["decayed"] += 1
                if not dry_run:
                    try:
                        with coordinated_write(
                            self.vector_store, self.graph_store, [mem_id]
                        ):
                            metadata = {
                                k: v
                                for k, v in payload.items()
                                if k
                                not in {
                                    "memory_id",
                                    "text",
                                    "entity_ids",
                                    "valid_from",
                                    "valid_until",
                                    "importance",
                                    "timestamp",
                                }
                            }
                            metadata["initial_importance"] = initial_importance
                            self.vector_store.upsert_memory(
                                mem_id,
                                payload["text"],
                                np.array(record.vector),
                                payload.get("entity_ids", []),
                                payload.get("valid_from", 0),
                                payload.get("valid_until", 2**63 - 1),
                                new_importance,
                                metadata=metadata,
                                timestamp=ts,
                            )
                            for observation in self.graph_store.get_memory_observations(
                                mem_id
                            ):
                                self.graph_store.conn.execute(
                                    "MATCH (o:Observation {id: $id}) SET o.importance = $value",
                                    {"id": observation["id"], "value": new_importance},
                                )
                    except Exception as error:
                        stats["errors"] += 1
                        stats.setdefault("error_details", []).append(
                            {"memory_id": mem_id, "error": str(error)}
                        )
            else:
                stats["unchanged"] += 1

        if importances_before:
            stats["avg_importance_before"] = float(np.mean(importances_before))
            stats["avg_importance_after"] = float(np.mean(importances_after))

        return stats


class MemoryDeduplication:
    """
    Exact-record deduplication with provenance and contradiction safeguards.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: FalkorDBGraphStore,
        embedder: Embedder,
        min_samples: int = 2,
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.embedder = embedder
        if min_samples < 2:
            raise ValueError("Deduplication requires at least two records.")
        self.min_samples = min_samples

    def find_duplicates(
        self,
        memory_ids: List[str],
        embeddings: np.ndarray,
        payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> List[List[str]]:
        """Group identical text, validity and type; similarity never establishes equivalence."""
        if payloads is None or len(payloads) != len(memory_ids):
            raise ValueError("One payload is required per memory ID.")
        groups = {}
        for mid, payload in zip(memory_ids, payloads):
            if payload.get("memory_type", "semantic") != "semantic":
                continue
            relationship_signature = tuple(
                sorted(
                    (
                        r["from_id"],
                        r["to_id"],
                        r["relation_type"],
                        r["valid_from"],
                        r["valid_until"],
                    )
                    for r in self.graph_store.get_memory_relations(mid)
                )
            )
            key = (
                relationship_signature,
                " ".join(payload.get("text", "").split()),
                payload.get("valid_from", 0),
                payload.get("valid_until", 2**63 - 1),
                payload.get("memory_type", "semantic"),
                json.dumps(
                    {
                        key: payload.get(key)
                        for key in ("user_id", "session_id", "benchmark", "sample_id")
                    },
                    sort_keys=True,
                ),
                payload.get("timestamp")
                if payload.get("memory_type") in {"episodic", "procedural"}
                else None,
            )
            if key[1]:
                groups.setdefault(key, []).append(mid)
        clusters = []
        for members in groups.values():
            safe = []
            for mid in members:
                conflicts = self.graph_store.get_relationship_conflicts_batch(
                    [mid]
                ).get(mid, [])
                linked = {c.get("memory_id", c.get("id")) for c in conflicts}
                if not linked.intersection(members):
                    safe.append(mid)
            if len(safe) >= self.min_samples:
                clusters.append(safe)
        return clusters

    def merge_duplicates(
        self, duplicate_clusters: List[List[str]], dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Merge duplicate memories in each cluster.
        Preserves canonical memory with merged entity IDs and cleans duplicates across stores.
        """
        stats = {"clusters_processed": 0, "memories_merged": 0, "canonical_memories": 0}

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
            eligible = self.find_duplicates(
                cluster, None, [m["payload"] for m in memories]
            )
            if not eligible or set(eligible[0]) != set(cluster):
                continue

            # Select canonical: highest importance, then latest timestamp
            canonical = max(
                memories,
                key=lambda m: (
                    m["payload"].get("importance", 0.0),
                    m["payload"].get("timestamp", 0),
                ),
            )
            canonical_id = canonical["payload"]["memory_id"]

            merged_entity_ids = sorted(
                {eid for m in memories for eid in m["payload"].get("entity_ids", [])}
            )
            merged_meta = {
                k: v
                for k, v in canonical["payload"].items()
                if k
                not in {
                    "text",
                    "memory_id",
                    "entity_ids",
                    "valid_from",
                    "valid_until",
                    "importance",
                    "timestamp",
                }
            }
            merged_meta["merged_from"] = sorted(
                set(merged_meta.get("merged_from", []))
                | (set(cluster) - {canonical_id})
            )
            merged_meta["merged_records"] = list(
                merged_meta.get("merged_records", [])
            ) + [
                {
                    "payload": m["payload"],
                    "observations": self.graph_store.get_memory_observations(
                        m["payload"]["memory_id"]
                    ),
                    "relations": self.graph_store.get_memory_relations(
                        m["payload"]["memory_id"]
                    ),
                }
                for m in memories
                if m is not canonical
            ]
            if not dry_run:
                with coordinated_write(self.vector_store, self.graph_store, cluster):
                    # 1. Update canonical memory in Qdrant
                    self.vector_store.upsert_memory(
                        memory_id=canonical_id,
                        text=canonical["payload"]["text"],
                        embedding=np.array(canonical["vector"], dtype=np.float32)
                        if canonical.get("vector") is not None
                        else None,
                        entity_ids=list(merged_entity_ids),
                        valid_from=canonical["payload"].get("valid_from", 0),
                        valid_until=canonical["payload"].get("valid_until", 2**63 - 1),
                        importance=canonical["payload"].get("importance", 1.0),
                        metadata=merged_meta,
                        timestamp=canonical["payload"].get(
                            "timestamp", int(time.time())
                        ),
                    )

                    for eid in merged_entity_ids or [canonical_id]:
                        self.graph_store.upsert_observation(
                            obs_id=f"obs_{canonical_id}_{eid}"
                            if eid != canonical_id
                            else f"obs_{canonical_id}",
                            entity_id=eid,
                            content=canonical["payload"]["text"],
                            embedding=canonical["vector"],
                            valid_from=canonical["payload"].get("valid_from", 0),
                            valid_until=canonical["payload"].get(
                                "valid_until", 2**63 - 1
                            ),
                            importance=canonical["payload"].get("importance", 1),
                            source=canonical["payload"].get("source", "user"),
                            timestamp=canonical["payload"].get("timestamp", 0),
                            source_memory_id=canonical_id,
                        )
                    # 2. Remove duplicate memories across Qdrant and FalkorDB
                    for m in memories:
                        dup_id = m["payload"]["memory_id"]
                        if dup_id != canonical_id:
                            self.vector_store.delete_memory(dup_id)
                            self.graph_store.delete_memory(
                                dup_id, clean_orphaned_entities=False
                            )

            stats["memories_merged"] += len(memories) - 1
            stats["canonical_memories"] += 1

        return stats

    def run_deduplication(
        self, limit: int = 1000, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run full deduplication pipeline scanning vector store."""
        if limit < 1:
            raise ValueError("Scan limit must be positive.")
        records = []
        offset = None
        while len(records) < limit:
            batch, next_offset = self.vector_store.scroll(
                limit=min(100, limit - len(records)),
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            records.extend(batch)
            if next_offset is None or len(batch) == 0:
                break
            offset = next_offset

        stats = {
            "scanned": len(records),
            "clusters_found": 0,
            "merged": 0,
            "dry_run": dry_run,
        }

        if len(records) < 2:
            return stats

        memory_ids = [
            r.payload.get("memory_id")
            for r in records
            if r.payload and r.payload.get("memory_id")
        ]
        embeddings = np.array(
            [r.vector for r in records if r.payload and r.payload.get("memory_id")],
            dtype=np.float32,
        )
        payloads = [
            r.payload for r in records if r.payload and r.payload.get("memory_id")
        ]

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
        graph_store: FalkorDBGraphStore,
        extractor: Optional[Any],
        embedder: Embedder,
        window_days: int = 30,
        min_episodes: int = 3,
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.extractor = extractor
        self.embedder = embedder
        self.window_days = window_days
        self.min_episodes = min_episodes

    def consolidate_window(
        self, start_time: int, end_time: int, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Consolidate memories in a time window into procedural patterns with source traceability.
        """
        stats = {
            "episodes_processed": 0,
            "skills_extracted": 0,
            "patterns_stored": 0,
            "dry_run": dry_run,
        }

        # Scroll memories
        records = []
        offset = None
        while True:
            batch, next_offset = self.vector_store.scroll(
                limit=100, offset=offset, with_payload=True
            )
            records.extend(batch)
            if next_offset is None or len(batch) == 0:
                break
            offset = next_offset

        # Filter memories in window
        window_episodes = []
        for r in records:
            p = r.payload or {}
            ts = p.get("timestamp", 0)
            if p.get("memory_type") == "episodic" and start_time <= ts <= end_time:
                window_episodes.append(
                    {
                        "id": p.get("memory_id"),
                        "text": p.get("text", ""),
                        "entity_ids": p.get("entity_ids", []),
                    }
                )

        stats["episodes_processed"] = len(window_episodes)
        if len(window_episodes) < self.min_episodes:
            return stats

        if dry_run:
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
                    "episode_count": len(window_episodes),
                }
                skill_id = self._skill_id(skill)
                if self.vector_store.get_memory(skill_id) is None:
                    self.store_skill(skill, dry_run=False)
                    stats["patterns_stored"] += 1

        return stats

    def extract_skill_patterns(self, episode_texts: List[str]) -> List[Dict[str, Any]]:
        """Accept explicit extraction; never manufacture generic skills."""
        if not self.extractor or not hasattr(self.extractor, "extract_skills"):
            return []
        skills = self.extractor.extract_skills(episode_texts)
        if not isinstance(skills, list) or any(
            not isinstance(skill, dict)
            or any(
                not isinstance(skill.get(k), str) or not skill[k].strip()
                for k in ("name", "description", "conditions", "actions")
            )
            for skill in skills
        ):
            raise ValueError("Skill extraction returned invalid data.")
        return skills

    @staticmethod
    def _skill_id(skill):
        identity = dict(skill)
        identity["provenance"] = {
            "source_memory_ids": sorted(
                skill.get("provenance", {}).get("source_memory_ids", [])
            )
        }
        return (
            "skill_"
            + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[
                :24
            ]
        )

    def store_skill(self, skill: Dict[str, Any], dry_run: bool = False) -> str:
        """Store extracted skill as procedural memory with provenance."""
        skill_id = self._skill_id(skill)
        text = f"Procedural Skill: {skill['name']}. {skill['description']}. Conditions: {skill['conditions']}. Actions: {skill['actions']}"
        embedder = (
            self.embedder()
            if callable(self.embedder) and not hasattr(self.embedder, "embed_single")
            else self.embedder
        )
        embedding = embedder.embed_single(text)

        if not dry_run:
            with coordinated_write(self.vector_store, self.graph_store, [skill_id]):
                self.vector_store.upsert_memory(
                    memory_id=skill_id,
                    text=text,
                    embedding=embedding,
                    entity_ids=[skill_id],
                    importance=0.9,
                    memory_type="procedural",
                    metadata={
                        "skill_data": skill,
                        "provenance": skill.get("provenance", {}),
                        "source": "consolidation",
                        "extraction_is_mock": bool(
                            getattr(self.extractor, "is_mock", False)
                        ),
                    },
                )

                # Upsert into FalkorDB as Entity of type Skill
                self.graph_store.upsert_entity(
                    entity_id=skill_id,
                    name=skill["name"],
                    entity_type="Skill",
                    description=skill["description"],
                    importance=0.9,
                )

                self.graph_store.upsert_observation(
                    obs_id=f"obs_{skill_id}",
                    entity_id=skill_id,
                    content=text,
                    embedding=embedding.tolist(),
                    importance=0.9,
                    source="consolidation",
                    source_memory_id=skill_id,
                )
        return skill_id


class MaintenanceScheduler:
    """Orchestrates all maintenance operations."""

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        graph_store: FalkorDBGraphStore,
        embedder: Embedder,
        extractor: Optional[Any] = None,
    ):
        self.decay = MemoryDecay(vector_store, graph_store)
        self.dedup = MemoryDeduplication(vector_store, graph_store, embedder)
        self.consolidation = MemoryConsolidation(
            vector_store, graph_store, extractor, embedder
        )

    def run_all(
        self, dry_run: bool = False, tasks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run requested maintenance tasks."""
        tasks = ["decay", "dedup", "consolidate"] if tasks is None else tasks
        if set(tasks) - {"decay", "dedup", "consolidate"}:
            raise ValueError("Unknown maintenance task.")
        results = {}

        if "decay" in tasks:
            results["decay"] = self.decay.apply_decay(dry_run=dry_run)

        if "dedup" in tasks:
            results["dedup"] = self.dedup.run_deduplication(dry_run=dry_run)

        if "consolidate" in tasks:
            current_time = int(time.time())
            window_start = current_time - (self.consolidation.window_days * 86400)
            results["consolidate"] = self.consolidation.consolidate_window(
                window_start, current_time, dry_run=dry_run
            )

        return results


# Backward compatibility alias
