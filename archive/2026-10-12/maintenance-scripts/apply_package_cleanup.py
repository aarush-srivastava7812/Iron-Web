from pathlib import Path
root=Path(__file__).resolve().parents[1]
exports={
    'MemoryEngine':('memory.engine','MemoryEngine'),
    'MemoryRecord':('memory.models','MemoryRecord'),
    'MemorySearchResult':('memory.models','MemorySearchResult'),
    'DeviceStatus':('memory.models','DeviceStatus'),
    'EngineStorageError':('memory.models','EngineStorageError'),
    'MemoryToolAdapter':('memory.tool_adapter','MemoryToolAdapter'),
    'QdrantVectorStore':('memory.vector_store.qdrant_store','QdrantVectorStore'),
    'KuzuGraphStore':('memory.graph.kuzu_store','KuzuGraphStore'),
    'Embedder':('memory.embeddings.embedder','Embedder'),
    'get_embedder':('memory.embeddings.embedder','get_embedder'),
    'Reranker':('memory.ranking.reranker','Reranker'),
    'get_reranker':('memory.ranking.reranker','get_reranker'),
    'HybridRetriever':('memory.retrieval.hybrid','HybridRetriever'),
    'RetrievalConfig':('memory.ranking.scorer','RetrievalConfig'),
    'ScoringWeights':('memory.ranking.scorer','ScoringWeights'),
    'IngestionPipeline':('memory.ingestion.pipeline','IngestionPipeline'),
    'NIMExtractor':('memory.ingestion.nim_extractor','NIMExtractor'),
    'TemporalFilter':('memory.temporal.filter','TemporalFilter'),
    'ContradictionDetector':('memory.contradiction.detector','ContradictionDetector'),
    'MaintenanceScheduler':('memory.maintenance.maintenance','MaintenanceScheduler'),
}
def lazy_package(mapping, description):
    return f'''"""{description}"""
from importlib import import_module
_EXPORTS = {mapping!r}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value
'''
(root/'memory/__init__.py').write_text(lazy_package(exports,'Local vector/graph memory API. Optional models and clients are imported on demand.'),encoding='utf-8')
ingestion={name:(f'memory.ingestion.{module}',name) for name,module in (
    ('BaseExtractor','extractor'),('ExtractionResult','extractor'),('ExtractedEntity','extractor'),('ExtractedRelation','extractor'),
    ('ExtractedTemporal','extractor'),('validate_extraction','extractor'),('NIMExtractor','nim_extractor'),
    ('CachedNIMExtractor','cached_nim_extractor'),('IngestionPipeline','pipeline'))}
(root/'memory/ingestion/__init__.py').write_text(lazy_package(ingestion,'Extraction and ingestion interfaces with optional hosted clients.'),encoding='utf-8')
(root/'memory/graph/__init__.py').write_text('"""Embedded graph storage."""\nfrom memory.graph.kuzu_store import KuzuGraphStore, RelationType\n__all__ = ["KuzuGraphStore", "RelationType"]\n',encoding='utf-8')
for name in ('tests/__init__.py','tests/fixtures/__init__.py','research/__init__.py','research/retrievers/__init__.py','research/upstream/__init__.py'):
    p=root/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('"""Project-local package."""\n',encoding='utf-8')
for p in (root/'tests').rglob('*.py'):
    s=p.read_text(encoding='utf-8').replace('memory.ingestion.mock_nim_extractor','tests.fixtures.extractor')
    p.write_text(s,encoding='utf-8')
for name in ('memory/maintenance/maintenance.py','memory/contradiction/detector.py'):
    p=root/name
    s=p.read_text(encoding='utf-8').replace('from memory.graph import KuzuGraphStore, GraphStore','from memory.graph import KuzuGraphStore')
    s=s.replace('from memory.graph import GraphStore','from memory.graph import KuzuGraphStore').replace(': GraphStore',': KuzuGraphStore')
    s=s.replace('\nMaintenanceManager = MaintenanceScheduler\n','\n')
    p.write_text(s,encoding='utf-8')
p=root/'memory/graph/kuzu_store.py'
s=p.read_text(encoding='utf-8')
a=s.index('        # Create indexes for common queries');b=s.index('    # === Entity Operations ===',a)
s=s[:a]+s[b:]
p.write_text(s,encoding='utf-8')
for name in ('memory/embeddings/embedder.py','memory/ranking/reranker.py'):
    p=root/name
    s=p.read_text(encoding='utf-8').replace('from fastembed import TextEmbedding\n','').replace('from fastembed.rerank.cross_encoder import TextCrossEncoder\n','')
    method='    def _init_model(self):'
    a=s.index('        try:',s.index(method))
    import_line='        from fastembed import TextEmbedding\n' if 'embedder.py' in name else '        from fastembed.rerank.cross_encoder import TextCrossEncoder\n'
    s=s[:a]+import_line+s[a:]
    if 'embedder.py' in name:
        s=s.replace('        quantize: bool = True,  # INT8 quantization for speed/memory\n','').replace('    quantize: bool = True,\n','')
        s=s.replace('        self.quantize = quantize\n','').replace('                quantize=self.quantize\n','').replace('                    quantize=self.quantize\n','').replace('        quantize=quantize,\n','')
        s=s.replace('        self.dimension = 384','        from fastembed import TextEmbedding\n        self.dimension = next(m["dim"] for m in TextEmbedding.list_supported_models() if m["model"] == self.model_name)')
    else:
        s=s.replace('documents = [" ".join(cand.get("text", "").split()[:max_words]) for cand in candidates]', 'documents = [cand.get("text", "") for cand in candidates]')
        s=s.replace('        max_words = 256\n','')
        s=s.replace('        # Add scores to candidates','        if len(scores) != len(candidates) or not np.isfinite(scores).all():\n            raise RuntimeError("Reranker returned invalid or incomplete scores.")\n        # Add scores to candidates')
        a=s.index('    def score_pairs('); b=s.index('\ndef get_reranker(',a)
        s=s[:a]+s[b:]
    p.write_text(s,encoding='utf-8')
p=root/'memory/engine.py'
s=p.read_text(encoding='utf-8').replace('            quantize = emb_conf.get("quantize", True)\n','').replace('                quantize=quantize,\n','')
s=s.replace('                self.use_gpu = env_gpu.lower() == "true"','                if env_gpu.lower() not in {"true", "false"}:\n                    raise ValueError("USE_GPU must be true or false.")\n                self.use_gpu = env_gpu.lower() == "true"')
s=s.replace('    def search(\n', '    def search(\n',1)
s=s.replace('        modes = {"no_memory", "none", "vector", "graph", "hybrid", "hybrid_no_rerank", "hybrid_no_graph", "hybrid_no_temporal"}', '        modes = self.retrieval_modes')
s=s.replace('    def __init__(\n', '    retrieval_modes = frozenset({"no_memory", "none", "vector", "graph", "hybrid", "hybrid_no_rerank", "hybrid_no_graph", "hybrid_no_temporal"})\n\n    def __init__(\n',1)
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/runner.py'
s=p.read_text(encoding='utf-8').replace('retrieval_mode not in {"none", "no_memory", "vector", "graph", "hybrid", "hybrid_no_rerank", "hybrid_no_graph", "hybrid_no_temporal"}', 'retrieval_mode not in engine.retrieval_modes')
p.write_text(s,encoding='utf-8')
