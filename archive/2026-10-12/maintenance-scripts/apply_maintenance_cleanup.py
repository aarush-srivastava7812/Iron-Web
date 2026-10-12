from pathlib import Path
p=Path(__file__).resolve().parents[1]/'memory/maintenance/maintenance.py'
s=p.read_text(encoding='utf-8').replace('from sklearn.cluster import DBSCAN', 'import hashlib\nimport json\nfrom memory.storage import coordinated_write')
s=s.replace('Production-ready background jobs for memory health, idempotency, and cross-store consistency.', 'Explicit maintenance with verified rollback and source provenance.')
s=s.replace('        self.half_life_days = half_life_days', '        if half_life_days <= 0 or not 0 <= min_importance <= 1:\n            raise ValueError("Invalid decay settings.")\n        self.half_life_days = half_life_days')
s=s.replace('np.exp(-age_days / self.half_life_days)', '2 ** (-age_days / self.half_life_days)')
s=s.replace('        now = int(time.time()) if current_time is None else current_time', '        if batch_size < 1:\n            raise ValueError("Batch size must be positive.")\n        now = int(time.time()) if current_time is None else current_time',1)
a=s.index('                    try:',s.index('    def apply_decay('))
b=s.index('            else:\n                stats["unchanged"]',a)
s=s[:a]+'''                    try:
                        with coordinated_write(self.vector_store, self.graph_store, [mem_id]):
                            metadata = {k: v for k, v in payload.items() if k not in {
                                "memory_id", "text", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"}}
                            metadata["initial_importance"] = initial_importance
                            self.vector_store.upsert_memory(mem_id, payload["text"], np.array(record.vector),
                                payload.get("entity_ids", []), payload.get("valid_from", 0), payload.get("valid_until", 2**63-1),
                                new_importance, metadata=metadata, timestamp=ts)
                            for observation in self.graph_store.get_memory_observations(mem_id):
                                self.graph_store.conn.execute("MATCH (o:Observation {id: $id}) SET o.importance = $value",
                                    {"id": observation["id"], "value": new_importance})
                    except Exception as error:
                        stats["errors"] += 1
                        stats.setdefault("error_details", []).append({"memory_id": mem_id, "error": str(error)})
''' +s[b:]
# Original loop variable is `r`, verified against source.
s=s.replace('np.array(record.vector)', 'np.array(r.vector)')
a=s.index('        """',s.index('    def find_duplicates('))
b=s.index('    def merge_duplicates(',a)
s=s[:a]+'''        """Group identical text, validity and type; similarity never establishes equivalence."""
        if payloads is None or len(payloads) != len(memory_ids):
            raise ValueError("One payload is required per memory ID.")
        groups = {}
        for mid, payload in zip(memory_ids, payloads):
            key = (" ".join(payload.get("text", "").split()), payload.get("valid_from", 0),
                   payload.get("valid_until", 2**63-1), payload.get("memory_type", "semantic"))
            if key[0]:
                groups.setdefault(key, []).append(mid)
        clusters = []
        for members in groups.values():
            safe = []
            for mid in members:
                conflicts = self.graph_store.get_relationship_conflicts_batch([mid]).get(mid, [])
                linked = {c.get("memory_id", c.get("id")) for c in conflicts}
                if not linked.intersection(members):
                    safe.append(mid)
            if len(safe) >= self.min_samples:
                clusters.append(safe)
        return clusters

''' +s[b:]
s=s.replace('                continue\n                \n            # Select canonical:', '''                continue
            eligible = self.find_duplicates(cluster, None, [m["payload"] for m in memories])
            if not eligible or set(eligible[0]) != set(cluster):
                continue

            # Select canonical:''',1)
