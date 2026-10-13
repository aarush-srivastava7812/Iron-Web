"""
Contradiction and supersession detection for memory consistency.
Uses LLM-as-judge (via NIM) + embedding similarity for detection.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from memory.embeddings.embedder import Embedder
from memory.graph import FalkorDBGraphStore


class ContradictionDetector:
    """
    Detects contradictions between memories using:
    1. Embedding similarity (semantic opposition)
    2. LLM-as-judge (via NIM extractor)
    3. Explicit CONTRADICTS/SUPERSEDES edges in graph
    """

    def __init__(
        self,
        embedder: Embedder,
        graph_store: FalkorDBGraphStore,
        extractor=None,  # NIM extractor for LLM judge
        similarity_threshold: float = 0.85,
        contradiction_threshold: float = 0.3,
    ):
        self.embedder = embedder
        self.graph_store = graph_store
        self.extractor = extractor
        self.similarity_threshold = (
            similarity_threshold  # High similarity = potential contradiction
        )
        self.contradiction_threshold = (
            contradiction_threshold  # Low cosine = contradiction
        )

    def detect_contradictions(
        self,
        new_obs_id: str,
        new_content: str,
        new_entity_ids: List[str],
        candidate_obs_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Detect contradictions between new observation and existing ones.

        Returns list of contradictions with confidence scores.
        """
        contradictions = []

        for cand_id in candidate_obs_ids:
            # Get candidate observation
            cand_obs = self._get_observation(cand_id)
            if not cand_obs:
                continue

            # Check if same entity
            cand_entities = cand_obs.get("entity_ids", [])
            if not set(new_entity_ids) & set(cand_entities):
                continue

            # Check embedding similarity (high similarity but different content = contradiction)
            similarity = self._compute_similarity(
                new_content, cand_obs.get("content", "")
            )

            if similarity > self.similarity_threshold:
                # Semantically similar - check for actual contradiction via LLM
                contradiction = self._llm_judge_contradiction(
                    new_content, cand_obs.get("content", "")
                )

                if contradiction["is_contradiction"]:
                    contradictions.append(
                        {
                            "obs_id_1": new_obs_id,
                            "obs_id_2": cand_id,
                            "confidence": contradiction["confidence"],
                            "type": "contradiction",
                            "reasoning": contradiction["reasoning"],
                            "similarity": similarity,
                        }
                    )

            # Check for supersession (new replaces old)
            elif similarity > 0.6:
                supersession = self._llm_judge_supersession(
                    new_content, cand_obs.get("content", "")
                )

                if supersession["is_supersession"]:
                    contradictions.append(
                        {
                            "obs_id_1": cand_id,  # Old
                            "obs_id_2": new_obs_id,  # New
                            "confidence": supersession["confidence"],
                            "type": "supersession",
                            "reasoning": supersession["reasoning"],
                            "similarity": similarity,
                        }
                    )

        return contradictions

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        emb1 = self.embedder.embed_single(text1)
        emb2 = self.embedder.embed_single(text2)

        return float(
            np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2) + 1e-8)
        )

    def _get_observation(self, obs_id: str) -> Optional[Dict[str, Any]]:
        """Get observation from graph store."""
        if hasattr(self.graph_store, "get_observation"):
            obs = self.graph_store.get_observation(obs_id)
            if obs:
                entity_id = obs.get("entity_id")
                obs["entity_ids"] = [entity_id] if entity_id else []
                return obs
        return None

    def _llm_judge_contradiction(self, text1, text2):
        if self.extractor is None or not hasattr(
            self.extractor, "detect_contradiction"
        ):
            raise ValueError(
                "Contradiction detection requires an explicit compatible extractor."
            )
        return self.extractor.detect_contradiction(text1, text2)

    def _llm_judge_supersession(self, new_text, old_text):
        if self.extractor is None or not hasattr(self.extractor, "detect_supersession"):
            raise ValueError(
                "Supersession detection requires an explicit compatible extractor."
            )
        return self.extractor.detect_supersession(old_text=old_text, new_text=new_text)

    def store_contradiction(self, contradiction: Dict[str, Any]):
        """Store contradiction in graph."""
        if contradiction["type"] == "contradiction":
            self.graph_store.add_contradiction(
                contradiction["obs_id_1"],
                contradiction["obs_id_2"],
                contradiction["confidence"],
            )
        elif contradiction["type"] == "supersession":
            self.graph_store.add_supersession(
                contradiction["obs_id_1"],  # old
                contradiction["obs_id_2"],  # new
                contradiction["confidence"],
                contradiction.get("reasoning", ""),
            )

    def detect_all_contradictions(self) -> List[Dict[str, Any]]:
        """Scan all observations in graph for contradictions."""
        all_contradictions = []

        # Get all observations
        result = self.graph_store.execute(
            "MATCH (o:Observation) RETURN o.id, o.entity_id, o.content, o.embedding, o.valid_from, o.valid_until, o.importance, o.source, o.created_at, o.source_memory_id"
        )
        columns = result.get_column_names()
        observations = []
        while result.has_next():
            row = result.get_next()
            # Convert list row to dict using column names
            obs = dict(zip(columns, row))
            if obs.get("o.embedding"):
                import json

                try:
                    obs["o.embedding"] = json.loads(obs["o.embedding"])
                except Exception:
                    obs["o.embedding"] = []
            observations.append(obs)

        # Compare each pair of observations for same entity
        for i, obs1 in enumerate(observations):
            for obs2 in observations[i + 1 :]:
                # Check if they share entities
                e1_result = self.graph_store.execute(
                    "MATCH (o:Observation {id: $id})-[:ABOUT]->(e:Entity) RETURN e.id",
                    {"id": obs1["o.id"]},
                )
                e1_cols = e1_result.get_column_names()
                e1_entities = []
                while e1_result.has_next():
                    r = e1_result.get_next()
                    r_dict = dict(zip(e1_cols, r))
                    if r_dict.get("e.id"):
                        e1_entities.append(r_dict["e.id"])

                e2_result = self.graph_store.execute(
                    "MATCH (o:Observation {id: $id})-[:ABOUT]->(e:Entity) RETURN e.id",
                    {"id": obs2["o.id"]},
                )
                e2_cols = e2_result.get_column_names()
                e2_entities = []
                while e2_result.has_next():
                    r = e2_result.get_next()
                    r_dict = dict(zip(e2_cols, r))
                    if r_dict.get("e.id"):
                        e2_entities.append(r_dict["e.id"])

                if not set(e1_entities) & set(e2_entities):
                    continue

                # Check embedding similarity
                content1 = obs1.get("o.content", "")
                content2 = obs2.get("o.content", "")

                if not content1 or not content2:
                    continue

                similarity = self._compute_similarity(content1, content2)

                if similarity > self.similarity_threshold:
                    contradiction = self._llm_judge_contradiction(content1, content2)
                    if contradiction["is_contradiction"]:
                        all_contradictions.append(
                            {
                                "obs1_id": obs1["o.id"],
                                "obs2_id": obs2["o.id"],
                                "confidence": contradiction["confidence"],
                                "type": "contradiction",
                                "reasoning": contradiction["reasoning"],
                                "similarity": similarity,
                            }
                        )

        return all_contradictions

    def detect_all_supersessions(self) -> List[Dict[str, Any]]:
        """Scan all observations in graph for supersessions."""
        all_supersessions = []

        # Get all observations
        result = self.graph_store.execute(
            "MATCH (o:Observation) RETURN o.id, o.entity_id, o.content, o.embedding, o.valid_from, o.valid_until, o.importance, o.source, o.created_at, o.source_memory_id"
        )
        columns = result.get_column_names()
        observations = []
        while result.has_next():
            row = result.get_next()
            # Convert list row to dict using column names
            obs = dict(zip(columns, row))
            if obs.get("o.embedding"):
                import json

                try:
                    obs["o.embedding"] = json.loads(obs["o.embedding"])
                except Exception:
                    obs["o.embedding"] = []
            observations.append(obs)

        # Compare each pair of observations for same entity
        for i, obs1 in enumerate(observations):
            for obs2 in observations[i + 1 :]:
                # Check if they share entities
                e1_result = self.graph_store.execute(
                    "MATCH (o:Observation {id: $id})-[:ABOUT]->(e:Entity) RETURN e.id",
                    {"id": obs1["o.id"]},
                )
                e1_cols = e1_result.get_column_names()
                e1_entities = []
                while e1_result.has_next():
                    r = e1_result.get_next()
                    r_dict = dict(zip(e1_cols, r))
                    if r_dict.get("e.id"):
                        e1_entities.append(r_dict["e.id"])

                e2_result = self.graph_store.execute(
                    "MATCH (o:Observation {id: $id})-[:ABOUT]->(e:Entity) RETURN e.id",
                    {"id": obs2["o.id"]},
                )
                e2_cols = e2_result.get_column_names()
                e2_entities = []
                while e2_result.has_next():
                    r = e2_result.get_next()
                    r_dict = dict(zip(e2_cols, r))
                    if r_dict.get("e.id"):
                        e2_entities.append(r_dict["e.id"])

                if not set(e1_entities) & set(e2_entities):
                    continue

                content1 = obs1.get("o.content", "")
                content2 = obs2.get("o.content", "")

                if not content1 or not content2:
                    continue

                similarity = self._compute_similarity(content1, content2)

                if similarity > 0.6:
                    supersession = self._llm_judge_supersession(
                        content2, content1
                    )  # new, old
                    if supersession["is_supersession"]:
                        all_supersessions.append(
                            {
                                "old_id": obs1["o.id"],
                                "new_id": obs2["o.id"],
                                "confidence": supersession["confidence"],
                                "type": "supersession",
                                "reasoning": supersession["reasoning"],
                                "similarity": similarity,
                            }
                        )

        return all_supersessions


class SupersessionResolver:
    """
    Resolves supersession chains to find current valid memory.
    """

    def __init__(self, graph_store: FalkorDBGraphStore):
        self.graph_store = graph_store

    def get_current_version(self, obs_id: str, query_time: int) -> Optional[str]:
        """
        Follow supersession chain to find current version at query_time.
        """
        current_id = obs_id
        visited = set()

        while current_id not in visited:
            visited.add(current_id)
            supers = self.graph_store.get_supersessions(current_id)

            # Find forward supersession (current -> newer)
            # Find backward supersession (older -> current)
            backward = [s for s in supers if s.get("from_id") == current_id]

            # We want forward: current is the OLD one, find NEW
            newer = None
            for s in backward:
                sup_time = s.get("superseded_at", 0)
                if sup_time <= query_time:
                    newer = s.get("to_id") or s.get("id")

            if newer and newer != current_id:
                current_id = newer
            else:
                break

        return current_id if current_id != obs_id else None

    def get_version_chain(self, obs_id: str) -> List[Dict[str, Any]]:
        """Get full supersession chain for an observation."""
        return self.graph_store.get_supersessions(obs_id)
