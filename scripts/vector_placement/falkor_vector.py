"""Experiment-only vector-store adapter for the unchanged MemoryEngine.

Uses a native cosine index on MemoryVector nodes in an isolated graph. FalkorDB
4.20.7 returns cosine DISTANCE: convert to similarity before the existing scorer.
Only the temporal/document filters used by the application are supported. Unknown
filters fail explicitly. Adaptive overfetch preserves post-filter candidate budgets.
This is not exposed through production configuration or offered as a full backend.
"""

from copy import deepcopy
import json
import time
import uuid

import numpy as np

from memory.schema import validate_metadata
from memory.vector_store.qdrant_store import MEMORY_NAMESPACE


class FalkorVectorExperiment:
    def __init__(self, graph_store, dimension=384, embedder=None):
        if not graph_store.graph_name.startswith(("vector_bench_", "test_vector_bench_")):
            raise ValueError("Vector experiment requires an isolated vector_bench_ graph.")
        self.graph_store = graph_store
        self.dimension = dimension
        self._embedder = embedder
        self._size = 0
        self.last_overfetch = 0
        graph_store.execute("CREATE INDEX FOR (n:MemoryVector) ON (n.id)")
        graph_store.execute(
            "CREATE VECTOR INDEX FOR (n:MemoryVector) ON (n.embedding) "
            f"OPTIONS {{dimension:{int(dimension)}, similarityFunction:'cosine', "
            "M:16, efConstruction:200, efRuntime:100}"
        )

    def _vector(self, value, normalize=False):
        vector = np.asarray(value, dtype=np.float32)
        if vector.shape != (self.dimension,) or not np.isfinite(vector).all():
            raise ValueError("Invalid embedding dimensions or non-finite values.")
        if not np.linalg.norm(vector):
            raise ValueError("Cosine search requires a nonzero vector.")
        if normalize:
            vector = vector / np.linalg.norm(vector)
        return vector.tolist()

    @staticmethod
    def _uuid(memory_id):
        return str(uuid.uuid5(MEMORY_NAMESPACE, memory_id))

    def load_points(self, points):
        """Copy identical stored vectors/payloads, outside measured query runs."""
        if self.count():
            raise ValueError("Bulk loading requires an empty experimental vector store.")
        rows = []
        for point in points:
            payload = deepcopy(point.payload)
            rows.append(dict(
                id=payload["memory_id"], payload=json.dumps(payload, allow_nan=False),
                vector=self._vector(point.vector), valid_from=payload["valid_from"],
                valid_until=payload["valid_until"],
            ))
        if len({r["id"] for r in rows}) != len(rows):
            raise ValueError("Duplicate logical memory IDs in input.")
        for start in range(0, len(rows), 100):
            self.graph_store.execute(
                "UNWIND $rows AS row CREATE (n:MemoryVector {id:row.id, "
                "payload:row.payload, valid_from:row.valid_from, "
                "valid_until:row.valid_until, embedding:vecf32(row.vector)})",
                {"rows": rows[start:start + 100]},
            )
        self._size = len(rows)

    @staticmethod
    def _filter(condition):
        """Compile supported Qdrant filter semantics into post-index WHERE."""
        if condition is None:
            return "true", {}
        body = condition.model_dump(exclude_none=True)
        if set(body) - {"must"}:
            raise ValueError("Experimental adapter supports must filters only.")
        parts, params = [], {}
        for i, field in enumerate(body.get("must", [])):
            key = field.get("key")
            if key in {"valid_from", "valid_until"} and set(field) == {"key", "range"}:
                for operator, value in field["range"].items():
                    symbol = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">="}.get(operator)
                    if symbol is None:
                        raise ValueError("Unsupported range operator.")
                    name = f"filter_{i}_{operator}"
                    parts.append(f"node.{key} {symbol} ${name}")
                    params[name] = value
            elif key == "memory_id" and set(field) == {"key", "match"} and set(field["match"]) == {"any"}:
                name = f"filter_{i}_ids"
                parts.append(f"node.id IN ${name}")
                params[name] = field["match"]["any"]
            else:
                raise ValueError(f"Unsupported experimental filter: {field!r}")
        return " AND ".join(parts) or "true", params

    def search(self, query_embedding, k=10, filter_condition=None, score_threshold=None):
        if not isinstance(k, int) or k < 1:
            raise ValueError("Result count must be positive.")
        vector = self._vector(query_embedding)
        where, params = self._filter(filter_condition)
        if score_threshold is not None:
            where += " AND (1.0-score) >= $minimum_score"
            params["minimum_score"] = float(score_threshold)
        if self._size == 0:
            return []
        requested = min(k, self._size)
        while True:
            rows = self.graph_store.execute(
                "CALL db.idx.vector.queryNodes('MemoryVector','embedding',$candidate_k,vecf32($vector)) "
                "YIELD node,score WHERE " + where +
                " RETURN node.id,score,node.payload ORDER BY score ASC LIMIT $result_k",
                dict(params, candidate_k=requested, vector=vector, result_k=k),
            ).rows
            self.last_overfetch = requested
            if len(rows) >= k or requested >= self._size:
                break
            requested = min(self._size, requested * 2)
        return [dict(id=self._uuid(row[0]), score=1.0-float(row[1]),
                     payload=json.loads(row[2])) for row in rows]

    def get_memory(self, memory_id):
        rows = self.graph_store.execute(
            "MATCH(n:MemoryVector {id:$id}) RETURN n.payload,n.embedding",
            {"id": memory_id},
        ).rows
        if not rows:
            return None
        return dict(id=self._uuid(memory_id), payload=json.loads(rows[0][0]),
                    vector=np.asarray(rows[0][1], dtype=np.float32).tolist())

    def upsert_memory(self, memory_id, text, embedding=None, entity_ids=None,
                      valid_from=0, valid_until=2**63-1, importance=1.0,
                      memory_type="semantic", metadata=None, timestamp=None):
        validate_metadata(metadata)
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("Memory ID must be nonempty.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Memory content must be nonempty.")
        if valid_from > valid_until or not np.isfinite(importance) or not 0 <= importance <= 1:
            raise ValueError("Invalid validity or importance.")
        if embedding is None:
            if self._embedder is None:
                raise ValueError("Provide a real embedding or an embedder.")
            embedding = self._embedder.embed_single(text)
        payload = dict(memory_id=memory_id, text=text, entity_ids=entity_ids or [],
                       valid_from=valid_from, valid_until=valid_until,
                       importance=importance, memory_type=memory_type,
                       timestamp=int(time.time()) if timestamp is None else timestamp)
        payload.update(deepcopy(metadata or {}))
        existed = self.get_memory(memory_id) is not None
        self.graph_store.execute(
            "MERGE(n:MemoryVector {id:$id}) SET n.payload=$payload, "
            "n.embedding=vecf32($vector),n.valid_from=$valid_from,n.valid_until=$valid_until",
            dict(id=memory_id, payload=json.dumps(payload, allow_nan=False),
                 vector=self._vector(embedding, normalize=True), valid_from=valid_from, valid_until=valid_until),
        )
        if not existed:
            self._size += 1
        return memory_id

    def restore_memory(self, memory_id, snapshot):
        if snapshot is None:
            self.delete_memory(memory_id)
        else:
            payload = snapshot["payload"]
            existed = self.get_memory(memory_id) is not None
            self.graph_store.execute(
                "MERGE(n:MemoryVector {id:$id}) SET n.payload=$payload, "
                "n.embedding=vecf32($vector),n.valid_from=$valid_from,n.valid_until=$valid_until",
                dict(id=memory_id, payload=json.dumps(payload, allow_nan=False),
                     vector=self._vector(snapshot["vector"]), valid_from=payload["valid_from"],
                     valid_until=payload["valid_until"]),
            )
            if not existed:
                self._size += 1
        # Graph rollback may already have restored the vector nodes.
        self._size = self.count()
        actual = self.get_memory(memory_id)
        if snapshot is None:
            if actual is not None:
                raise RuntimeError("Experimental vector rollback failed to remove a record.")
        elif actual is None or actual["payload"] != snapshot["payload"] or not np.allclose(actual["vector"], snapshot["vector"]):
            raise RuntimeError("Experimental vector rollback verification failed.")

    def delete_memory(self, memory_id):
        existed = self.get_memory(memory_id) is not None
        self.graph_store.execute("MATCH(n:MemoryVector {id:$id}) DELETE n", {"id":memory_id})
        if existed:
            self._size -= 1
        return existed

    def count(self):
        return int(self.graph_store.execute("MATCH(n:MemoryVector) RETURN count(n)").rows[0][0])

    def close(self):
        """The caller owns the graph store; closing this adapter never deletes it."""
