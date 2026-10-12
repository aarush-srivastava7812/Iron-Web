from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8')
s=s.replace('        limit: int = 50\n', '        limit: int = 50,\n        temporal_mode: str = "now"\n',1)
a=s.index('        result = self.conn.execute("""',s.index('    def get_observations('))
s=s[:a]+'''        if temporal_mode not in {"now", "historical", "auto"} or limit < 1:
            raise ValueError("Invalid observation query.")
        predicate = {"now": "WHERE o.valid_from <= $time AND o.valid_until >= $time",
                     "historical": "WHERE o.valid_until < $time", "auto": ""}[temporal_mode]
''' +s[a:]
a=s.index('        result = self.conn.execute("""',s.index('    def get_observations('))
b=s.index('        obs = []',a)
block=s[a:b].replace('self.conn.execute("""','self.conn.execute(f"""').replace('{id: $eid}', '{{id: $eid}}')
block=block.replace('WHERE o.valid_from <= $time AND o.valid_until >= $time', '{predicate}')
s=s[:a]+block+s[b:]
a=s.index('    def expand_graph(')
b=s.index('    # === Contradiction/Supersession ===',a)
s=s[:a]+'''    def expand_graph(self, seed_entity_ids, hops=2, relation_types=None, valid_at=None,
                     include_relations=True, max_nodes=50, temporal_mode="now"):
        """Bounded breadth-first expansion includes seeds and every depth up to two."""
        import time
        if hops not in (1, 2) or max_nodes < 1 or temporal_mode not in {"now", "historical", "auto"}:
            raise ValueError("Invalid graph expansion settings.")
        if not seed_entity_ids:
            return [], []
        now = int(time.time()) if valid_at is None else valid_at
        entities = {}
        for eid in sorted(set(seed_entity_ids))[:max_nodes]:
            entity = self.get_entity(eid)
            if entity:
                entities[eid] = entity
        frontier, relations = list(entities), {}
        predicate = {"now": "AND r.valid_from <= $time AND r.valid_until >= $time",
                     "historical": "AND r.valid_until < $time", "auto": ""}[temporal_mode]
        types = "AND r.relation_type IN $types" if relation_types else ""
        for _ in range(hops):
            if not frontier:
                break
            result = self.conn.execute(f"""
                MATCH (e:Entity)-[r:RELATES]-(n:Entity)
                WHERE e.id IN $ids {predicate} {types}
                RETURN n.id, n.name, n.entity_type, n.description, n.importance, n.created_at, n.updated_at,
                       e.id, r.relation_type, r.confidence, r.valid_from, r.valid_until, r.created_at, r.updated_at, r.metadata
                ORDER BY n.id LIMIT $limit
            """, {"ids": frontier, "time": now, "types": relation_types or [], "limit": max_nodes*4})
            next_frontier = []
            while result.has_next():
                row = result.get_next()
                eid = row[0]
                if eid not in entities:
                    if len(entities) >= max_nodes:
                        continue
                    entities[eid] = dict(zip(("id", "name", "entity_type", "description", "importance", "created_at", "updated_at"), row[:7]))
                    next_frontier.append(eid)
                if include_relations:
                    key = (row[7], eid, row[8])
                    relations[key] = dict(from_id=row[7], to_id=eid, relation_type=row[8], confidence=row[9],
                        valid_from=row[10], valid_until=row[11], created_at=row[12], updated_at=row[13], metadata=row[14])
            frontier = next_frontier
        return list(entities.values()), list(relations.values())

''' +s[b:]
p.write_text(s,encoding='utf-8')

