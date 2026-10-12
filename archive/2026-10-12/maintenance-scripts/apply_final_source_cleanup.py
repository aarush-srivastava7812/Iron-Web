from pathlib import Path
root=Path(__file__).resolve().parents[1]
for name, key in (('longmemeval','haystack_sessions'),('locomo','conversation')):
    p=root/f'memory/evaluation/harness/{name}_adapter.py'
    s=p.read_text(encoding='utf-8')
    marker='    def _parse_date_to_timestamp('
    a=s.index(marker)
    s=s[:a]+'''    def _read_data(self):
        if not hasattr(self, "_data"):
            self._data = json.loads(self.resolved_path.read_text(encoding="utf-8"))
            if not isinstance(self._data, list):
                raise ValueError("Benchmark source must be a records array.")
        return self._data

    @property
    def _official_format(self):
        records = self._read_data()
        return bool(records and "'''+key+'''" in records[0])

''' +s[a:]
    old='if self.resolved_path.name.endswith(".json") and "s_cleaned" in self.resolved_path.name:' if name=='longmemeval' else 'if self.resolved_path.name.endswith(".json") and "locomo10" in self.resolved_path.name:'
    s=s.replace(old,'if self._official_format:')
    s=s.replace('json.loads(self.resolved_path.read_text(encoding="utf-8"))','self._read_data()')
    # Avoid making the new reader recursive.
    s=s.replace('            self._data = self._read_data()', '            self._data = json.loads(self.resolved_path.read_text(encoding="utf-8"))')
    if name=='locomo':
        # Evidence IDs refer to actual dialog IDs, not an assumed session number.
        a=s.index('                    evidence_sessions = []');b=s.index('                    ex = BenchmarkExample(',a)
        s=s[:a]+'''                    evidence_to_session = {}
                    for session_key, turns in record.get("conversation", {}).items():
                        if session_key.startswith("session_") and isinstance(turns, list):
                            for turn in turns:
                                if turn.get("dia_id"):
                                    evidence_to_session[turn["dia_id"]] = f"locomo:{sample_id}:{session_key}"
                    evidence_sessions = [evidence_to_session[ev] for ev in evidence_turns if ev in evidence_to_session]
                    unmapped = [ev for ev in evidence_turns if ev not in evidence_to_session]

''' +s[b:]
        s=s.replace('"raw_evidence": evidence_turns,', '"raw_evidence": evidence_turns,\n                            "unmapped_evidence": unmapped,')
    p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/runner.py'
s=p.read_text(encoding='utf-8').replace('if (set(e.ground_truth_ids) | set(e.metadata.get("corpus_ids", []))) - document_ids]', 'if (set(e.ground_truth_ids) | set(e.metadata.get("corpus_ids", []))) - document_ids or e.metadata.get("unmapped_evidence")]')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/base.py'
s=p.read_text(encoding='utf-8')+'\n__all__ = ["BenchmarkAdapter", "BenchmarkDocument", "BenchmarkExample", "EvaluationResult", "normalize_answer", "compute_exact_match", "compute_token_f1", "compute_substring_match", "compute_retrieval_metrics", "recall_at_k", "precision_at_k", "mean_reciprocal_rank", "ndcg_at_k"]\n'
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/official_corpora.py'
p.write_text('''"""Document dictionaries backed by the canonical benchmark adapters."""
from dataclasses import asdict
from memory.evaluation.harness.locomo_adapter import LoCoMoAdapter
from memory.evaluation.harness.longmemeval_adapter import LongMemEvalAdapter


def _convert(documents, examples):
    return ([dict(id=d.doc_id, text=d.text, metadata=dict(d.metadata, timestamp=d.timestamp)) for d in documents],
            [dict(query_id=e.example_id, text=e.query, ground_truth_ids=e.ground_truth_ids, answer=e.gold_answer, metadata=e.metadata) for e in examples])


def load_official_locomo():
    adapter = LoCoMoAdapter()
    return _convert(adapter.load_documents(), adapter.load_examples())


def load_official_longmemeval(question_limit=50):
    if question_limit < 1:
        raise ValueError("Question limit must be positive.")
    adapter = LongMemEvalAdapter()
    all_documents, all_examples = adapter.load_documents(), adapter.load_examples()
    examples = all_examples[:question_limit]
    ids = {mid for example in examples for mid in example.metadata["corpus_ids"]}
    documents = [d for d in all_documents if d.doc_id in ids]
    corpus, queries = _convert(documents, examples)
    return corpus, queries, len(all_examples)
''',encoding='utf-8')
p=root/'memory/contradiction/detector.py'
s=p.read_text(encoding='utf-8')
s=s.replace('            forward = [s for s in supers if s.get("to_id") == current_id]\n','')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/metrics.py'
s=p.read_text(encoding='utf-8').replace('    all_maps = []\n','')
p.write_text(s,encoding='utf-8')
p=root/'memory/device.py'
s=p.read_text(encoding='utf-8')
a=s.index('"""');b=s.index('"""',a+3)+3
s=s[:a]+'"""Observed device status and optional Windows runtime preparation. VRAM values are telemetry; profile targets are not allocation limits."""'+s[b:]
s=s.replace('    if emb_prov.startswith("CUDA")', '    if embedder is None and reranker is None:\n        mode = "Uninitialized"\n        notes = "No neural model has been initialized."\n    elif emb_prov.startswith("Tensorrt") or rerank_prov.startswith("Tensorrt"):\n        mode = "GPU (TensorRT)"\n        notes = "An initialized model uses TensorrtExecutionProvider."\n    elif emb_prov.startswith("CUDA")')
s=s.replace('cuda_available=gpu_provider_available','cuda_available="CUDAExecutionProvider" in providers')
s=s.replace('# Hard limits for RTX 4050 6GB Profile','# Informational target for the original 6 GB hardware profile; not an enforced allocator limit.')
p.write_text(s,encoding='utf-8')
p=root/'tests/test_memory_engine.py'
s=p.read_text(encoding='utf-8').replace('assert status_initial.execution_mode in ["GPU (CUDA)", "CPU Fallback"]','assert status_initial.execution_mode == "Uninitialized"')
p.write_text(s,encoding='utf-8')
p=root/'tests/test_benchmark_harness.py'
s=p.read_text(encoding='utf-8')
for name in ('test_longmemeval_adapter_loading','test_locomo_adapter_loading','test_dmr_adapter_loading','test_benchmark_runner_and_resumability'):
    s=s.replace('def '+name+'(', '@pytest.mark.dataset\ndef '+name+'(')
# The evaluator stage check exercises the evaluator with declared documents; no downloaded corpus is needed.
a=s.index('def test_benchmark_evaluator_stages(');b=s.index('def test_benchmark_runner_and_resumability(',a)
block=s[a:b].replace('adapter = LongMemEvalAdapter()', 'from tests.test_evaluation_regressions import FixtureAdapter\n        adapter = FixtureAdapter()')
s=s[:a]+block+s[b:]
p.write_text(s,encoding='utf-8')
