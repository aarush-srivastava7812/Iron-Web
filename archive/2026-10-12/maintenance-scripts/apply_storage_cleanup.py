from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / 'memory/vector_store/qdrant_store.py'
s = p.read_text(encoding='utf-8')
a = s.index('    def _create_payload_indexes(')
b = s.index('    def _memory_id_to_uuid(', a)
s = s[:a] + s[b:]
a = s.index('        try:\n', s.index('    def get_memory('))
b = s.index('        return None', a)
block = s[a:b]
block = block[block.index('            points ='):block.index('        except Exception:')]
s = s[:a] + ''.join(line[4:] if line.startswith('    ') else line for line in block.splitlines(True)) + s[b:]
p.write_text(s, encoding='utf-8')

p = root / 'memory/engine.py'
s = p.read_text(encoding='utf-8')
s = s.replace('from memory.vector_store.qdrant_store import QdrantVectorStore', 'from memory.vector_store.qdrant_store import QdrantVectorStore, validate_metadata\nfrom memory.storage import coordinated_write')
s = s.replace('        meta = metadata.copy() if metadata else {}', '        validate_metadata(metadata)\n        meta = metadata.copy() if metadata else {}')
# Place both writes in the same coordinator; graph mutations roll back as a unit.
a = s.index('        # 3. Store in Qdrant (Vector Store)')
b = s.index('        return mem_id', a)
block = s[a:b]
q = block[:block.index('        # 4. Store in')]
g = block[block.index('            # 4a.'):block.index('        except Exception as e:')]
g = ''.join(line[4:] if line.startswith('    ') else line for line in g.splitlines(True))
body = '        self.graph_store.delete_memory(mem_id)\n' + q + g
s = s[:a] + '        with coordinated_write(self.vector_store, self.graph_store, [mem_id]):\n' + ''.join('    ' + line if line.strip() else line for line in body.splitlines(True)) + '\n' + s[b:]
a = s.index('        # 1. Update Qdrant', s.index('    def update('))
b = s.index('        return True', a)
block = s[a:b]
q = block[:block.index('        # 2. Update')]
g = block[block.index('            entity_ids ='):block.index('        except Exception as e:')]
g = ''.join(line[4:] if line.startswith('    ') else line for line in g.splitlines(True))
g = g.replace('timestamp=int(time.time())', 'source=new_meta.get("source", "user"),\n                    source_memory_id=memory_id,\n                    timestamp=old_payload.get("timestamp", int(time.time()))')
body = q + g
s = s[:a] + '        with coordinated_write(self.vector_store, self.graph_store, [memory_id]):\n' + ''.join('    '+line if line.strip() else line for line in body.splitlines(True)) + '\n' + s[b:]
s = s.replace('        if metadata:\n            new_meta.update(metadata)', '        validate_metadata(metadata)\n        if metadata:\n            new_meta.update(metadata)')
a = s.index('        qdrant_deleted =', s.index('    def delete('))
b = s.index('        return bool(qdrant_deleted or kuzu_deleted)', a)
body=s[a:b]
s=s[:a]+'        with coordinated_write(self.vector_store, self.graph_store, [memory_id]):\n'+''.join('    '+line if line.strip() else line for line in body.splitlines(True))+s[b:]
s=s.replace('        if metadatas is None:', '        if metadatas is not None and len(metadatas) != len(contents):\n            raise ValueError("Batch content and metadata lengths differ.")\n        if timestamps is not None and len(timestamps) != len(contents):\n            raise ValueError("Batch content and timestamp lengths differ.")\n        if metadatas is None:',1)
s=s.replace('graph_stored=True', 'graph_stored=bool(self.graph_store.get_memory_observations(memory_id))')
p.write_text(s, encoding='utf-8')
