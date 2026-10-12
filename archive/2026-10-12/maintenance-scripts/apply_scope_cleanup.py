from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/vector_store/qdrant_store.py'
s=p.read_text(encoding='utf-8').replace('Distance, VectorParams, PointStruct, Filter, FieldCondition,','Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchAny,')
s+='''

def create_search_filter(query_time, mode="auto", document_ids=None):
    temporal = create_temporal_filter(query_time, mode)
    conditions = list(temporal.must or []) if temporal else []
    if document_ids is not None:
        conditions.append(FieldCondition(key="memory_id", match=MatchAny(any=document_ids)))
    return Filter(must=conditions) if conditions else None
'''
p.write_text(s,encoding='utf-8')
p=root/'memory/retrieval/vector.py'
s=p.read_text(encoding='utf-8').replace('temporal_mode: str = "auto"\n', 'temporal_mode: str = "auto",\n        document_ids: Optional[List[str]] = None\n')
s=s.replace('        if temporal_mode != "auto":\n            from memory.vector_store.qdrant_store import create_temporal_filter\n            import time\n            query_time = int(time.time()) if query_time is None else query_time\n            filter_condition = create_temporal_filter(query_time, temporal_mode)', '        from memory.vector_store.qdrant_store import create_search_filter\n        import time\n        query_time = int(time.time()) if query_time is None else query_time\n        filter_condition = create_search_filter(query_time, temporal_mode, document_ids)')
p.write_text(s,encoding='utf-8')
p=root/'memory/engine.py'
s=p.read_text(encoding='utf-8').replace('        retrieval_mode: str = "hybrid"\n', '        retrieval_mode: str = "hybrid",\n        document_ids: Optional[List[str]] = None\n',1)
s=s.replace('        if query_time is not None', '        if document_ids is not None and (not isinstance(document_ids, list) or any(not isinstance(mid, str) for mid in document_ids)):\n            raise ValueError("Document scope must be a list of memory IDs.")\n        if document_ids == []:\n            return []\n        if query_time is not None',1)
s=s.replace('.retrieve(query, k, q_time, temporal_mode)', '.retrieve(query, k, q_time, temporal_mode, document_ids)')
p.write_text(s,encoding='utf-8')
p=root/'memory/retrieval/hybrid.py'
s=p.read_text(encoding='utf-8').replace('def retrieve(self, query, k=None, query_time=None, temporal_mode="auto"):', 'def retrieve(self, query, k=None, query_time=None, temporal_mode="auto", document_ids=None):')
s=s.replace('from memory.vector_store.qdrant_store import create_temporal_filter', 'from memory.vector_store.qdrant_store import create_search_filter')
s=s.replace('filter_condition=create_temporal_filter(now, mode)', 'filter_condition=create_search_filter(now, mode, document_ids)')
s=s.replace('query, mode, query_embedding)', 'query, mode, query_embedding, document_ids)')
s=s.replace('temporal_mode="auto", query_embedding=None):', 'temporal_mode="auto", query_embedding=None, document_ids=None):')
s=s.replace('limit=self.config.graph_max_nodes, temporal_mode=temporal_mode)', 'limit=self.config.graph_max_nodes, temporal_mode=temporal_mode, memory_ids=document_ids)')
p.write_text(s,encoding='utf-8')
p=root/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8').replace('        temporal_mode: str = "now"\n', '        temporal_mode: str = "now",\n        memory_ids: Optional[List[str]] = None\n',1)
a=s.index('        result = self.conn.execute(f"""',s.index('    def get_observations('))
s=s[:a]+'''        time_parameter = {"time": valid_at} if predicate else {}
        scope_parameter = {"memory_ids": memory_ids} if memory_ids is not None else {}
        if memory_ids is not None:
            predicate += (" AND " if predicate else "WHERE ") + "o.source_memory_id IN $memory_ids"
''' +s[a:]
s=s.replace('{"eid": entity_id, "limit": limit, **({"time": valid_at} if predicate else {})}', '{"eid": entity_id, "limit": limit, **time_parameter, **scope_parameter}')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/evaluator.py'
s=p.read_text(encoding='utf-8').replace('            retrieval_mode=self.retrieval_mode\n', '            retrieval_mode=self.retrieval_mode,\n            document_ids=example.metadata.get("corpus_ids")\n',1)
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/longmemeval_adapter.py'
s=p.read_text(encoding='utf-8').replace('                        "raw_answer_session_ids":', '                        "corpus_ids": [f"longmemeval:{sid}" for sid in item.get("haystack_session_ids", [])],\n                        "raw_answer_session_ids":')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/locomo_adapter.py'
s=p.read_text(encoding='utf-8').replace('                            "raw_evidence": evidence_turns', '                            "raw_evidence": evidence_turns,\n                            "corpus_ids": [f"locomo:{sample_id}:{key}" for key, value in record.get("conversation", {}).items() if key.startswith("session_") and isinstance(value, list)]')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/runner.py'
s=p.read_text(encoding='utf-8')
s=s.replace('if set(e.ground_truth_ids) - document_ids]', 'if (set(e.ground_truth_ids) | set(e.metadata.get("corpus_ids", []))) - document_ids]')
p.write_text(s,encoding='utf-8')
p=root/'server.py'
s=p.read_text(encoding='utf-8').replace('"query_time", "retrieval_mode"}', '"query_time", "retrieval_mode", "document_ids"}')
p.write_text(s,encoding='utf-8')
