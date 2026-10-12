from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/vector_store/qdrant_store.py'
s=p.read_text(encoding='utf-8').replace('import uuid','import uuid\nfrom copy import deepcopy')
s=s.replace('    ScalarQuantization, ScalarQuantizationConfig, ScalarType\n','')
s=s.replace('        quantization: bool = True,  # Scalar INT8 quantization\n        hnsw_m: int = 16,\n        hnsw_ef_construct: int = 100,\n','')
s=s.replace('        self._create_collection(quantization, hnsw_m, hnsw_ef_construct)', '        try:\n            self._create_collection()\n        except Exception:\n            self.client.close()\n            raise')
a=s.index('    def _create_collection(');b=s.index('    def _memory_id_to_uuid(',a)
s=s[:a]+'''    def _create_collection(self):
        """Embedded Qdrant performs exact search; server-only index knobs are omitted."""
        collections = self.client.get_collections().collections
        if any(collection.name == self.collection_name for collection in collections):
            vectors = self.client.get_collection(self.collection_name).config.params.vectors
            if not isinstance(vectors, VectorParams) or vectors.size != self.dimension or vectors.distance != self.distance:
                raise ValueError("Existing collection dimensions or distance differ from configuration.")
        else:
            self.client.create_collection(collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=self.distance))

''' +s[b:]
s=s.replace('payload.update(metadata)', 'payload.update(deepcopy(metadata))')
s=s.replace('"payload": hit.payload','"payload": deepcopy(hit.payload)').replace('"payload": p.payload','"payload": deepcopy(p.payload)')
s=s.replace('# Max int32 = "forever"','# Unbounded application sentinel within INT64')
p.write_text(s,encoding='utf-8')
p=root/'memory/contradiction/detector.py'
s=p.read_text(encoding='utf-8')
a=s.index('    def _llm_judge_contradiction(');b=s.index('    def store_contradiction(',a)
s=s[:a]+'''    def _llm_judge_contradiction(self, text1, text2):
        if self.extractor is None or not hasattr(self.extractor, "detect_contradiction"):
            raise ValueError("Contradiction detection requires an explicit compatible extractor.")
        return self.extractor.detect_contradiction(text1, text2)

    def _llm_judge_supersession(self, new_text, old_text):
        if self.extractor is None or not hasattr(self.extractor, "detect_supersession"):
            raise ValueError("Supersession detection requires an explicit compatible extractor.")
        return self.extractor.detect_supersession(old_text=old_text, new_text=new_text)

''' +s[b:]
p.write_text(s,encoding='utf-8')
p=root/'memory/engine.py'
s=p.read_text(encoding='utf-8').replace('import uuid','import uuid\nfrom copy import deepcopy')
s=s.replace('meta = metadata.copy() if metadata else {}','meta = deepcopy(metadata) if metadata else {}')
s=s.replace('uuid.uuid4().hex[:12]','uuid.uuid4().hex')
s=s.replace('        if entity_ids is not None:\n            for eid', '        if entity_ids is not None:\n            meta.update(extraction_status="explicit_entities", extraction_is_mock=False, extractor_name="manual")\n            for eid',1)
s=s.replace('            if raw is not None:', '            meta["extraction_is_mock"] = False\n            meta["extractor_name"] = "disabled"\n            if raw is not None:',1)
s=s.replace('result = validate_extraction(raw, is_mock=meta["extraction_is_mock"]).to_dict()', 'result = validate_extraction(raw, extractor_name=raw.get("extractor_name", type(selected).__name__), is_mock=meta["extraction_is_mock"]).to_dict()\n                meta["extractor_name"] = result["extractor_name"]')
s=s.replace('                    timestamp=ts\n                )\n            \n            # 4c.', '                    timestamp=ts,\n                    metadata={"source_memory_id": mem_id}\n                )\n            \n            # 4c.')
s=s.replace('        if document_ids == []:\n            return []\n','')
s=s.replace('        if not query.strip() or retrieval_mode in {"no_memory", "none"}:','        if not query.strip() or document_ids == [] or retrieval_mode in {"no_memory", "none"}:')
# Automatic links are recomputed after a content change through the same ingestion service.
a=s.index('        # Re-embed if content changed',s.index('    def update('))
s=s[:a]+'''        if content is not None and content != old_payload.get("text") and old_payload.get("extraction_status") == "completed":
            self.add(new_text, metadata=new_meta, timestamp=old_payload.get("timestamp"),
                valid_from=new_valid_from, valid_until=new_valid_until, importance=new_importance, memory_id=memory_id)
            return True
''' +s[a:]
# Maintenance previews and operations without synthesis must not instantiate optional models.
s=s.replace('embedder=self._embedder if dry_run else self.embedder','embedder=self._embedder if dry_run else (lambda: self.embedder)')
s=s.replace('embedder=self.embedder if needs_models else self._embedder','embedder=(lambda: self.embedder) if needs_models else self._embedder')
# Status collection uses the same shared lock as mutations.
a=s.index('    @serialized\n    def memory_ids(')
s=s[:a]+'''    @serialized
    def storage_status(self):
        return dict(memories=self.vector_store.count(), nodes=self.graph_store.get_node_counts(), edges=self.graph_store.get_edge_counts())

''' +s[a:]
p.write_text(s,encoding='utf-8')
p=root/'memory/maintenance/maintenance.py'
s=p.read_text(encoding='utf-8')
s=s.replace('payload.get("valid_until", 2**63-1), payload.get("memory_type", "semantic"))', 'payload.get("valid_until", 2**63-1), payload.get("memory_type", "semantic"),\n                   tuple(payload.get(key) for key in ("user_id", "session_id", "benchmark", "sample_id")),\n                   payload.get("timestamp") if payload.get("memory_type") in {"episodic", "procedural"} else None)')
s=s.replace('merged_meta["merged_records"] = [{', 'merged_meta["merged_records"] = list(merged_meta.get("merged_records", [])) + [{')
s=s.replace('        embedding = self.embedder.embed_single(text)', '        embedder = self.embedder() if callable(self.embedder) and not hasattr(self.embedder, "embed_single") else self.embedder\n        embedding = embedder.embed_single(text)')
s=s.replace('metadata={"skill_data": skill, "provenance": skill.get("provenance", {})}', 'metadata={"skill_data": skill, "provenance": skill.get("provenance", {}), "source": "consolidation", "extraction_is_mock": bool(getattr(self.extractor, "is_mock", False))}')
p.write_text(s,encoding='utf-8')
p=root/'memory/retrieval/hybrid.py'
s=p.read_text(encoding='utf-8').replace('now = int(time.time()) if query_time is None else query_time', 'now = query_time if query_time is not None else (self.config.default_query_time if self.config.default_query_time is not None else int(time.time()))')
p.write_text(s,encoding='utf-8')
p=root/'memory/models.py'
s=p.read_text(encoding='utf-8')
a=s.index('class MemoryMetadata(');b=s.index('class MemoryRecord(',a)
s=s[:a]+s[b:]
a=s.index('class SearchFilter(');b=s.index('class DeviceStatus(',a)
s=s[:a]+s[b:]
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/metrics.py'
s=p.read_text(encoding='utf-8')
a=s.index('# === LLM-as-Judge');b=s.index('def evaluate_retrieval(',a)
s=s[:a]+s[b:]
p.write_text(s,encoding='utf-8')
p=root/'server.py'
s=p.read_text(encoding='utf-8').replace('storage=dict(memories=engine.vector_store.count(), nodes=engine.graph_store.get_node_counts())','storage=engine.storage_status()')
s=s.replace('def run_server(port=8080):\n', 'def run_server(port=8080):\n    global _ENGINE\n')
s=s.replace('            _ENGINE.close()\n', '            _ENGINE.close()\n            _ENGINE = None\n')
p.write_text(s,encoding='utf-8')
