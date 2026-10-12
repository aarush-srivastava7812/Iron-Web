from pathlib import Path
root=Path(__file__).resolve().parents[1]
for name in ('memory/embeddings/embedder.py','memory/ranking/reranker.py'):
    p=root/name
    s=p.read_text(encoding='utf-8')
    s=s.replace('# Global config flag\nUSE_GPU = os.getenv("USE_GPU", "false").lower() == "true"\n','')
    s=s.replace('# Global config flag\nUSE_GPU = os.getenv("USE_GPU", "false").lower() == "true"\n','')
    s=s.replace('self.use_gpu = use_gpu if use_gpu is not None else USE_GPU','self.use_gpu = use_gpu if use_gpu is not None else os.getenv("USE_GPU", "false").lower() == "true"')
    s=s.replace('    providers: Optional[List[str]] = None,\n','')
    a=s.find('    if providers is not None:')
    if a!=-1:
        b=s.index('    return ',a)
        s=s[:a]+s[b:]
    s=s.replace('        providers: ONNX Runtime providers (overrides use_gpu if provided)\n','')
    s=s.replace('            quantize: Enable INT8 quantization (4x memory reduction, <2% recall loss)\n','')
    s=s.replace('        quantize: Enable INT8 quantization\n','')
    s=s.replace('batch_size: Batch size for embedding (not used by FastEmbed directly)','batch_size: Batch size passed to FastEmbed')
    s=s.replace('        # Bound long conversational context before ONNX inference.  This is a\n        # token-safe approximation that avoids sending unbounded transcripts.','        # The model tokenizer applies its own sequence-length limit.')
    p.write_text(s,encoding='utf-8')
p=root/'memory/temporal/filter.py'
s=p.read_text(encoding='utf-8')
a=s.index('    """',s.index('def resolve_temporal_conflicts('));b=s.index('\n\nclass TemporalFilter',a)
s=s[:a]+'''    """Keep valid memories and deduplicate IDs; a shared entity does not imply a conflict."""
    valid = filter_by_time(candidates, query_time, "now")
    unique = {}
    for candidate in valid:
        mid = candidate.get("memory_id")
        if mid and (mid not in unique or candidate.get("final_score", candidate.get("score", 0)) > unique[mid].get("final_score", unique[mid].get("score", 0))):
            unique[mid] = candidate
    return list(unique.values())
''' +s[b:]
s=s.replace('Handles valid_from/valid_until bitemporal logic.','Applies explicit fact-validity intervals independently of record creation time.')
s=s.replace('Weight = exp(-age_days / half_life_days)','Weight = 2 ** (-age_days / half_life_days)')
p.write_text(s,encoding='utf-8')
p=root/'memory/vector_store/qdrant_store.py'
s=p.read_text(encoding='utf-8')
for line in ('            quantization: Enable scalar INT8 quantization\n','            hnsw_m: HNSW M parameter (connections per node)\n','            hnsw_ef_construct: HNSW ef_construct parameter\n'):
    s=s.replace(line,'')
p.write_text(s,encoding='utf-8')
