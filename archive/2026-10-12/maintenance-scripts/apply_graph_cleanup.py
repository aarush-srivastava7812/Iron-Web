from pathlib import Path
p=Path(__file__).resolve().parents[1]/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8')
a=s.index('    def _resolve_obs_id(')
b=s.index('    def add_contradiction(',a)
s=s[:a]+'''    @staticmethod
    def observation_memory_id(observation):
        owner = observation.get("source_memory_id")
        if owner:
            return owner
        oid, eid = observation["id"], observation.get("entity_id", "")
        suffix = "_" + eid
        if oid.startswith("obs_") and eid and oid.endswith(suffix):
            return oid[4:-len(suffix)]
        return oid[4:] if oid.startswith("obs_") else oid

    def _resolve_obs_id(self, target_id):
        if self.get_observation(target_id):
            return target_id
        observations = self.get_memory_observations(target_id)
        if not observations:
            raise ValueError(f"Unknown observation or memory: {target_id}")
        return sorted(o["id"] for o in observations)[0]

    def get_relationship_conflicts_batch(self, observation_ids, use_batched_resolution=True):
        """Resolve every observation for each owner, retaining edge direction and time."""
        original_ids = list(dict.fromkeys(observation_ids))
        output = {mid: [] for mid in original_ids}
        result = self.conn.execute("MATCH (o:Observation) RETURN o.id, o.entity_id, o.source_memory_id")
        owners, aliases = {}, {}
        while result.has_next():
            oid, eid, source = result.get_next()
            owner = self.observation_memory_id(dict(id=oid, entity_id=eid, source_memory_id=source))
            owners[oid] = owner
            aliases[oid] = [mid for mid in original_ids if mid == oid or mid == owner]
        resolved = [oid for oid, ids in aliases.items() if ids]
        if not resolved:
            return output
        for kind, time_field, extra in (("CONTRADICTS", "detected_at", "AND r.resolved = false"),
                                       ("SUPERSEDES", "superseded_at", "")):
            result = self.conn.execute(f"""
                MATCH (old:Observation)-[r:{kind}]->(new:Observation)
                WHERE (old.id IN $ids OR new.id IN $ids) {extra}
                RETURN old.id, new.id, r.confidence, r.{time_field}
            """, {"ids": resolved})
            while result.has_next():
                old, new, confidence, effective_at = result.get_next()
                for oid, other, direction in ((old, new, "outgoing"), (new, old, "incoming")):
                    for mid in aliases.get(oid, []):
                        output[mid].append(dict(relationship_type=kind, id=other, memory_id=owners.get(other, other),
                            confidence=confidence, effective_at=effective_at, direction=direction, from_id=old, to_id=new))
        return output

''' +s[b:]
s=s.replace('        self.conn.execute("""\n            MATCH (old:Observation {id: $old})', '        old_obs_id = self._resolve_obs_id(old_obs_id)\n        new_obs_id = self._resolve_obs_id(new_obs_id)\n        self.conn.execute("""\n            MATCH (old:Observation {id: $old})',1)
s=s.replace('                "direction": row[6]', '                "from_id": real_id if row[6] == "SUPERSEDED_BY" else row[0],\n                "to_id": row[0] if row[6] == "SUPERSEDED_BY" else real_id,\n                "direction": row[6]')
s=s.replace('2**31 - 1','2**63 - 1')
p.write_text(s,encoding='utf-8')
