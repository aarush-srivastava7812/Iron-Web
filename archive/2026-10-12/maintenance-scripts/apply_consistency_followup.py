from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/engine.py'
s=p.read_text(encoding='utf-8')
s=s.replace('        with self._operation_lock:', '        with self.graph_store.write_lock, self._operation_lock:',1)
s=s.replace('        self.vector_store = vector_store or self._init_vector_store()\n        self.graph_store = graph_store or self._init_graph_store()', '''        self._owns_vector_store = vector_store is None
        self._owns_graph_store = graph_store is None
        self.vector_store = vector_store if vector_store is not None else self._init_vector_store()
        try:
            self.graph_store = graph_store if graph_store is not None else self._init_graph_store()
        except Exception:
            if self._owns_vector_store:
                self.vector_store.close()
            raise''')
s=s.replace('        extraction: Optional[Dict[str, Any]] = None\n', '        extraction: Optional[Dict[str, Any]] = None,\n        enrich_graph=None\n',1)
a=s.index('\n        return mem_id',s.index('    def add('))
s=s[:a]+'\n            if enrich_graph is not None:\n                enrich_graph(mem_id)\n'+s[a:]
a=s.index('        if not contents:',s.index('    def add_batch('));b=s.index('    @serialized\n    def get(',a)
s=s[:a]+'''        from memory.validation import MemoryInput
        if not isinstance(contents, list):
            raise ValueError("Batch contents must be a list.")
        if metadatas is not None and len(metadatas) != len(contents):
            raise ValueError("Batch content and metadata lengths differ.")
        if timestamps is not None and len(timestamps) != len(contents):
            raise ValueError("Batch content and timestamp lengths differ.")
        metadatas = [None]*len(contents) if metadatas is None else metadatas
        timestamps = [None]*len(contents) if timestamps is None else timestamps
        prepared = []
        fields = {"content", "text", "metadata", "timestamp", "entity_ids", "valid_from", "valid_until", "importance", "memory_id"}
        for item, metadata, timestamp in zip(contents, metadatas, timestamps):
            if isinstance(item, dict):
                values = dict(content=item.get("content", item.get("text", "")),
                    metadata=metadata if metadata is not None else item.get("metadata", {k:v for k,v in item.items() if k not in fields}),
                    timestamp=timestamp if timestamp is not None else item.get("timestamp"),
                    entity_ids=item.get("entity_ids"), valid_from=item.get("valid_from", 0),
                    valid_until=item.get("valid_until", 2**63-1), importance=item.get("importance", 1.), memory_id=item.get("memory_id"))
            elif isinstance(item, str):
                values = dict(content=item, metadata=metadata, timestamp=timestamp)
            else:
                raise ValueError("Batch entries must be strings or record dictionaries.")
            prepared.append(MemoryInput(**values).model_dump())
        # Validate the complete request first. Storage commits remain per record.
        return [self.add(**values) for values in prepared]

    @staticmethod
    def _validate_id(memory_id):
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("Memory ID must be a nonempty string.")

''' +s[b:]
for name, marker in (('get','        qdrant_point ='),('update','        if content is not None'),('delete','        with coordinated_write(')):
    a=s.index(marker,s.index('    def '+name+'('))
    s=s[:a]+'        self._validate_id(memory_id)\n'+s[a:]
a=s.index('        # If missing from Qdrant',s.index('    def get('));b=s.index('        return None',a)
s=s[:a]+'''        observations = self.graph_store.get_memory_observations(memory_id)
        if observations:
            if len({o["content"] for o in observations}) != 1:
                from memory.models import EngineStorageError
                raise EngineStorageError("Graph observations disagree on memory contents.", memory_id, rolled_back=False)
            observation = observations[0]
            return MemoryRecord(memory_id=memory_id, content=observation["content"],
                metadata={"source": observation.get("source"), "graph_only_recovery": True},
                entity_ids=sorted({o["entity_id"] for o in observations if o["entity_id"] != memory_id}),
                valid_from=observation["valid_from"], valid_until=observation["valid_until"],
                importance=observation["importance"], timestamp=observation["created_at"],
                vector_stored=False, graph_stored=True)

''' +s[b:]
s=s.replace('        eps: float = 0.15,\n','').replace('            eps=eps,\n','')
s=s.replace('            extractor=self.extractor,\n            embedder=self.embedder,\n            window_days', '            extractor=self._extractor if dry_run else self.extractor,\n            embedder=self._embedder if dry_run else self.embedder,\n            window_days')
s=s.replace('        scheduler = MaintenanceScheduler(', '''        selected = ["decay", "dedup", "consolidate"] if tasks is None else tasks
        if not isinstance(selected, list) or set(selected)-{"decay", "dedup", "consolidate"}:
            raise ValueError("Unknown maintenance tasks.")
        needs_models = not dry_run and "consolidate" in selected
        scheduler = MaintenanceScheduler(''',1)
