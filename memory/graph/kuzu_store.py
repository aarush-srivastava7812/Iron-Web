"""
Kuzu graph store for structural memory (entities, relations, observations).
Embedded mode - zero network overhead.
"""

import os
from threading import RLock
from typing import List, Dict, Any, Optional, Tuple
import kuzu


class KuzuGraphStore:
    """
    Kuzu embedded graph database for memory graph.
    Schema: Entities, Relations, Observations with temporal validity.
    """

    def __init__(self, db_path: str = "./data/kuzu/memory.db"):
        """
        Initialize Kuzu graph store.

        Args:
            db_path: Path to Kuzu database file (will be created if doesn't exist)
        """
        self.db_path = db_path
        # Create directory if needed
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        # Initialize database
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self.write_lock = RLock()
        self._entity_name_index: Optional[List[Tuple[str, str]]] = None

        # Create schema
        self._create_schema()

        print(f"Kuzu graph store initialized: {db_path}")

    def invalidate_entity_name_index(self) -> None:
        """Discard the in-process entity lookup index after graph mutation."""
        self._entity_name_index = None

    def get_entity_name_index(self) -> List[Tuple[str, str]]:
        """Return the current entity id/name pairs, cached until a mutation."""
        if self._entity_name_index is None:
            result = self.conn.execute("MATCH (e:Entity) RETURN e.id, e.name")
            index: List[Tuple[str, str]] = []
            while result.has_next():
                row = result.get_next()
                index.append((str(row[0]).strip(), str(row[1]).strip()))
            self._entity_name_index = index
        return self._entity_name_index

    def _create_schema(self):
        """Create graph schema: nodes and relationships."""

        # Entity node table
        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity(
                id STRING,
                name STRING,
                entity_type STRING,
                description STRING,
                importance DOUBLE,
                created_at INT64,
                updated_at INT64,
                PRIMARY KEY (id)
            )
        """)

        # Relation (edge) table
        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS RELATES(
                FROM Entity TO Entity,
                relation_type STRING,
                confidence DOUBLE,
                valid_from INT64,
                valid_until INT64,
                created_at INT64,
                updated_at INT64,
                metadata STRING
            )
        """)

        # Observation node table (facts/claims about entities)
        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Observation(
                id STRING,
                entity_id STRING,
                content STRING,
                embedding STRING,
                valid_from INT64,
                valid_until INT64,
                importance DOUBLE,
                source STRING,
                created_at INT64,
                source_memory_id STRING,
                PRIMARY KEY (id)
            )
        """)
        columns = self.conn.execute("CALL table_info('Observation') RETURN name")
        names = []
        while columns.has_next():
            names.append(columns.get_next()[0])
        if "source_memory_id" not in names:
            self.conn.execute(
                "ALTER TABLE Observation ADD source_memory_id STRING DEFAULT ''"
            )

        # Relation between Observation and Entity
        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS ABOUT(
                FROM Observation TO Entity,
                relevance DOUBLE
            )
        """)

        # Contradiction/Supersession edges
        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS CONTRADICTS(
                FROM Observation TO Observation,
                confidence DOUBLE,
                detected_at INT64,
                resolved BOOLEAN,
                resolution STRING
            )
        """)

        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS SUPERSEDES(
                FROM Observation TO Observation,
                confidence DOUBLE,
                superseded_at INT64,
                reason STRING
            )
        """)

    # === Entity Operations ===

    @staticmethod
    def _cypher_str(value: str) -> str:
        """Render a string as a Cypher string literal (Kuzu rejects both SQL-style
        '' escaping and $param bindings for the reserved property name
        'description', so escaped literals are required for it)."""
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

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
            # Update: parameters everywhere except 'description', which is
            # reserved in Kuzu's parameterized grammar and must be an escaped
            # string literal.
            desc_lit = self._cypher_str(description)
            query = f"""
                MATCH (e:Entity {{id: $id}})
                SET e.name = $name, e.entity_type = $etype, e.description = {desc_lit},
                    e.importance = $imp, e.updated_at = $ts
            """
            self.conn.execute(
                query,
                {
                    "id": entity_id,
                    "name": name,
                    "etype": entity_type,
                    "imp": float(importance),
                    "ts": timestamp,
                },
            )
        else:
            desc_lit = self._cypher_str(description)
            query = f"""
                CREATE (e:Entity {{id: $id, name: $name, entity_type: $etype,
                    description: {desc_lit}, importance: $imp,
                    created_at: $ts, updated_at: $ts2}})
            """
            self.conn.execute(
                query,
                {
                    "id": entity_id,
                    "name": name,
                    "etype": entity_type,
                    "imp": float(importance),
                    "ts": timestamp,
                    "ts2": timestamp,
                },
            )
        self.invalidate_entity_name_index()
        return entity_id

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by ID."""
        result = self.conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.*", {"id": entity_id}
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

    def find_entities_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find entities by name (fuzzy match)."""
        result = self.conn.execute(
            """
            MATCH (e:Entity)
            WHERE e.name CONTAINS $name
            RETURN e.*
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
            RETURN a.id as from_id, b.id as to_id, r.*
            ORDER BY r.confidence DESC
        """

        params = {"id": entity_id, "time": valid_at}
        if relation_type:
            params["rel_type"] = relation_type

        result = self.conn.execute(query, params)

        relations = []
        while result.has_next():
            row = result.get_next()
            # Kuzu returns list: [from_id, to_id, relation_type, confidence, valid_from, valid_until, created_at, updated_at, metadata]
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
            # Kuzu returns list: [id, entity_id, content, embedding, valid_from,
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
        entities = {}
        for eid in list(dict.fromkeys(seed_entity_ids))[:max_nodes]:
            entity = self.get_entity(eid)
            if entity:
                entities[eid] = entity
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

    def get_relationship_conflicts_batch(
        self, observation_ids, use_batched_resolution=True
    ):
        """Resolve every observation for each owner, retaining edge direction and time."""
        original_ids = list(dict.fromkeys(observation_ids))
        output = {mid: [] for mid in original_ids}
        result = self.conn.execute(
            "MATCH (o:Observation) RETURN o.id, o.entity_id, o.source_memory_id"
        )
        owners, aliases = {}, {}
        while result.has_next():
            oid, eid, source = result.get_next()
            owner = self.observation_memory_id(
                dict(id=oid, entity_id=eid, source_memory_id=source)
            )
            owners[oid] = owner
            aliases[oid] = [mid for mid in original_ids if mid == oid or mid == owner]
        resolved = [oid for oid, ids in aliases.items() if ids]
        if not resolved:
            return output
        for kind, time_field, extra in (
            ("CONTRADICTS", "detected_at", "AND r.resolved = false"),
            ("SUPERSEDES", "superseded_at", ""),
        ):
            result = self.conn.execute(
                f"""
                MATCH (old:Observation)-[r:{kind}]->(new:Observation)
                WHERE (old.id IN $ids OR new.id IN $ids) {extra}
                RETURN old.id, new.id, r.confidence, r.{time_field}
            """,
                {"ids": resolved},
            )
            while result.has_next():
                old, new, confidence, effective_at = result.get_next()
                for oid, other, direction in (
                    (old, new, "outgoing"),
                    (new, old, "incoming"),
                ):
                    for mid in aliases.get(oid, []):
                        output[mid].append(
                            dict(
                                relationship_type=kind,
                                id=other,
                                memory_id=owners.get(other, other),
                                confidence=confidence,
                                effective_at=effective_at,
                                direction=direction,
                                from_id=old,
                                to_id=new,
                            )
                        )
        return output

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

    def get_node_counts(self):
        """Report real counts; query failures propagate rather than becoming zeros."""
        return {
            table: self.conn.execute(f"MATCH (n:{table}) RETURN count(n)").get_next()[0]
            for table in ("Entity", "Observation")
        }

    def get_edge_counts(self):
        return {
            table: self.conn.execute(
                f"MATCH ()-[r:{table}]->() RETURN count(r)"
            ).get_next()[0]
            for table in ("RELATES", "ABOUT", "CONTRADICTS", "SUPERSEDES")
        }

    def execute(self, query: str, params: Optional[Dict] = None):
        """Execute raw Cypher query."""
        return self.conn.execute(query, params or {})

    def close(self):
        """Close connection."""
        self.conn.close()
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
