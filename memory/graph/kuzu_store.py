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
        import os
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
        # Older databases created before source_memory_id existed: add the
        # column in place so they stay readable.
        try:
            self.conn.execute(
                "ALTER NODE TABLE Observation ADD source_memory_id STRING DEFAULT ''"
            )
        except Exception:
            pass  # column already exists
        
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
        
        # Create indexes for common queries
        self._create_indexes()
    
    def _create_indexes(self):
        """Create indexes for performance."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_entity_name ON Entity(name)",
            "CREATE INDEX IF NOT EXISTS idx_entity_type ON Entity(type)",
            "CREATE INDEX IF NOT EXISTS idx_observation_entity ON Observation(entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_observation_valid ON Observation(valid_from, valid_until)",
            "CREATE INDEX IF NOT EXISTS idx_relates_type ON RELATES(relation_type)",
        ]
        
        for idx in indexes:
            try:
                self.conn.execute(idx)
            except Exception:
                pass
    
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
        timestamp: Optional[int] = None
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
            self.conn.execute(query, {
                "id": entity_id, "name": name, "etype": entity_type,
                "imp": float(importance), "ts": timestamp
            })
        else:
            desc_lit = self._cypher_str(description)
            query = f"""
                CREATE (e:Entity {{id: $id, name: $name, entity_type: $etype,
                    description: {desc_lit}, importance: $imp,
                    created_at: $ts, updated_at: $ts2}})
            """
            self.conn.execute(query, {
                "id": entity_id, "name": name, "etype": entity_type,
                "imp": float(importance), "ts": timestamp, "ts2": timestamp
            })
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
                "updated_at": row[6]
            }
        return None
    
    def find_entities_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find entities by name (fuzzy match)."""
        result = self.conn.execute("""
            MATCH (e:Entity)
            WHERE e.name CONTAINS $name
            RETURN e.*
            ORDER BY e.importance DESC
            LIMIT $limit
        """, {"name": name, "limit": limit})
        
        entities = []
        while result.has_next():
            row = result.get_next()
            entities.append({
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "description": row[3],
                "importance": row[4],
                "created_at": row[5],
                "updated_at": row[6]
            })
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
                {"id": entity_id}
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
        valid_until: int = 2**31 - 1,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None
    ) -> bool:
        """Upsert a relation between entities."""
        import time
        import json
        if timestamp is None:
            timestamp = int(time.time())
        
        meta_str = json.dumps(metadata) if metadata else "{}"
        
        # Check if relation exists
        result = self.conn.execute("""
            MATCH (a:Entity {id: $from_id})-[r:RELATES]->(b:Entity {id: $to_id})
            WHERE r.relation_type = $rel_type
            RETURN r
        """, {"from_id": from_id, "to_id": to_id, "rel_type": relation_type})
        
        if result.has_next():
            # Update
            self.conn.execute("""
                MATCH (a:Entity {id: $from_id})-[r:RELATES]->(b:Entity {id: $to_id})
                WHERE r.relation_type = $rel_type
                SET r.confidence = $conf, r.valid_from = $vf, r.valid_until = $vu,
                    r.updated_at = $ts, r.metadata = $meta
            """, {
                "from_id": from_id, "to_id": to_id, "rel_type": relation_type,
                "conf": confidence, "vf": valid_from, "vu": valid_until,
                "ts": timestamp, "meta": meta_str
            })
        else:
            # Create
            self.conn.execute("""
                MATCH (a:Entity {id: $from_id}), (b:Entity {id: $to_id})
                CREATE (a)-[r:RELATES {
                    relation_type: $rel_type, confidence: $conf,
                    valid_from: $vf, valid_until: $vu,
                    created_at: $ts, metadata: $meta
                }]->(b)
            """, {
                "from_id": from_id, "to_id": to_id, "rel_type": relation_type,
                "conf": confidence, "vf": valid_from, "vu": valid_until,
                "ts": timestamp, "meta": meta_str
            })
        
        return True
    
    def get_relations(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both",  # "out", "in", "both"
        valid_at: Optional[int] = None
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
            relations.append({
                "from_id": row[0],
                "to_id": row[1],
                "relation_type": row[2],
                "confidence": row[3],
                "valid_from": row[4],
                "valid_until": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "metadata": row[8]
            })
        return relations
    
    # === Observation Operations ===
    
    def upsert_observation(
        self,
        obs_id: str,
        entity_id: str,
        content: str,
        embedding: Optional[List[float]] = None,
        valid_from: int = 0,
        valid_until: int = 2**31 - 1,
        importance: float = 1.0,
        source: str = "user",
        timestamp: Optional[int] = None,
        source_memory_id: Optional[str] = None
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
            src_mem = obs_id[4:-len(suffix)] if obs_id.endswith(suffix) else obs_id[4:]
        
        # Check if exists
        result = self.conn.execute(
            "MATCH (o:Observation {id: $id}) RETURN o.id", {"id": obs_id}
        )
        
        if result.has_next():
            if embedding is not None:
                self.conn.execute("""
                    MATCH (o:Observation {id: $id})
                    SET o.content = $content, o.embedding = $emb, o.valid_from = $vf,
                        o.valid_until = $vu, o.importance = $imp, o.source = $src,
                        o.source_memory_id = $src_mem
                """, {
                    "id": obs_id, "content": content, "emb": emb_str,
                    "vf": valid_from, "vu": valid_until, "imp": importance,
                    "src": source, "src_mem": src_mem
                })
            else:
                self.conn.execute("""
                    MATCH (o:Observation {id: $id})
                    SET o.content = $content, o.valid_from = $vf,
                        o.valid_until = $vu, o.importance = $imp, o.source = $src,
                        o.source_memory_id = $src_mem
                """, {
                    "id": obs_id, "content": content,
                    "vf": valid_from, "vu": valid_until, "imp": importance,
                    "src": source, "src_mem": src_mem
                })
        else:
            self.conn.execute("""
                CREATE (o:Observation {
                    id: $id, entity_id: $eid, content: $content, embedding: $emb,
                    valid_from: $vf, valid_until: $vu, importance: $imp,
                    source: $src, created_at: $ts, source_memory_id: $src_mem
                })
            """, {
                "id": obs_id, "eid": entity_id, "content": content, "emb": emb_str,
                "vf": valid_from, "vu": valid_until, "imp": importance,
                "src": source, "ts": timestamp, "src_mem": src_mem
            })
        
        # Link to entity
        self.conn.execute("""
            MATCH (o:Observation {id: $oid}), (e:Entity {id: $eid})
            MERGE (o)-[:ABOUT {relevance: 1.0}]->(e)
        """, {"oid": obs_id, "eid": entity_id})
        
        return obs_id
    
    def get_observations(
        self,
        entity_id: str,
        valid_at: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get observations for an entity."""
        import time
        if valid_at is None:
            valid_at = int(time.time())
        
        result = self.conn.execute("""
            MATCH (o:Observation)-[:ABOUT]->(e:Entity {id: $eid})
            WHERE o.valid_from <= $time AND o.valid_until >= $time
            RETURN o.id, o.entity_id, o.content, o.embedding, o.valid_from,
                   o.valid_until, o.importance, o.source, o.created_at, o.source_memory_id
            ORDER BY o.importance DESC
            LIMIT $limit
        """, {"eid": entity_id, "time": valid_at, "limit": limit})
        
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
                "source_memory_id": row[9] if len(row) > 9 else ""
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
        result = self.conn.execute("""
            MATCH (o:Observation {id: $id})
            RETURN o.id, o.entity_id, o.content, o.embedding, o.valid_from, o.valid_until, o.importance, o.source, o.created_at, o.source_memory_id
        """, {"id": obs_id})
        
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
            "source_memory_id": row[9] if len(row) > 9 else ""
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
        result = self.conn.execute("""
            MATCH (o:Observation)
            WHERE o.source_memory_id = $mid OR
                ((o.source_memory_id IS NULL OR o.source_memory_id = '') AND
                 (o.id = $mid OR o.id = 'obs_' + $mid OR
                  o.id = 'obs_' + $mid + '_' + o.entity_id))
            RETURN o.id
        """, {"mid": memory_id})
        ids = []
        while result.has_next():
            ids.append(result.get_next()[0])
        return [self.get_observation(oid) for oid in ids]

    def delete_memory(self, memory_id: str, clean_orphaned_entities: bool = False) -> bool:
        """
        Delete all observations and graph components associated with a memory ID.
        
        Args:
            memory_id: Memory identifier
            clean_orphaned_entities: If True, remove entities that no longer have any observations
            
        Returns:
            True if one or more observations were deleted, False if none found
        """
        observations = self.get_memory_observations(memory_id)
        matched_obs_ids = [obs["id"] for obs in observations]
        referenced_entity_ids = {obs["entity_id"] for obs in observations if obs["entity_id"]}
                    
        if not matched_obs_ids:
            return False
            
        for oid in matched_obs_ids:
            self.conn.execute(
                "MATCH (o:Observation {id: $id}) DETACH DELETE o", {"id": oid}
            )
            
        if clean_orphaned_entities:
            for eid in referenced_entity_ids:
                rem = self.conn.execute(
                    "MATCH (o:Observation)-[:ABOUT]->(e:Entity {id: $id}) RETURN count(o)",
                    {"id": eid}
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
        seed_entity_ids: List[str],
        hops: int = 2,
        relation_types: Optional[List[str]] = None,
        valid_at: Optional[int] = None,
        include_relations: bool = True,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Expand graph from seed entities (1-2 hop traversal).
        
        Returns:
            (entities, relations)
        """
        import time
        if valid_at is None:
            valid_at = int(time.time())
        
        if not seed_entity_ids:
            return [], []
        
        # Fetch only the graph material the caller consumes.  The former
        # implementation first ran a third traversal and discarded every row.
        entities = self._get_expanded_entities(seed_entity_ids, hops, relation_types, valid_at)
        relations = (
            self._get_expanded_relations(seed_entity_ids, hops, relation_types, valid_at)
            if include_relations else []
        )
        
        return entities, relations
    
    def _get_expanded_entities(
        self,
        seed_ids: List[str],
        hops: int,
        relation_types: Optional[List[str]],
        valid_at: int
    ) -> List[Dict]:
        """Get expanded entities."""
        seed_list = ", ".join([f"'{eid}'" for eid in seed_ids])
        rel_filter = ""
        if relation_types:
            rel_list = ", ".join([f"'{rt}'" for rt in relation_types])
            rel_filter = f"AND r.relation_type IN [{rel_list}]"
        
        if hops == 1:
            query = (
                "MATCH (e:Entity)-[r:RELATES]-(n:Entity) "
                f"WHERE e.id IN [{seed_list}] "
                "AND r.valid_from <= $time AND r.valid_until >= $time "
                f"{rel_filter} "
                "RETURN DISTINCT n.*"
            )
        else:
            # Build NOT IN equivalent using <> for each seed ID
            not_in_filter = ""
            if seed_ids:
                not_in_filter = " AND " + " AND ".join([f"n.id <> '{eid}'" for eid in seed_ids])
            query = (
                "MATCH (e:Entity)-[r1:RELATES]-(mid:Entity)-[r2:RELATES]-(n:Entity) "
                f"WHERE e.id IN [{seed_list}] "
                "AND r1.valid_from <= $time AND r1.valid_until >= $time "
                "AND r2.valid_from <= $time AND r2.valid_until >= $time "
                f"{rel_filter} "
                f"{not_in_filter} "
                "RETURN DISTINCT n.*"
            )
        
        result = self.conn.execute(query, {"time": valid_at})
        entities = []
        while result.has_next():
            row = result.get_next()
            entities.append({
                "id": row[0],
                "name": row[1],
                "entity_type": row[2],
                "description": row[3],
                "importance": row[4],
                "created_at": row[5],
                "updated_at": row[6]
            })
        return entities
    
    def _get_expanded_relations(
        self,
        seed_ids: List[str],
        hops: int,
        relation_types: Optional[List[str]],
        valid_at: int
    ) -> List[Dict]:
        """Get expanded relations."""
        seed_list = ", ".join([f"'{eid}'" for eid in seed_ids])
        rel_filter = ""
        if relation_types:
            rel_list = ", ".join([f"'{rt}'" for rt in relation_types])
            rel_filter = f"AND r.relation_type IN [{rel_list}]"
        
        if hops == 1:
            query = (
                "MATCH (e:Entity)-[r:RELATES]-(n:Entity) "
                f"WHERE e.id IN [{seed_list}] "
                "AND r.valid_from <= $time AND r.valid_until >= $time "
                f"{rel_filter} "
                "RETURN DISTINCT r.*, e.id as from_id, n.id as to_id"
            )
        else:
            # Build NOT IN equivalent using <> for each seed ID
            not_in_filter = ""
            if seed_ids:
                not_in_filter = " AND " + " AND ".join([f"n.id <> '{eid}'" for eid in seed_ids])
            query = (
                "MATCH (e:Entity)-[r1:RELATES]-(mid:Entity)-[r2:RELATES]-(n:Entity) "
                f"WHERE e.id IN [{seed_list}] "
                "AND r1.valid_from <= $time AND r1.valid_until >= $time "
                "AND r2.valid_from <= $time AND r2.valid_until >= $time "
                f"{rel_filter} "
                f"{not_in_filter} "
                "RETURN DISTINCT r2.*, mid.id as from_id, n.id as to_id"
            )
        
        result = self.conn.execute(query, {"time": valid_at})
        relations = []
        while result.has_next():
            row = result.get_next()
            # Kuzu returns list: [relation_type, confidence, valid_from, valid_until, created_at, updated_at, metadata, from_id, to_id]
            relations.append({
                "relation_type": row[0],
                "confidence": row[1],
                "valid_from": row[2],
                "valid_until": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "metadata": row[6],
                "from_id": row[7],
                "to_id": row[8]
            })
        return relations
    
    # === Contradiction/Supersession ===
    
    def _resolve_obs_id(self, target_id: str) -> str:
        """Resolve exact observation identifiers without a table-wide substring scan."""
        res = self.conn.execute("MATCH (o:Observation {id: $id}) RETURN o.id", {"id": target_id})
        if res.has_next():
            return target_id
        res2 = self.conn.execute("MATCH (o:Observation {id: $id}) RETURN o.id", {"id": f"obs_{target_id}"})
        if res2.has_next():
            return f"obs_{target_id}"
        return target_id

    def get_relationship_conflicts_batch(
        self, observation_ids: List[str], use_batched_resolution: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch conflicts in constant queries, with a legacy resolver fallback."""
        if not use_batched_resolution:
            return self._get_relationship_conflicts_legacy(observation_ids)

        original_ids = list(dict.fromkeys(obs_id for obs_id in observation_ids if obs_id))
        candidates = list(dict.fromkeys(
            original_ids + [f"obs_{obs_id}" for obs_id in original_ids if not obs_id.startswith("obs_")]
        ))
        try:
            result = self.conn.execute(
                "MATCH (o:Observation) WHERE o.id IN $ids RETURN o.id", {"ids": candidates}
            )
            available = set()
            while result.has_next():
                available.add(str(result.get_next()[0]))
            resolved_by_original = {
                obs_id: obs_id if obs_id in available else f"obs_{obs_id}"
                for obs_id in original_ids
                if obs_id in available or f"obs_{obs_id}" in available
            }
        except Exception:
            return self._get_relationship_conflicts_legacy(observation_ids)

        output: Dict[str, List[Dict[str, Any]]] = {obs_id: [] for obs_id in original_ids}
        resolved_to_original = {resolved: original for original, resolved in resolved_by_original.items()}
        resolved = list(resolved_to_original)
        if not resolved:
            return output
        for relationship_type in ("CONTRADICTS", "SUPERSEDES"):
            result = self.conn.execute(f"""
                MATCH (o:Observation)-[r:{relationship_type}]-(other:Observation)
                WHERE o.id IN $ids
                RETURN o.id, other.id, r.confidence
            """, {"ids": resolved})
            while result.has_next():
                row = result.get_next()
                output[resolved_to_original[row[0]]].append({
                    "relationship_type": relationship_type, "id": row[1], "confidence": row[2],
                })
        return output

    def _get_relationship_conflicts_legacy(self, observation_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Original resolver retained for A/B rollback and exceptional fallback."""
        resolved = [self._resolve_obs_id(obs_id) for obs_id in observation_ids]
        resolved = [obs_id for obs_id in resolved if obs_id.startswith("obs_")]
        output: Dict[str, List[Dict[str, Any]]] = {obs_id: [] for obs_id in resolved}
        if not resolved:
            return output
        # Kuzu 0.11.3 has no Cypher type(r), so keep the relationship type
        # explicit while still issuing a constant two queries, not 2*N scans.
        for relationship_type in ("CONTRADICTS", "SUPERSEDES"):
            result = self.conn.execute(f"""
                MATCH (o:Observation)-[r:{relationship_type}]-(other:Observation)
                WHERE o.id IN $ids
                RETURN o.id, other.id, r.confidence
            """, {"ids": resolved})
            while result.has_next():
                row = result.get_next()
                output.setdefault(row[0], []).append({
                    "relationship_type": relationship_type, "id": row[1],
                    "confidence": row[2],
                })
        return output

    def add_contradiction(
        self,
        obs_id_1: Optional[str] = None,
        obs_id_2: Optional[str] = None,
        confidence: float = 1.0,
        detected_at: Optional[int] = None,
        nature: Optional[str] = None,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None
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
        
        self.conn.execute("""
            MATCH (o1:Observation {id: $id1}), (o2:Observation {id: $id2})
            MERGE (o1)-[c:CONTRADICTS {confidence: $conf, detected_at: $det, resolved: false}]->(o2)
        """, {"id1": id1, "id2": id2, "conf": confidence, "det": detected_at})

    record_contradiction = add_contradiction
    
    def add_supersession(
        self,
        old_obs_id: str,
        new_obs_id: str,
        confidence: float,
        reason: str = "",
        superseded_at: Optional[int] = None
    ):
        """Add supersession edge (old -> new)."""
        import time
        if superseded_at is None:
            superseded_at = int(time.time())
        
        self.conn.execute("""
            MATCH (old:Observation {id: $old}), (new:Observation {id: $new})
            MERGE (old)-[s:SUPERSEDES {confidence: $conf, superseded_at: $ts, reason: $reason}]->(new)
        """, {"old": old_obs_id, "new": new_obs_id, "conf": confidence, "ts": superseded_at, "reason": reason})
    
    def get_contradictions(self, obs_id: str) -> List[Dict[str, Any]]:
        """Get contradictions for an observation."""
        real_id = self._resolve_obs_id(obs_id)
        result = self.conn.execute("""
            MATCH (o:Observation {id: $id})-[c:CONTRADICTS]-(other:Observation)
            RETURN other.id, other.entity_id, other.content, c.confidence, c.detected_at, c.resolved
        """, {"id": real_id})
        
        contra = []
        while result.has_next():
            row = result.get_next()
            contra.append({
                "id": row[0],
                "entity_id": row[1],
                "content": row[2],
                "confidence": row[3],
                "detected_at": row[4],
                "resolved": row[5]
            })
        return contra
    
    def get_supersessions(self, obs_id: str) -> List[Dict[str, Any]]:
        """Get supersession chain for an observation."""
        real_id = self._resolve_obs_id(obs_id)
        result = self.conn.execute("""
            MATCH (o:Observation {id: $id})-[s:SUPERSEDES]->(new:Observation)
            RETURN new.id, new.entity_id, new.content, s.confidence, s.reason, s.superseded_at, 'SUPERSEDED_BY' as direction
            UNION
            MATCH (old:Observation)-[s:SUPERSEDES]->(o:Observation {id: $id})
            RETURN old.id, old.entity_id, old.content, s.confidence, s.reason, s.superseded_at, 'SUPERSEDES' as direction
        """, {"id": real_id})
        
        supers = []
        while result.has_next():
            row = result.get_next()
            supers.append({
                "id": row[0],
                "entity_id": row[1],
                "content": row[2],
                "confidence": row[3],
                "reason": row[4],
                "superseded_at": row[5],
                "direction": row[6]
            })
        return supers
    
    # === Utility ===
    
    def get_node_counts(self) -> Dict[str, int]:
        """Get counts of all node types."""
        counts = {}
        for table in ["Entity", "Observation"]:
            try:
                result = self.conn.execute(f"MATCH (n:{table}) RETURN count(n) as count")
                if result.has_next():
                    row = result.get_next()
                    counts[table] = row[0] if isinstance(row, (list, tuple)) else row.get("count", 0)
                else:
                    counts[table] = 0
            except Exception:
                counts[table] = 0
        return counts
    
    def get_edge_counts(self) -> Dict[str, int]:
        """Get counts of all edge types."""
        counts = {}
        for table in ["RELATES", "ABOUT", "CONTRADICTS", "SUPERSEDES"]:
            try:
                # All schema relations are directed. An undirected Cypher pattern
                # visits each stored edge from both endpoints and doubles counts.
                result = self.conn.execute(f"MATCH ()-[r:{table}]->() RETURN count(r) as count")
                if result.has_next():
                    row = result.get_next()
                    counts[table] = row[0] if isinstance(row, (list, tuple)) else row.get("count", 0)
                else:
                    counts[table] = 0
            except Exception:
                counts[table] = 0
        return counts
    
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
