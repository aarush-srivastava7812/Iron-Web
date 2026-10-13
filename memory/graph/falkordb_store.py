"""
FalkorDB graph store for structural memory (entities, relations, observations).
Service-backed storage with isolated graph publication and shared graph leases.
"""

import os
from typing import List, Dict, Any, Optional
from functools import wraps


def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.write_lock:
            return method(self, *args, **kwargs)

    return call


class FalkorDBGraphStore:
    """
    FalkorDB named graph for memory graph.
    Schema: Entities, Relations, Observations with temporal validity.
    """

    def __init__(
        self,
        graph_name="iron_web",
        host=None,
        port=None,
        username=None,
        password=None,
        ssl=None,
        socket_timeout=10.0,
        query_timeout_ms=10000,
    ):
        from falkordb import FalkorDB
        import re
        from memory.graph.connection import GraphConnection, GraphLease

        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", graph_name):
            raise ValueError(
                "Graph name must contain 1-128 letters, digits, dots, underscores, colons or hyphens."
            )
        self.graph_name = graph_name
        self.host = host or os.getenv("FALKORDB_HOST", "127.0.0.1")
        self.port = int(
            port if port is not None else os.getenv("FALKORDB_PORT", "6379")
        )
        self.db = FalkorDB(
            host=self.host,
            port=self.port,
            username=username or os.getenv("FALKORDB_USERNAME"),
            password=password or os.getenv("FALKORDB_PASSWORD"),
            ssl=ssl
            if ssl is not None
            else os.getenv("FALKORDB_TLS", "false").lower() == "true",
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_timeout,
            ssl_check_hostname=True,
        )
        self.redis = self.db.connection
        self.redis.ping()
        self.result_limit = int(self.db.config_get("RESULTSET_SIZE"))
        self.graph = self.db.select_graph(graph_name)
        self.conn = GraphConnection(self)
        self.lock_key = "{" + graph_name + "}:lock"
        self.revision_key = "{" + graph_name + "}:revision"
        self.write_lock = GraphLease(self.redis, self.lock_key)
        self.query_timeout_ms = query_timeout_ms
        self.socket_timeout = socket_timeout
        self._entity_name_index = None
        self._index_revision = None
        self._conflict_cache = None
        self._conflict_revision = None
        self._staging = None
        self._backup = None
        self._published = False
        self._closed = False
        try:
            with self.write_lock:
                self._create_schema()
        except Exception:
            self.db.close()
            raise

    def invalidate_entity_name_index(self) -> None:
        """Discard the in-process entity lookup index after graph mutation."""
        self._entity_name_index = None
        self._conflict_cache = None
        self._conflict_revision = None

    @synchronized
    def get_entity_name_index(self):
        revision = self.redis.get(self.revision_key)
        if self._entity_name_index is None or revision != self._index_revision:
            result = self.conn.execute("MATCH (e:Entity) RETURN e.id, e.name")
            self._entity_name_index = [
                (str(row[0]).strip(), str(row[1]).strip()) for row in result.rows
            ]
            self._index_revision = revision
        return self._entity_name_index

    def _create_schema(self):
        # Native ID constraints retain primary-key uniqueness/non-null behavior.
        # Shared graph leases also serialize compound read/modify operations.
        existing = {
            (row[0], property_name)
            for row in self.graph.query(
                "CALL db.indexes() YIELD label, properties RETURN label, properties"
            ).result_set
            for property_name in row[1]
        }
        for label, property_name in (
            ("Entity", "id"),
            ("Entity", "name"),
            ("Observation", "id"),
            ("Observation", "source_memory_id"),
        ):
            if (label, property_name) not in existing:
                self.graph.query(
                    f"CREATE INDEX FOR (n:{label}) ON (n.{property_name})",
                    timeout=self.query_timeout_ms,
                )
        existing_constraints = {
            (row[0], row[1], tuple(row[2]), row[3])
            for row in self.graph.query("CALL db.constraints()").result_set
        }
        for label in ("Entity", "Observation"):
            for kind in ("UNIQUE", "MANDATORY"):
                if (kind, label, ("id",), "NODE") not in existing_constraints:
                    method = (
                        self.graph.create_node_unique_constraint
                        if kind == "UNIQUE"
                        else self.graph.create_node_mandatory_constraint
                    )
                    method(label, "id")
        import time

        deadline = time.monotonic() + self.socket_timeout
        while True:
            constraints = self.graph.query("CALL db.constraints()").result_set
            required = [
                row
                for row in constraints
                if row[1] in {"Entity", "Observation"}
                and row[2] == ["id"]
                and row[0] in {"UNIQUE", "MANDATORY"}
            ]
            if len(required) == 4 and all(row[4] == "OPERATIONAL" for row in required):
                break
            if (
                any(row[4] == "FAILED" for row in required)
                or time.monotonic() >= deadline
            ):
                raise RuntimeError(
                    "FalkorDB identifier constraints could not be verified."
                )
            time.sleep(0.01)

    # === Entity Operations ===

    @synchronized
    def upsert_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        description: str = "",
        importance: float = 1.0,
        timestamp: Optional[int] = None,
    ) -> str:
        """Upsert an entity."""
        import time

        if timestamp is None:
            timestamp = int(time.time())

        # Check if exists
        result = self.conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.id", {"id": entity_id}
        )

        if result.has_next():
            # Update the existing entity fields.
            query = """
                MATCH (e:Entity {id: $id})
                SET e.name = $name, e.entity_type = $etype, e.description = $description,
                    e.importance = $imp, e.updated_at = $ts
            """
            self.conn.execute(
                query,
                {
                    "id": entity_id,
                    "name": name,
                    "etype": entity_type,
                    "description": description,
                    "imp": float(importance),
                    "ts": timestamp,
                },
            )
        else:
            query = """
                CREATE (e:Entity {id: $id, name: $name, entity_type: $etype,
                    description: $description, importance: $imp,
                    created_at: $ts, updated_at: $ts2})
            """
            self.conn.execute(
                query,
                {
                    "id": entity_id,
                    "name": name,
                    "etype": entity_type,
                    "description": description,
                    "imp": float(importance),
                    "ts": timestamp,
                    "ts2": timestamp,
                },
            )
        self.invalidate_entity_name_index()
        return entity_id

    @synchronized
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        result = self.conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.id, e.name, e.entity_type, e.description, e.importance, e.created_at, e.updated_at",
            {"id": entity_id},
        )
        if result.has_next():
            row = result.get_next()
            return {
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "description": row[3],
                "importance": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
        return None

    @synchronized
    def get_entities(self, entity_ids):
        """Read seeds in bounded batches, preserving first occurrence order."""
        ids = list(dict.fromkeys(entity_ids))
        fields = (
            "id",
            "name",
            "entity_type",
            "description",
            "importance",
            "created_at",
            "updated_at",
        )
        entities = {}
        for start in range(0, len(ids), 100):
            result = self.conn.execute(
                "MATCH (e:Entity) WHERE e.id IN $ids RETURN "
                + ", ".join("e." + field for field in fields),
                {"ids": ids[start : start + 100]},
            )
            for row in result.rows:
                entities[row[0]] = dict(zip(fields, row))
        return [entities[eid] for eid in ids if eid in entities]

    @synchronized
    def find_entities_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find entities by name (fuzzy match)."""
        result = self.conn.execute(
            """
            MATCH (e:Entity)
            WHERE e.name CONTAINS $name
            RETURN e.id, e.name, e.entity_type, e.description, e.importance, e.created_at, e.updated_at
            ORDER BY e.importance DESC
            LIMIT $limit
        """,
            {"name": name, "limit": limit},
        )

        entities = []
        while result.has_next():
            row = result.get_next()
            entities.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "entity_type": row[2],
                    "description": row[3],
                    "importance": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                }
            )
        return entities

    @synchronized
    def delete_entity(self, entity_id: str, force: bool = False) -> bool:
        """
        Delete an entity by ID, preserving referential integrity unless force=True.

        Args:
            entity_id: Entity identifier
            force: If True, delete even if observations still reference this entity

        Returns:
            True if deleted, False if not found or referenced by observations (when force=False)
        """
        check = self.conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.id", {"id": entity_id}
        )
        if not check.has_next():
            return False

        if not force:
            obs_check = self.conn.execute(
                "MATCH (o:Observation)-[:ABOUT]->(e:Entity {id: $id}) RETURN count(o)",
                {"id": entity_id},
            )
            if obs_check.has_next():
                row = obs_check.get_next()
                if row[0] > 0:
                    return False

        self.conn.execute(
            "MATCH (e:Entity {id: $id}) DETACH DELETE e", {"id": entity_id}
        )
        self.invalidate_entity_name_index()
        return True

    # === Relation Operations ===

    @synchronized
    def upsert_relation(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
        confidence: float = 1.0,
        valid_from: int = 0,
        valid_until: int = 2**63 - 1,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
    ) -> bool:
        """Version relationships by interval and provenance rather than overwriting history."""
        import time
        import json
        import math

        if (
            valid_from > valid_until
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("Invalid relationship validity or confidence.")
        if self.get_entity(from_id) is None or self.get_entity(to_id) is None:
            raise ValueError("Both relationship endpoints must exist.")
        timestamp = int(time.time()) if timestamp is None else timestamp
        meta = json.dumps(metadata or {}, sort_keys=True, allow_nan=False)
        parameters = dict(
            source=from_id,
            target=to_id,
            kind=relation_type,
            confidence=confidence,
            vf=valid_from,
            vu=valid_until,
            timestamp=timestamp,
            metadata=meta,
        )
        result = self.conn.execute(
            """
            MATCH (a:Entity {id: $source})-[r:RELATES]->(b:Entity {id: $target})
            WHERE r.relation_type = $kind AND r.valid_from = $vf AND r.valid_until = $vu AND r.metadata = $metadata
            RETURN r.relation_type
        """,
            {
                k: parameters[k]
                for k in ("source", "target", "kind", "vf", "vu", "metadata")
            },
        )
        if result.has_next():
            self.conn.execute(
                """
                MATCH (a:Entity {id: $source})-[r:RELATES]->(b:Entity {id: $target})
                WHERE r.relation_type = $kind AND r.valid_from = $vf AND r.valid_until = $vu AND r.metadata = $metadata
                SET r.confidence = $confidence, r.updated_at = $timestamp
            """,
                parameters,
            )
        else:
            self.conn.execute(
                """
                MATCH (a:Entity {id: $source}), (b:Entity {id: $target})
                CREATE (a)-[:RELATES {relation_type: $kind, confidence: $confidence, valid_from: $vf,
                    valid_until: $vu, created_at: $timestamp, updated_at: $timestamp, metadata: $metadata}]->(b)
            """,
                parameters,
            )
        return True

    @synchronized
    def get_relations(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both",  # "out", "in", "both"
        valid_at: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get relations for an entity."""
        import time

        if valid_at is None:
            valid_at = int(time.time())

        if direction == "out":
            pattern = "(a:Entity {id: $id})-[r:RELATES]->(b:Entity)"
        elif direction == "in":
            pattern = "(a:Entity)-[r:RELATES]->(b:Entity {id: $id})"
        else:
            pattern = "(a:Entity {id: $id})-[r:RELATES]-(b:Entity)"

        where_clause = "WHERE r.valid_from <= $time AND r.valid_until >= $time"
        if relation_type:
            where_clause += " AND r.relation_type = $rel_type"

        query = f"""
            MATCH {pattern}
            {where_clause}
            RETURN a.id as from_id, b.id as to_id, r.relation_type, r.confidence, r.valid_from, r.valid_until, r.created_at, r.updated_at, r.metadata
            ORDER BY r.confidence DESC
        """

        params = {"id": entity_id, "time": valid_at}
        if relation_type:
            params["rel_type"] = relation_type

        result = self.conn.execute(query, params)

        relations = []
        while result.has_next():
            row = result.get_next()
            # Projected fields: [from_id, to_id, relation_type, confidence, valid_from, valid_until, created_at, updated_at, metadata]
            relations.append(
                {
                    "from_id": row[0],
                    "to_id": row[1],
                    "relation_type": row[2],
                    "confidence": row[3],
                    "valid_from": row[4],
                    "valid_until": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                    "metadata": row[8],
                }
            )
        return relations

    # === Observation Operations ===

    @synchronized
    def upsert_observation(
        self,
        obs_id: str,
        entity_id: str,
        content: str,
        embedding: Optional[List[float]] = None,
        valid_from: int = 0,
        valid_until: int = 2**63 - 1,
        importance: float = 1.0,
        source: str = "user",
        timestamp: Optional[int] = None,
        source_memory_id: Optional[str] = None,
    ) -> str:
        """Upsert an observation (fact about entity)."""
        import time
        import json

        if timestamp is None:
            timestamp = int(time.time())

        emb_str = json.dumps(embedding) if embedding else "[]"
        previous = self.get_observation(obs_id)
        src_mem = source_memory_id or (previous or {}).get("source_memory_id", "")
        if not src_mem and obs_id.startswith("obs_"):
            suffix = "_" + entity_id
            src_mem = (
                obs_id[4 : -len(suffix)] if obs_id.endswith(suffix) else obs_id[4:]
            )

        # Check if exists
        result = self.conn.execute(
            "MATCH (o:Observation {id: $id}) RETURN o.id", {"id": obs_id}
        )

        if result.has_next():
            if embedding is not None:
                self.conn.execute(
                    """
                    MATCH (o:Observation {id: $id})
                    SET o.content = $content, o.embedding = $emb, o.valid_from = $vf,
                        o.valid_until = $vu, o.importance = $imp, o.source = $src,
                        o.source_memory_id = $src_mem
                """,
                    {
                        "id": obs_id,
                        "content": content,
                        "emb": emb_str,
                        "vf": valid_from,
                        "vu": valid_until,
                        "imp": importance,
                        "src": source,
                        "src_mem": src_mem,
                    },
                )
            else:
                self.conn.execute(
                    """
                    MATCH (o:Observation {id: $id})
                    SET o.content = $content, o.valid_from = $vf,
                        o.valid_until = $vu, o.importance = $imp, o.source = $src,
                        o.source_memory_id = $src_mem
                """,
                    {
                        "id": obs_id,
                        "content": content,
                        "vf": valid_from,
                        "vu": valid_until,
                        "imp": importance,
                        "src": source,
                        "src_mem": src_mem,
                    },
                )
        else:
            self.conn.execute(
                """
                CREATE (o:Observation {
                    id: $id, entity_id: $eid, content: $content, embedding: $emb,
                    valid_from: $vf, valid_until: $vu, importance: $imp,
                    source: $src, created_at: $ts, source_memory_id: $src_mem
                })
            """,
                {
                    "id": obs_id,
                    "eid": entity_id,
                    "content": content,
                    "emb": emb_str,
                    "vf": valid_from,
                    "vu": valid_until,
                    "imp": importance,
                    "src": source,
                    "ts": timestamp,
                    "src_mem": src_mem,
                },
            )

        # Link to entity
        self.conn.execute(
            """
            MATCH (o:Observation {id: $oid}), (e:Entity {id: $eid})
            MERGE (o)-[:ABOUT {relevance: 1.0}]->(e)
        """,
            {"oid": obs_id, "eid": entity_id},
        )

        return obs_id

    @synchronized
    def get_observations(
        self,
        entity_id: str,
        valid_at: Optional[int] = None,
        limit: int = 50,
        temporal_mode: str = "now",
        memory_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get observations for an entity."""
        import time

        if valid_at is None:
            valid_at = int(time.time())

        if temporal_mode not in {"now", "historical", "auto"} or limit < 1:
            raise ValueError("Invalid observation query.")
        predicate = {
            "now": "WHERE o.valid_from <= $time AND o.valid_until >= $time",
            "historical": "WHERE o.valid_until < $time",
            "auto": "",
        }[temporal_mode]
        time_parameter = {"time": valid_at} if predicate else {}
        scope_parameter = {"memory_ids": memory_ids} if memory_ids is not None else {}
        if memory_ids is not None:
            predicate += (
                " AND " if predicate else "WHERE "
            ) + "o.source_memory_id IN $memory_ids"
        result = self.conn.execute(
            f"""
            MATCH (o:Observation)-[:ABOUT]->(e:Entity {{id: $eid}})
            {predicate}
            RETURN o.id, o.entity_id, o.content, o.embedding, o.valid_from,
                   o.valid_until, o.importance, o.source, o.created_at, o.source_memory_id
            ORDER BY o.importance DESC
            LIMIT $limit
        """,
            {"eid": entity_id, "limit": limit, **time_parameter, **scope_parameter},
        )

        obs = []
        while result.has_next():
            row = result.get_next()
            # Projected fields: [id, entity_id, content, embedding, valid_from,
            # valid_until, importance, source, created_at, source_memory_id]
            obs_dict = {
                "id": row[0],
                "entity_id": row[1],
                "content": row[2],
                "embedding": row[3],
                "valid_from": row[4],
                "valid_until": row[5],
                "importance": row[6],
                "source": row[7],
                "created_at": row[8],
                "source_memory_id": row[9] if len(row) > 9 else "",
            }
            # Parse embedding if present
            if obs_dict["embedding"]:
                import json

                try:
                    obs_dict["embedding"] = json.loads(obs_dict["embedding"])
                except Exception:
                    obs_dict["embedding"] = []
            obs.append(obs_dict)
        return obs

    @synchronized
    def get_observation(self, obs_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an observation by ID.

        Args:
            obs_id: Observation identifier

        Returns:
            Observation dictionary or None if not found
        """
        import json

        result = self.conn.execute(
            """
            MATCH (o:Observation {id: $id})
            RETURN o.id, o.entity_id, o.content, o.embedding, o.valid_from, o.valid_until, o.importance, o.source, o.created_at, o.source_memory_id
        """,
            {"id": obs_id},
        )

        if not result.has_next():
            return None

        row = result.get_next()
        obs_dict = {
            "id": row[0],
            "entity_id": row[1],
            "content": row[2],
            "embedding": row[3],
            "valid_from": row[4],
            "valid_until": row[5],
            "importance": row[6],
            "source": row[7],
            "created_at": row[8],
            "source_memory_id": row[9] if len(row) > 9 else "",
        }
        if obs_dict["embedding"]:
            try:
                obs_dict["embedding"] = json.loads(obs_dict["embedding"])
            except Exception:
                obs_dict["embedding"] = []
        return obs_dict

    @synchronized
    def delete_observation(self, obs_id: str) -> bool:
        """
        Delete an observation by ID, detaching any edges (ABOUT, CONTRADICTS, SUPERSEDES).

        Args:
            obs_id: Observation identifier

        Returns:
            True if deleted, False if not found
        """
        check = self.conn.execute(
            "MATCH (o:Observation {id: $id}) RETURN o.id", {"id": obs_id}
        )
        if not check.has_next():
            return False

        self.conn.execute(
            "MATCH (o:Observation {id: $id}) DETACH DELETE o", {"id": obs_id}
        )
        return True

    @synchronized
    def get_memory_observations(self, memory_id: str) -> List[Dict[str, Any]]:
        """Find exact ownership, including the original observation naming scheme."""
        result = self.conn.execute(
            """
            MATCH (o:Observation)
            WHERE o.source_memory_id = $mid OR
                ((o.source_memory_id IS NULL OR o.source_memory_id = '') AND
                 (o.id = $mid OR o.id = 'obs_' + $mid OR
                  o.id = 'obs_' + $mid + '_' + o.entity_id))
            RETURN o.id
        """,
            {"mid": memory_id},
        )
        ids = []
        while result.has_next():
            ids.append(result.get_next()[0])
        return [self.get_observation(oid) for oid in ids]

    @synchronized
    def get_memory_relations(self, memory_id):
        """Read attributed relationships without inferring ownership from entity names."""
        import json

        result = self.conn.execute("""
            MATCH (a:Entity)-[r:RELATES]->(b:Entity)
            RETURN a.id, b.id, r.relation_type, r.confidence, r.valid_from, r.valid_until, r.metadata
        """)
        relations = []
        while result.has_next():
            source, target, kind, confidence, start, end, raw = result.get_next()
            try:
                metadata = json.loads(raw or "{}")
            except ValueError:
                continue
            if (
                isinstance(metadata, dict)
                and metadata.get("source_memory_id") == memory_id
            ):
                relations.append(
                    dict(
                        from_id=source,
                        to_id=target,
                        relation_type=kind,
                        confidence=confidence,
                        valid_from=start,
                        valid_until=end,
                        metadata=metadata,
                    )
                )
        return relations

    @synchronized
    def delete_memory(
        self, memory_id: str, clean_orphaned_entities: bool = False
    ) -> bool:
        """
        Delete all observations and graph components associated with a memory ID.

        Args:
            memory_id: Memory identifier
            clean_orphaned_entities: If True, remove entities that no longer have any observations

        Returns:
            True if one or more observations were deleted, False if none found
        """
        import json

        relation_result = self.conn.execute(
            "MATCH ()-[r:RELATES]->() RETURN DISTINCT r.metadata"
        )
        owned_metadata = []
        while relation_result.has_next():
            value = relation_result.get_next()[0]
            if value:
                try:
                    owner = json.loads(value).get("source_memory_id")
                except (ValueError, AttributeError):
                    continue  # Legacy unstructured relationship metadata cannot establish ownership.
                if owner == memory_id:
                    owned_metadata.append(value)
        for value in owned_metadata:
            self.conn.execute(
                "MATCH ()-[r:RELATES]->() WHERE r.metadata = $metadata DELETE r",
                {"metadata": value},
            )
        observations = self.get_memory_observations(memory_id)
        matched_obs_ids = [obs["id"] for obs in observations]
        referenced_entity_ids = {
            obs["entity_id"] for obs in observations if obs["entity_id"]
        }

        if not matched_obs_ids:
            return bool(owned_metadata)

        for oid in matched_obs_ids:
            self.conn.execute(
                "MATCH (o:Observation {id: $id}) DETACH DELETE o", {"id": oid}
            )

        if clean_orphaned_entities:
            for eid in referenced_entity_ids:
                rem = self.conn.execute(
                    "MATCH (o:Observation)-[:ABOUT]->(e:Entity {id: $id}) RETURN count(o)",
                    {"id": eid},
                )
                if rem.has_next() and rem.get_next()[0] == 0:
                    self.conn.execute(
                        "MATCH (e:Entity {id: $id}) DETACH DELETE e", {"id": eid}
                    )
            self.invalidate_entity_name_index()

        return True

    # === Graph Expansion (1-2 hop) ===

    @synchronized
    def expand_graph(
        self,
        seed_entity_ids,
        hops=2,
        relation_types=None,
        valid_at=None,
        include_relations=True,
        max_nodes=50,
        temporal_mode="now",
    ):
        """Bounded breadth-first expansion includes seeds and every depth up to two."""
        import time

        if (
            hops not in (1, 2)
            or max_nodes < 1
            or temporal_mode not in {"now", "historical", "auto"}
        ):
            raise ValueError("Invalid graph expansion settings.")
        if not seed_entity_ids:
            return [], []
        now = int(time.time()) if valid_at is None else valid_at
        entities = {
            entity["id"]: entity
            for entity in self.get_entities(
                list(dict.fromkeys(seed_entity_ids))[:max_nodes]
            )
        }
        frontier, relations = list(entities), {}
        predicate = {
            "now": "AND r.valid_from <= $time AND r.valid_until >= $time",
            "historical": "AND r.valid_until < $time",
            "auto": "",
        }[temporal_mode]
        types = "AND r.relation_type IN $types" if relation_types else ""
        for _ in range(hops):
            if not frontier:
                break
            result = self.conn.execute(
                f"""
                MATCH (e:Entity)-[r:RELATES]-(n:Entity)
                WHERE e.id IN $ids {predicate} {types}
                RETURN n.id, n.name, n.entity_type, n.description, n.importance, n.created_at, n.updated_at,
                       e.id, r.relation_type, r.confidence, r.valid_from, r.valid_until, r.created_at, r.updated_at, r.metadata
                ORDER BY n.id LIMIT $limit
            """,
                {
                    "ids": frontier,
                    "limit": max_nodes * 4,
                    **({"time": now} if predicate else {}),
                    **({"types": relation_types} if relation_types else {}),
                },
            )
            next_frontier = []
            while result.has_next():
                row = result.get_next()
                eid = row[0]
                if eid not in entities:
                    if len(entities) >= max_nodes:
                        continue
                    entities[eid] = dict(
                        zip(
                            (
                                "id",
                                "name",
                                "entity_type",
                                "description",
                                "importance",
                                "created_at",
                                "updated_at",
                            ),
                            row[:7],
                        )
                    )
                    next_frontier.append(eid)
                if include_relations:
                    key = (row[7], eid, row[8])
                    relations[key] = dict(
                        from_id=row[7],
                        to_id=eid,
                        relation_type=row[8],
                        confidence=row[9],
                        valid_from=row[10],
                        valid_until=row[11],
                        created_at=row[12],
                        updated_at=row[13],
                        metadata=row[14],
                    )
            frontier = next_frontier
        return list(entities.values()), list(relations.values())

    # === Contradiction/Supersession ===

    @staticmethod
    def observation_memory_id(observation):
        owner = observation.get("source_memory_id")
        if owner:
            return owner
        oid, eid = observation["id"], observation.get("entity_id", "")
        suffix = "_" + eid
        if oid.startswith("obs_") and eid and oid.endswith(suffix):
            return oid[4 : -len(suffix)]
        return oid[4:] if oid.startswith("obs_") else oid

    def _resolve_obs_id(self, target_id):
        if self.get_observation(target_id):
            return target_id
        observations = self.get_memory_observations(target_id)
        if not observations:
            raise ValueError(f"Unknown observation or memory: {target_id}")
        return sorted(o["id"] for o in observations)[0]

    @synchronized
    def get_relationship_conflicts_batch(
        self, observation_ids, use_batched_resolution=True
    ):
        """Resolve every observation for each owner, retaining edge direction and time."""
        from copy import deepcopy

        original_ids = list(dict.fromkeys(observation_ids))
        if not original_ids:
            return {}
        revision = (self.graph.name, self.redis.get(self.revision_key))
        if self._conflict_cache is None or revision != self._conflict_revision:
            result = self.conn.execute(
                "MATCH (o:Observation) RETURN o.id, o.entity_id, o.source_memory_id"
            )
            owners = {
                oid: self.observation_memory_id(
                    dict(id=oid, entity_id=eid, source_memory_id=source)
                )
                for oid, eid, source in result.rows
            }
            index = {}
            edge_count = 0
            for kind, time_field, extra in (
                ("CONTRADICTS", "detected_at", "WHERE r.resolved = false"),
                ("SUPERSEDES", "superseded_at", ""),
            ):
                result = self.conn.execute(
                    f"MATCH (old:Observation)-[r:{kind}]->(new:Observation) {extra} "
                    f"RETURN old.id, new.id, r.confidence, r.{time_field}"
                )
                edge_count += len(result.rows)
                for old, new, confidence, effective_at in result.rows:
                    for oid, other, direction in (
                        (old, new, "outgoing"),
                        (new, old, "incoming"),
                    ):
                        item = dict(
                            relationship_type=kind,
                            id=other,
                            memory_id=owners.get(other, other),
                            confidence=confidence,
                            effective_at=effective_at,
                            direction=direction,
                            from_id=old,
                            to_id=new,
                        )
                        for alias in dict.fromkeys((oid, owners.get(oid, oid))):
                            index.setdefault(alias, []).append(item)
            # Bound retained cache size; larger graphs use the same uncached result.
            if len(owners) <= 50000 and edge_count <= 100000:
                self._conflict_cache = index
                self._conflict_revision = revision
        else:
            index = self._conflict_cache
        # Callers attach ranking metadata; never expose mutable cache entries.
        return {mid: deepcopy(index.get(mid, [])) for mid in original_ids}

    @synchronized
    def add_contradiction(
        self,
        obs_id_1: Optional[str] = None,
        obs_id_2: Optional[str] = None,
        confidence: float = 1.0,
        detected_at: Optional[int] = None,
        nature: Optional[str] = None,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
    ):
        """Add contradiction edge between observations."""
        import time

        if detected_at is None:
            detected_at = int(time.time())

        target1 = obs_id_1 or from_id
        target2 = obs_id_2 or to_id
        if not target1 or not target2:
            raise ValueError("Must provide both observation IDs for contradiction.")

        id1 = self._resolve_obs_id(target1)
        id2 = self._resolve_obs_id(target2)

        self.conn.execute(
            """
            MATCH (o1:Observation {id: $id1}), (o2:Observation {id: $id2})
            MERGE (o1)-[c:CONTRADICTS {confidence: $conf, detected_at: $det, resolved: false}]->(o2)
        """,
            {"id1": id1, "id2": id2, "conf": confidence, "det": detected_at},
        )

    record_contradiction = add_contradiction

    @synchronized
    def add_supersession(
        self,
        old_obs_id: str,
        new_obs_id: str,
        confidence: float,
        reason: str = "",
        superseded_at: Optional[int] = None,
    ):
        """Add supersession edge (old -> new)."""
        import time

        if superseded_at is None:
            superseded_at = int(time.time())

        old_obs_id = self._resolve_obs_id(old_obs_id)
        new_obs_id = self._resolve_obs_id(new_obs_id)
        self.conn.execute(
            """
            MATCH (old:Observation {id: $old}), (new:Observation {id: $new})
            MERGE (old)-[s:SUPERSEDES {confidence: $conf, superseded_at: $ts, reason: $reason}]->(new)
        """,
            {
                "old": old_obs_id,
                "new": new_obs_id,
                "conf": confidence,
                "ts": superseded_at,
                "reason": reason,
            },
        )

    @synchronized
    def get_contradictions(self, obs_id: str) -> List[Dict[str, Any]]:
        """Get contradictions for an observation."""
        real_id = self._resolve_obs_id(obs_id)
        result = self.conn.execute(
            """
            MATCH (o:Observation {id: $id})-[c:CONTRADICTS]-(other:Observation)
            RETURN other.id, other.entity_id, other.content, c.confidence, c.detected_at, c.resolved
        """,
            {"id": real_id},
        )

        contra = []
        while result.has_next():
            row = result.get_next()
            contra.append(
                {
                    "id": row[0],
                    "entity_id": row[1],
                    "content": row[2],
                    "confidence": row[3],
                    "detected_at": row[4],
                    "resolved": row[5],
                }
            )
        return contra

    @synchronized
    def get_supersessions(self, obs_id: str) -> List[Dict[str, Any]]:
        """Get supersession chain for an observation."""
        real_id = self._resolve_obs_id(obs_id)
        result = self.conn.execute(
            """
            MATCH (o:Observation {id: $id})-[s:SUPERSEDES]->(new:Observation)
            RETURN new.id, new.entity_id, new.content, s.confidence, s.reason, s.superseded_at, 'SUPERSEDED_BY' as direction
            UNION
            MATCH (old:Observation)-[s:SUPERSEDES]->(o:Observation {id: $id})
            RETURN old.id, old.entity_id, old.content, s.confidence, s.reason, s.superseded_at, 'SUPERSEDES' as direction
        """,
            {"id": real_id},
        )

        supers = []
        while result.has_next():
            row = result.get_next()
            supers.append(
                {
                    "id": row[0],
                    "entity_id": row[1],
                    "content": row[2],
                    "confidence": row[3],
                    "reason": row[4],
                    "superseded_at": row[5],
                    "from_id": real_id if row[6] == "SUPERSEDED_BY" else row[0],
                    "to_id": row[0] if row[6] == "SUPERSEDED_BY" else real_id,
                    "direction": row[6],
                }
            )
        return supers

    # === Utility ===

    @synchronized
    def get_node_counts(self):
        """Report real counts; query failures propagate rather than becoming zeros."""
        return {
            table: self.conn.execute(f"MATCH (n:{table}) RETURN count(n)").get_next()[0]
            for table in ("Entity", "Observation")
        }

    @synchronized
    def get_edge_counts(self):
        return {
            table: self.conn.execute(
                f"MATCH ()-[r:{table}]->() RETURN count(r)"
            ).get_next()[0]
            for table in ("RELATES", "ABOUT", "CONTRADICTS", "SUPERSEDES")
        }

    def execute(self, query, params=None):
        import re
        from memory.graph.connection import GraphResult, parameterized

        with self.write_lock:
            if self._closed:
                raise RuntimeError("FalkorDB graph store is closed.")
            self.write_lock.assert_owned()
            result = self.graph.query(
                parameterized(query, params or {}), timeout=self.query_timeout_ms
            )
            if re.search(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP)\b", query, re.I):
                self.invalidate_entity_name_index()
                if self._staging is None:
                    self.redis.incr(self.revision_key)
            if self.result_limit >= 0 and len(result.result_set) >= self.result_limit:
                raise RuntimeError(
                    "FalkorDB result limit reached; complete results cannot be verified. "
                    "Configure RESULTSET_SIZE -1 and reconnect."
                )
            return GraphResult(
                result.result_set, [column[1] for column in result.header]
            )

    def begin(self):
        import uuid

        self.write_lock.assert_owned()
        if self._staging is not None:
            raise RuntimeError("Nested graph transactions are unsupported.")
        staging = "{" + self.graph_name + "}:staging:" + uuid.uuid4().hex
        self.graph.copy(staging)
        self._staging = staging
        self._backup = staging.replace(":staging:", ":rollback:")
        self._base_revision = int(self.redis.get(self.revision_key) or 0)
        self._published = False
        self.graph = self.db.select_graph(staging)

    def commit(self):
        if self._staging is None:
            raise RuntimeError("No graph transaction is active.")
        self.write_lock.assert_owned()
        staging = self._staging
        # Verify the lease and switch the complete graph in one Redis operation.
        # No live graph query is partially overwritten by a failed application write.
        self.redis.eval(
            """
            if redis.call('GET', KEYS[1]) ~= ARGV[1] then
                return redis.error_reply('Graph lease lost before publication')
            end
            if redis.call('EXISTS', KEYS[2]) == 0 then
                return redis.error_reply('Staging graph is missing')
            end
            if tonumber(redis.call('GET', KEYS[4]) or '0') ~= tonumber(ARGV[2]) then
                return redis.error_reply('Graph revision changed before publication')
            end
            if redis.call('EXISTS', KEYS[5]) ~= 0 then
                return redis.error_reply('Rollback graph already exists')
            end
            redis.call('SET', KEYS[6], ARGV[3])
            redis.call('RENAME', KEYS[3], KEYS[5])
            redis.call('RENAME', KEYS[2], KEYS[3])
            redis.call('INCR', KEYS[4])
            return 1
        """,
            6,
            self.lock_key,
            staging,
            self.graph_name,
            self.revision_key,
            self._backup,
            "{" + self.graph_name + "}:publication",
            self.write_lock.token,
            self._base_revision,
            staging,
        )
        self._published = True
        self.graph = self.db.select_graph(self.graph_name)
        self.invalidate_entity_name_index()

    def rollback(self):
        if self._staging is None:
            return
        staging = self._staging
        if self._backup and self.redis.exists(self._backup):
            self.write_lock.assert_owned()
            self.redis.eval(
                """
                if redis.call('GET', KEYS[1]) ~= ARGV[1] then
                    return redis.error_reply('Graph lease lost before recovery')
                end
                if redis.call('GET', KEYS[4]) ~= ARGV[2] then
                    return redis.error_reply('A newer graph publication prevents recovery')
                end
                if tonumber(redis.call('GET', KEYS[5]) or '0') > tonumber(ARGV[3]) + 1 then
                    return redis.error_reply('A newer graph write prevents recovery')
                end
                redis.call('RENAME', KEYS[2], KEYS[3])
                redis.call('INCR', KEYS[5])
                return 1
            """,
                5,
                self.lock_key,
                self._backup,
                self.graph_name,
                "{" + self.graph_name + "}:publication",
                self.revision_key,
                self.write_lock.token,
                staging,
                self._base_revision,
            )
        elif not self.redis.exists(staging):
            raise RuntimeError(
                "No staging or recovery graph exists; rollback cannot be verified."
            )
        if self.redis.exists(staging):
            self.db.select_graph(staging).delete()
        self._staging = None
        self._backup = None
        self._published = False
        self.graph = self.db.select_graph(self.graph_name)
        self.invalidate_entity_name_index()

    def finish(self):
        """Release a confirmed transaction's recovery copy after both stores commit."""
        import logging

        if self._backup:
            try:
                if self.redis.exists(self._backup):
                    self.db.select_graph(self._backup).delete()
            except Exception:
                # Published data is intact; keep the recovery copy on the server
                # if cleanup is unavailable instead of fabricating a write failure.
                logging.getLogger(__name__).warning(
                    "FalkorDB recovery-copy cleanup failed; copy retained."
                )
        self._staging = None
        self._backup = None
        self._published = False

    def close(self):
        if self._closed:
            return
        with self.write_lock:
            if self._staging is not None:
                if self._published:
                    self.finish()
                else:
                    self.rollback()
            self._closed = True
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Relation type constants
class RelationType:
    USES = "USES"
    PREFERS = "PREFERS"
    SUPERSEDES = "SUPERSEDES"
    CONTRADICTS = "CONTRADICTS"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    HAS_SKILL = "HAS_SKILL"
    AVOIDS = "AVOIDS"
    LEARNED = "LEARNED"