s=s.replace('            embedder=self.embedder,\n            extractor=self.extractor\n', '            embedder=self.embedder if needs_models else self._embedder,\n            extractor=self.extractor if needs_models else self._extractor\n',1)
s=s.replace('        for store in (self.vector_store, self.graph_store):', '        stores = ([self.vector_store] if self._owns_vector_store else []) + ([self.graph_store] if self._owns_graph_store else [])\n        for store in stores:')
p.write_text(s,encoding='utf-8')
p=root/'memory/ingestion/pipeline.py'
s=p.read_text(encoding='utf-8')
a=s.index('        mid = self.engine.add(',s.index('    def ingest_text_with_extraction('));b=s.index('    def ingest_batch(',a)
s=s[:a]+'''        def enrich(mid):
            own = self.engine.graph_store.get_memory_observations(mid)
            own_ids = {o["id"] for o in own}
            for observation in own:
                candidates = self.engine.graph_store.get_observations(observation["entity_id"], valid_at=timestamp)
                conflicts = self.contradiction_detector.detect_contradictions(observation["id"], text,
                    [observation["entity_id"]], [o["id"] for o in candidates if o["id"] not in own_ids])
                for conflict in conflicts:
                    self.contradiction_detector.store_contradiction(conflict)
        return self.engine.add(text, memory_id=memory_id, metadata=metadata, timestamp=timestamp, extraction=extraction,
                               enrich_graph=enrich if self.contradiction_detector else None)

''' +s[b:]
p.write_text(s,encoding='utf-8')
p=root/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8')
a=s.index('        # Older databases');b=s.index('        # Relation between Observation',a)
s=s[:a]+'''        columns = self.conn.execute("CALL table_info('Observation') RETURN name")
        names = []
        while columns.has_next():
            names.append(columns.get_next()[0])
        if "source_memory_id" not in names:
            self.conn.execute("ALTER TABLE Observation ADD source_memory_id STRING DEFAULT ''")

''' +s[b:]
a=s.index('    def get_node_counts(');b=s.index('    def execute(',a)
s=s[:a]+'''    def get_node_counts(self):
        """Report real counts; query failures propagate rather than becoming zeros."""
        return {table: self.conn.execute(f"MATCH (n:{table}) RETURN count(n)").get_next()[0]
                for table in ("Entity", "Observation")}

    def get_edge_counts(self):
        return {table: self.conn.execute(f"MATCH ()-[r:{table}]->() RETURN count(r)").get_next()[0]
                for table in ("RELATES", "ABOUT", "CONTRADICTS", "SUPERSEDES")}

''' +s[b:]
s=s.replace('for eid in sorted(set(seed_entity_ids))[:max_nodes]:','for eid in list(dict.fromkeys(seed_entity_ids))[:max_nodes]:')
p.write_text(s,encoding='utf-8')
p=root/'memory/retrieval/hybrid.py'
s=p.read_text(encoding='utf-8').replace('        seeds = set(query_entities or [])', '        seeds = list(query_entities or [])').replace('            seeds.update(result["payload"].get("entity_ids", []))', '            seeds.extend(result["payload"].get("entity_ids", []))')
s=s.replace('expand_graph(sorted(seeds)[:self.config.graph_max_nodes]', 'expand_graph(list(dict.fromkeys(seeds))[:self.config.graph_max_nodes]')
s=s.replace('return self._combine_candidates([], results)[:self.config.graph_max_nodes]', 'return sorted(self._combine_candidates([], results), key=lambda c: (-c["score"], -c["payload"].get("importance", 0), c["memory_id"]))[:self.config.graph_max_nodes]')
p.write_text(s,encoding='utf-8')
p=root/'memory/maintenance/maintenance.py'
s=p.read_text(encoding='utf-8').replace('        eps: float = 0.15,  # Cosine distance threshold (~0.85 cosine similarity)\n','').replace('        self.eps = eps\n','')
s=s.replace('    Semantic deduplication using embedding clustering (DBSCAN) with safety\n    guards preventing the accidental merging of distinct or contradictory facts.', '    Exact-record deduplication with provenance and contradiction safeguards.')
p.write_text(s,encoding='utf-8')
for p in (root/'tests').rglob('*.py'):
    s=p.read_text(encoding='utf-8')
    import re
    s=re.sub(r'eps=[.\d]+, ?', '', s)
    s=re.sub(r'deduplicate_memories\(eps=[.\d]+\)', 'deduplicate_memories()', s)
    if p.name=='test_maintenance.py':
        s=s.replace('        dedup_stats = engine.deduplicate_memories(dry_run=False)\n        \n        # Both', '        dedup_stats = engine.deduplicate_memories(dry_run=False)\n        assert dedup_stats["merged"] == 0\n        # Both')
        s=s.replace('        ingest_t0 = time.perf_counter()\n','').replace('        ingest_duration = time.perf_counter() - ingest_t0\n','')
    p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/runner.py'
s=p.read_text(encoding='utf-8').replace('        key = benchmark_name.lower()', '        key = benchmark_name.lower()\n        if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):\n            raise ValueError("Invalid benchmark name.")')
p.write_text(s,encoding='utf-8')
