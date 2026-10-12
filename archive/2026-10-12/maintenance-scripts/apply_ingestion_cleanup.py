from pathlib import Path
root = Path(__file__).resolve().parents[1]
p = root/'memory/engine.py'
s = p.read_text(encoding='utf-8')
s = s.replace('from memory.ingestion.mock_nim_extractor import MockNIMExtractor', 'from memory.ingestion.extractor import validate_extraction, canonicalize_entities')
a = s.index('        """Access extractor', s.index('    def extractor('))
b = s.index('    def _init_vector_store(', a)
s = s[:a] + '''        """Use only an explicitly selected extractor; failures never fabricate data."""
        if self._extractor is None and self.config_data.get("extraction_policy", "none") == "nim":
            from memory.ingestion.cached_nim_extractor import CachedNIMExtractor
            conf = self.config_data.get("nim", {})
            self._extractor = CachedNIMExtractor(cache_dir=conf.get("cache_dir"),
                api_key=os.getenv("NVIDIA_API_KEY"), base_url=conf.get("base_url"),
                model=conf.get("extractor_model", "meta/llama-3.1-70b-instruct"))
        return self._extractor

''' + s[b:]
s = s.replace('embedder=self.embedder,\n            dimension=dim', 'embedder=self._embedder,\n            dimension=dim')
s = s.replace('        memory_id: Optional[str] = None\n', '        memory_id: Optional[str] = None,\n        extraction: Optional[Dict[str, Any]] = None\n', 1)
a = s.index('        else:\n            try:', s.index('    def add('))
b = s.index('        assigned_entity_ids =', a)
s = s[:a] + '''        else:
            selected = self.extractor if extraction is None else None
            raw = extraction if extraction is not None else (
                selected.extract_entities_and_relations(content) if selected is not None else None)
            meta["extraction_status"] = "disabled" if raw is None else "completed"
            if raw is not None:
                meta["extraction_is_mock"] = bool(getattr(selected, "is_mock", raw.get("is_mock", False)))
                raw = canonicalize_entities(raw)
                result = validate_extraction(raw, is_mock=meta["extraction_is_mock"]).to_dict()
                resolved_entities, resolved_relations = result["entities"], result["relations"]
                if valid_from == 0:
                    valid_from = result["temporal"]["valid_from"]
                if valid_until == 2**63 - 1:
                    valid_until = result["temporal"]["valid_until"]
                if importance == 1.0:
                    importance = result["importance"]

''' + s[b:]
# Future default expiration; old stored 2038 bounds remain actual finite bounds.
s = s.replace('2**31 - 1', '2**63 - 1')
p.write_text(s, encoding='utf-8')

p = root/'memory/ingestion/nim_extractor.py'
s = p.read_text(encoding='utf-8')
a = s.index('        # Truncated-JSON salvage:')
b = s.index('    def _normalize_extraction(', a)
s = s[:a] + '        raise ValueError("Extraction response did not contain a complete JSON object.")\n\n' + s[b:]
s = s.replace('from memory.ingestion.extractor import BaseExtractor, validate_extraction', 'from memory.ingestion.extractor import BaseExtractor, validate_extraction, canonicalize_entities')
a = s.index('        entities =', s.index('    def _normalize_extraction('))
b = s.index('    @retry(', a)
s = s[:a] + '        return canonicalize_entities(raw)\n\n' + s[b:]
s = s.replace('episode_texts[:20]', 'episode_texts')
s = s.replace('Output JSON array of skills:', 'Output a JSON object with a skills array:')
s = s.replace('[{{"name": "...", "description": "...", "conditions": "...", "actions": "..."}}]', '{{"skills": [{{"name": "...", "description": "...", "conditions": "...", "actions": "..."}}]}}')
s = s.replace('2147483647', '9223372036854775807')
p.write_text(s, encoding='utf-8')

p=root/'memory/ingestion/pipeline.py'
p.write_text('''"""Compatibility ingestion adapter; all storage writes go through MemoryEngine."""
from pathlib import Path


class IngestionPipeline:
    def __init__(self, embedder, vector_store, graph_store, extractor=None, contradiction_detector=None):
        from memory.engine import MemoryEngine
        self.engine = MemoryEngine(config={"extraction_policy": "none"}, embedder=embedder,
            vector_store=vector_store, graph_store=graph_store, extractor=extractor)
        self.contradiction_detector = contradiction_detector

    def ingest_text(self, text, memory_id=None, metadata=None, timestamp=None):
        return self.ingest_text_with_extraction(text, memory_id, metadata, timestamp)

    def ingest_text_with_extraction(self, text, memory_id=None, metadata=None, timestamp=None, extraction=None):
        mid = self.engine.add(text, memory_id=memory_id, metadata=metadata, timestamp=timestamp, extraction=extraction)
        if self.contradiction_detector:
            own = self.engine.graph_store.get_memory_observations(mid)
            own_ids = {o["id"] for o in own}
            for observation in own:
                candidates = self.engine.graph_store.get_observations(observation["entity_id"], valid_at=timestamp)
                conflicts = self.contradiction_detector.detect_contradictions(observation["id"], text,
                    [observation["entity_id"]], [o["id"] for o in candidates if o["id"] not in own_ids])
                for conflict in conflicts:
                    self.contradiction_detector.store_contradiction(conflict)
        return mid

    def ingest_batch(self, texts, metadata_list=None, timestamp=None):
        if metadata_list is not None and len(metadata_list) != len(texts):
            raise ValueError("Content and metadata lengths differ.")
        return self.engine.add_batch(texts, metadatas=metadata_list, timestamps=[timestamp]*len(texts))

    def ingest_from_file(self, file_path, chunk_size=1000, chunk_overlap=200):
        return self.ingest_batch(self._chunk_text(Path(file_path).read_text(encoding="utf-8"), chunk_size, chunk_overlap))

    @staticmethod
    def _chunk_text(text, chunk_size, overlap):
        if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("Chunk size must be positive, with overlap smaller than the chunk.")
        chunks, start = [], 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = end - overlap
        return chunks
''', encoding='utf-8')
