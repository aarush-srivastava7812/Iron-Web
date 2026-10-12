from pathlib import Path
p=Path(__file__).resolve().parents[1]/'memory/engine.py'
s=p.read_text(encoding='utf-8')
s=s.replace('import yaml', 'import yaml\nfrom threading import RLock\nfrom functools import wraps')
a=s.index('class MemoryEngine:')
s=s[:a]+'''def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._operation_lock:
            if self._closed and method.__name__ != "close":
                raise RuntimeError("Memory engine is closed.")
            return method(self, *args, **kwargs)
    return call


''' +s[a:]
s=s.replace('        # 1. Load and resolve configuration', '        self._operation_lock = RLock()\n        self._closed = False\n        # 1. Load and resolve configuration',1)
for name in ('add','add_batch','get','search','update','delete','decay_memories','deduplicate_memories','consolidate_memories','run_maintenance','close'):
    s=s.replace(f'    def {name}(',f'    @serialized\n    def {name}(',1)
s=s.replace('        if not isinstance(content, str) or not content.strip():\n            raise ValueError("Memory content cannot be empty.")', '''        from memory.validation import MemoryInput
        checked = MemoryInput(content=content, metadata=metadata, entity_ids=entity_ids, timestamp=timestamp,
            valid_from=valid_from, valid_until=valid_until, importance=importance, memory_id=memory_id)
        entity_ids = checked.entity_ids''',1)
s=s.replace('        if entity_ids:\n            for eid', '        if entity_ids is not None:\n            for eid',1)
s=s.replace('        if not isinstance(query, str):', '        if query_time is not None and (not isinstance(query_time, int) or isinstance(query_time, bool)):\n            raise ValueError("Reference timestamp must be an integer.")\n        if not isinstance(query, str):',1)
s=s.replace('        old_point = self.vector_store.get_memory(memory_id)', '''        if content is not None and (not isinstance(content, str) or not content.strip()):
            raise ValueError("Memory content must be nonempty text.")
        old_point = self.vector_store.get_memory(memory_id)''',1)
s=s.replace('        # Re-embed if content changed', '''        from memory.validation import MemoryInput
        MemoryInput(content=new_text, metadata=new_meta, importance=new_importance,
                    valid_from=new_valid_from, valid_until=new_valid_until, memory_id=memory_id)
        # Re-embed if content changed''',1)
s=s.replace('else (now + 300)', 'else now')
s=s.replace('Identify and merge semantically duplicate memories using DBSCAN clustering.', 'Merge identical text, memory type and validity intervals; retain distinct similar facts.')
s=s.replace('            embedder=self.embedder,\n            eps=eps', '            embedder=self._embedder,\n            eps=eps')
a=s.index('        """Close vector and graph',s.index('    def close('))
b=s.index('    def __enter__(',a)
s=s[:a]+'''        """Close both stores, reporting any failure, and allow repeated close calls."""
        if self._closed:
            return
        errors = []
        for store in (self.vector_store, self.graph_store):
            try:
                store.close()
            except Exception as error:
                errors.append(error)
        self._closed = True
        if errors:
            raise ExceptionGroup("Memory store close failed", errors)

''' +s[b:]
p.write_text(s,encoding='utf-8')