a=s.index('            # Merge entity IDs and metadata')
b=s.index('            if not dry_run:',a)
s=s[:a]+'''            merged_entity_ids = sorted({eid for m in memories for eid in m["payload"].get("entity_ids", [])})
            merged_meta = {k: v for k, v in canonical["payload"].items() if k not in {
                "text", "memory_id", "entity_ids", "valid_from", "valid_until", "importance", "timestamp"}}
            merged_meta["merged_from"] = sorted(set(merged_meta.get("merged_from", [])) | (set(cluster) - {canonical_id}))
            merged_meta["merged_records"] = [{"payload": m["payload"],
                "observations": self.graph_store.get_memory_observations(m["payload"]["memory_id"])}
                for m in memories if m is not canonical]
''' +s[b:]
a=s.index('                # 1. Update canonical')
b=s.index('            stats["canonical_memories"]',a)
block=s[a:b]
block=block.replace('                        stats["memories_merged"] += 1','')
insert=block.index('                # 2. Remove duplicate')
block=block[:insert]+'''                for eid in merged_entity_ids or [canonical_id]:
                    self.graph_store.upsert_observation(
                        obs_id=f"obs_{canonical_id}_{eid}" if eid != canonical_id else f"obs_{canonical_id}",
                        entity_id=eid, content=canonical["payload"]["text"], embedding=canonical["vector"],
                        valid_from=canonical["payload"].get("valid_from", 0), valid_until=canonical["payload"].get("valid_until", 2**63-1),
                        importance=canonical["payload"].get("importance", 1), source=canonical["payload"].get("source", "user"),
                        timestamp=canonical["payload"].get("timestamp", 0), source_memory_id=canonical_id)
''' +block[insert:]
s=s[:a]+'                with coordinated_write(self.vector_store, self.graph_store, cluster):\n'+''.join('    '+line if line.strip() else line for line in block.splitlines(True))+'            stats["memories_merged"] += len(memories) - 1\n'+s[b:]
s=s.replace('        records = []\n        offset = None\n        while len(records) < limit:', '        if limit < 1:\n            raise ValueError("Scan limit must be positive.")\n        records = []\n        offset = None\n        while len(records) < limit:',1)
s=s.replace('            if start_time <= ts <= end_time:', '            if p.get("memory_type") == "episodic" and start_time <= ts <= end_time:')
s=s.replace('        texts = [ep["text"]', '        if dry_run:\n            return stats\n        texts = [ep["text"]',1)
s=s.replace('                self.store_skill(skill, dry_run=False)\n                stats["patterns_stored"] += 1', '                skill_id = self._skill_id(skill)\n                if self.vector_store.get_memory(skill_id) is None:\n                    self.store_skill(skill, dry_run=False)\n                    stats["patterns_stored"] += 1')
a=s.index('        """',s.index('    def extract_skill_patterns('))
b=s.index('    def store_skill(',a)
s=s[:a]+'''        """Accept explicit extraction; never manufacture generic skills."""
        if not self.extractor or not hasattr(self.extractor, "extract_skills"):
            return []
        skills = self.extractor.extract_skills(episode_texts)
        if not isinstance(skills, list) or any(not isinstance(skill, dict) or any(
            not isinstance(skill.get(k), str) or not skill[k].strip()
            for k in ("name", "description", "conditions", "actions")) for skill in skills):
            raise ValueError("Skill extraction returned invalid data.")
        return skills

    @staticmethod
    def _skill_id(skill):
        identity = dict(skill)
        identity["provenance"] = {"source_memory_ids": sorted(skill.get("provenance", {}).get("source_memory_ids", []))}
        return "skill_" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]

''' +s[b:]
s=s.replace('skill_id = f"skill_{uuid.uuid4().hex[:8]}"', 'skill_id = self._skill_id(skill)')
s=s.replace('text = f"Procedural Skill: {skill[\'name\']}. {skill[\'description\']}"', 'text = f"Procedural Skill: {skill[\'name\']}. {skill[\'description\']}. Conditions: {skill[\'conditions\']}. Actions: {skill[\'actions\']}"')
a=s.index('            self.vector_store.upsert_memory(',s.index('    def store_skill('))
b=s.index('        return skill_id',a)
block=s[a:b].replace('entity_ids=[]', 'entity_ids=[skill_id]')
block+='''            self.graph_store.upsert_observation(obs_id=f"obs_{skill_id}", entity_id=skill_id,
                content=text, embedding=embedding.tolist(), importance=0.9, source="consolidation", source_memory_id=skill_id)
'''
s=s[:a]+'            with coordinated_write(self.vector_store, self.graph_store, [skill_id]):\n'+''.join('    '+line if line.strip() else line for line in block.splitlines(True))+s[b:]
s=s.replace('tasks = tasks or ["decay", "dedup", "consolidate"]', 'tasks = ["decay", "dedup", "consolidate"] if tasks is None else tasks\n        if set(tasks) - {"decay", "dedup", "consolidate"}:\n            raise ValueError("Unknown maintenance task.")')
s=s.replace('current_time + 300', 'current_time')
s=s.replace('2**31 - 1','2**63 - 1')
p.write_text(s,encoding='utf-8')