p=root/'memory/engine.py'
s=p.read_text(encoding='utf-8')
a=s.index('        if not query or not query.strip():',s.index('    def search('))
b=s.index('    def update(',a)
s=s[:a]+'''        if not isinstance(query, str):
            raise ValueError("Query must be a string.")
        if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= 100:
            raise ValueError("Result count must be between 1 and 100.")
        if temporal_mode not in {"auto", "now", "historical"}:
            raise ValueError("Unknown temporal mode.")
        modes = {"no_memory", "none", "vector", "graph", "hybrid", "hybrid_no_rerank", "hybrid_no_graph", "hybrid_no_temporal"}
        if retrieval_mode not in modes:
            raise ValueError(f"Unknown retrieval mode: {retrieval_mode}")
        if not query.strip() or retrieval_mode in {"no_memory", "none"}:
            return []
        q_time = int(time.time()) if query_time is None else query_time
        if retrieval_mode == "vector":
            hits = VectorRetriever(self.embedder, self.vector_store).retrieve(query, k, q_time, temporal_mode)
        else:
            settings = self.config_data.get("retrieval", {})
            use_rerank = retrieval_mode not in {"graph", "hybrid_no_rerank"} and settings.get("reranker_enabled", False)
            ret_conf = RetrievalConfig(final_top_k=k, use_vector=retrieval_mode != "graph",
                use_graph_expansion=retrieval_mode != "hybrid_no_graph", use_reranker=use_rerank,
                use_temporal_filter=retrieval_mode != "hybrid_no_temporal", default_query_time=q_time,
                vector_candidates=settings.get("vector_candidates", 100), graph_hops=settings.get("graph_hops", 2),
                graph_max_nodes=settings.get("graph_max_nodes", 50),
                use_entity_lookup_cache=settings.get("entity_lookup_cache", True),
                weights=ScoringWeights(**settings.get("weights", {})))
            hits = HybridRetriever(self.embedder, self.vector_store, self.graph_store,
                self.reranker if use_rerank else None, ret_conf).retrieve(query, k, q_time, temporal_mode)
        return [self._search_result(hit, retrieval_mode) for hit in hits]

    @staticmethod
    def _search_result(hit, mode):
        payload = hit.get("payload", {})
        return MemorySearchResult(memory_id=hit["memory_id"], content=hit.get("text", payload.get("text", "")),
            score=float(hit.get("final_score", hit.get("score", 0))),
            metadata={key: value for key, value in payload.items() if key not in {"text", "memory_id", "entity_ids"}},
            entity_ids=payload.get("entity_ids", []), retrieval_method=hit.get("retrieval_method", mode),
            timestamp=payload.get("timestamp"), valid_from=payload.get("valid_from"), valid_until=payload.get("valid_until"),
            importance=payload.get("importance"), is_superseded=bool(hit.get("superseded", False)),
            retrieval_trace=hit.get("retrieval_trace", {}))

''' +s[b:]
s=s.replace('from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig', 'from memory.retrieval.hybrid import HybridRetriever, RetrievalConfig\nfrom memory.ranking.scorer import ScoringWeights')
p.write_text(s,encoding='utf-8')

p=root/'memory/retrieval/vector.py'
s=p.read_text(encoding='utf-8')
s=s.replace('if self.use_temporal_filter and query_time is not None:', 'if temporal_mode != "auto":\n            import time\n            query_time = int(time.time()) if query_time is None else query_time')
p.write_text(s,encoding='utf-8')
for name in ('memory/models.py','memory/ingestion/extractor.py','memory/vector_store/qdrant_store.py','memory/temporal/filter.py'):
    p=root/name
    s=p.read_text(encoding='utf-8').replace('2**31 - 1','2**63 - 1')
    if name.endswith('qdrant_store.py'):
        s=s.replace('    if mode == "now":', '    if mode not in {"now", "historical", "auto"}:\n        raise ValueError("Unknown temporal mode.")\n    if mode == "now":')
    if name.endswith('filter.py'):
        s=s.replace('if mode == "all":', 'if mode not in {"now", "historical", "auto", "all"}:\n        raise ValueError("Unknown temporal mode.")\n    if mode in {"all", "auto"}:')
        s=s.replace("float(__import__('math').exp(-age_days / half_life_days))", 'float(2 ** (-age_days / half_life_days))')
    p.write_text(s,encoding='utf-8')
