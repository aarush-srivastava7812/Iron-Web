from pathlib import Path
p=Path(__file__).resolve().parents[1]/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8')
a=s.index('        """Upsert a relation');b=s.index('    def get_relations(',a)
s=s[:a]+'''        """Version relationships by interval and provenance rather than overwriting history."""
        import time
        import json
        import math
        if valid_from > valid_until or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Invalid relationship validity or confidence.")
        if self.get_entity(from_id) is None or self.get_entity(to_id) is None:
            raise ValueError("Both relationship endpoints must exist.")
        timestamp = int(time.time()) if timestamp is None else timestamp
        meta = json.dumps(metadata or {}, sort_keys=True, allow_nan=False)
        parameters = dict(source=from_id, target=to_id, kind=relation_type, confidence=confidence,
                          start=valid_from, end=valid_until, timestamp=timestamp, metadata=meta)
        result = self.conn.execute("""
            MATCH (a:Entity {id: $source})-[r:RELATES]->(b:Entity {id: $target})
            WHERE r.relation_type = $kind AND r.valid_from = $start AND r.valid_until = $end AND r.metadata = $metadata
            RETURN r.relation_type
        """, {k:parameters[k] for k in ("source", "target", "kind", "start", "end", "metadata")})
        if result.has_next():
            self.conn.execute("""
                MATCH (a:Entity {id: $source})-[r:RELATES]->(b:Entity {id: $target})
                WHERE r.relation_type = $kind AND r.valid_from = $start AND r.valid_until = $end AND r.metadata = $metadata
                SET r.confidence = $confidence, r.updated_at = $timestamp
            """, parameters)
        else:
            self.conn.execute("""
                MATCH (a:Entity {id: $source}), (b:Entity {id: $target})
                CREATE (a)-[:RELATES {relation_type: $kind, confidence: $confidence, valid_from: $start,
                    valid_until: $end, created_at: $timestamp, updated_at: $timestamp, metadata: $metadata}]->(b)
            """, parameters)
        return True

''' +s[b:]
a=s.index('        observations =',s.index('    def delete_memory('))
s=s[:a]+'''        import json
        relation_result = self.conn.execute("MATCH ()-[r:RELATES]->() RETURN DISTINCT r.metadata")
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
            self.conn.execute("MATCH ()-[r:RELATES]->() WHERE r.metadata = $metadata DELETE r", {"metadata": value})
''' +s[a:]
s=s.replace('        if not matched_obs_ids:\n            return False','        if not matched_obs_ids:\n            return bool(owned_metadata)')
p.write_text(s,encoding='utf-8')
