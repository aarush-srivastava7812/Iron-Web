from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/engine.py'
s=p.read_text(encoding='utf-8')
s=s.replace('- Safe GPU Integration (RTX 4050 6GB Profile, 1GB Safety Buffer)','- Optional GPU execution with observed provider and memory telemetry')
s=s.replace('        self.config_data = self._load_config(config)', '        self.config_data = self._load_config(config)\n        if use_gpu is not None and not isinstance(use_gpu, bool):\n            raise ValueError("GPU preference must be a boolean.")')
s=s.replace('        # 3. Storage stores', '        self.config_data["qdrant"]["path"] = self.qdrant_path\n        self.config_data["kuzu"]["path"] = self.kuzu_path\n        # 3. Storage stores',1)
s=s.replace('        return EngineSettings.model_validate(raw or {}).model_dump()', '''        resolved = EngineSettings.model_validate(raw or {}).model_dump()
        base = Path(config_input).resolve().parent if isinstance(config_input, str) else Path(__file__).resolve().parents[1]
        for section, keys in (("qdrant", ("path",)), ("kuzu", ("path",)), ("embeddings", ("cache_dir",)),
                              ("reranker", ("cache_dir", "tensorrt_cache_path")), ("nim", ("cache_dir",))):
            for key in keys:
                if resolved[section].get(key) is not None:
                    value = Path(resolved[section][key]).expanduser()
                    resolved[section][key] = str(value if value.is_absolute() else (base/value).resolve())
        return resolved''')
s=s.replace('        return self._embedder\n', '        if hasattr(self, "vector_store") and self.vector_store._embedder is None:\n            self.vector_store._embedder = self._embedder\n        return self._embedder\n',1)
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/evaluator.py'
s=p.read_text(encoding='utf-8')
s=s.replace('        if hasattr(self.engine, "ingest_documents"):', '        if self.retrieval_mode in {"none", "no_memory"}:\n            return dict(num_documents=len(documents), ingested_ids=0, skipped_reason="no_memory_baseline", ingestion_time_sec=0.)\n        if hasattr(self.engine, "ingest_documents"):',1)
s=s.replace('                if existing and existing.content', '''                selected = self.engine.extractor
                expected_mock = bool(getattr(selected, "is_mock", False))
                expected_status = "disabled" if selected is None else "completed"
                provenance_matches = existing and existing.metadata.get("extraction_is_mock") is expected_mock and existing.metadata.get("extraction_status") == expected_status
                if provenance_matches and existing.content''',1)
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/runner.py'
s=p.read_text(encoding='utf-8').replace('extractor = engine.extractor','extractor = None if retrieval_mode in {"none", "no_memory"} else engine.extractor')
s=s.replace('config=engine.config_data,','config=engine.config_data, backend_identity=getattr(engine, "evaluation_identity", {}),')
p.write_text(s,encoding='utf-8')
p=root/'research/engine.py'
s=p.read_text(encoding='utf-8')
a=s.index('    @serialized')
s=s[:a]+'''    @property
    def evaluation_identity(self):
        from memory.evaluation.harness.persistence import source_fingerprint
        return {"research_source": source_fingerprint(("research",))}

''' +s[a:]
p.write_text(s,encoding='utf-8')
for name in ('memory/config.py','config.yaml'):
    p=root/name
    s=p.read_text(encoding='utf-8').replace('meta/llama-3.1-70b-instruct','meta/llama-3.2-11b-vision-instruct')
    p.write_text(s,encoding='utf-8')
