from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'memory/evaluation/metrics.py'
s=p.read_text(encoding='utf-8')
a=s.index('def recall_at_k('); b=s.index('def map_score(',a)
s=s[:a]+'from memory.evaluation.retrieval_metrics import recall_at_k, precision_at_k, mrr, ndcg_at_k, average_precision\n\n\n'+s[b:]
s=s.replace('        scenario_id = r.get("query_id", r.get("scenario_id", ""))\n        relevant = relevant_map.get(scenario_id, [])', '        scenario_id = r.get("query_id", r.get("scenario_id", ""))\n        relevant = r.get("ground_truth_ids", relevant_map.get(scenario_id, []))')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/base.py'
s=p.read_text(encoding='utf-8')
a=s.index('def recall_at_k('); b=s.index('# =============================================================================\n# Benchmark Adapter',a)
s=s[:a]+'from memory.evaluation.retrieval_metrics import recall_at_k, precision_at_k, mean_reciprocal_rank, ndcg_at_k, compute_retrieval_metrics\n\n\n'+s[b:]
s=s.replace('norm_gold in norm_pred or norm_pred in norm_gold', 'norm_gold in norm_pred').replace('2**31 - 1','2**63 - 1')
p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/evaluator.py'
s=p.read_text(encoding='utf-8')
s=s.replace('        t0 = time.perf_counter()\n        ingested_ids = []', '        if batch_size < 1:\n            raise ValueError("Batch size must be positive.")\n        t0 = time.perf_counter()\n        ingested_ids = []\n        skipped = 0',1)
s=s.replace('            for doc in batch:\n                items.append({', '''            for doc in batch:
                existing = self.engine.get(doc.doc_id)
                if existing and existing.content == doc.text and (doc.timestamp is None or existing.timestamp == doc.timestamp) and all(
                    existing.metadata.get(key) == value for key, value in doc.metadata.items()) and existing.valid_from == doc.valid_from and existing.valid_until == doc.valid_until:
                    skipped += 1
                    continue
                items.append({''',1)
s=s.replace('            "ingested_ids": len(ingested_ids),', '            "ingested_ids": len(ingested_ids),\n            "skipped_unchanged": skipped,')
s=s.replace('        ret_metrics = compute_retrieval_metrics(', '        ret_metrics = compute_retrieval_metrics(',1)
s=s.replace('            k_values=[1, 3, 5, self.k]\n        )', '            k_values=[1, 3, 5, self.k]\n        ) if example.ground_truth_ids else {}',1)
a=s.index('        ret_metrics_keys =',s.index('    def aggregate_results('))
b=s.index('        # Category breakdowns',a)
s=s[:a]+'''        successful = [r for r in results if not r.error]
        ret_metrics_keys = sorted({key for r in successful for key in r.retrieval_metrics})
        ans_metrics_keys = sorted({key for r in successful for key in r.answer_metrics})
        agg = {"total_examples": len(results), "successful_examples": len(successful),
            "failed_examples": len(results)-len(successful),
            "retrieval_scored_examples": sum(bool(r.retrieval_metrics) for r in successful),
            "answer_scored_examples": sum(bool(r.answer_metrics) for r in successful),
            "retrieval": {}, "answer": {}, "by_category": {},
            "latency": {"mean_retrieval_ms": float(np.mean([r.retrieval_latency_ms for r in successful])) if successful else None,
                        "mean_total_ms": float(np.mean([r.total_latency_ms for r in successful])) if successful else None}}
        for key in ret_metrics_keys:
            agg["retrieval"][key] = float(np.mean([r.retrieval_metrics[key] for r in successful if key in r.retrieval_metrics]))
        for key in ans_metrics_keys:
            agg["answer"][key] = float(np.mean([r.answer_metrics[key] for r in successful if key in r.answer_metrics]))

''' +s[b:]
s=s.replace('categories = set(r.category for r in results if r.category)', 'categories = set(r.category for r in successful if r.category)')
s=s.replace('cat_results = [r for r in results if r.category == cat]', 'cat_results = [r for r in successful if r.category == cat]')
s=s.replace('for r in cat_results]))', 'for r in cat_results if r.retrieval_metrics])) if any(r.retrieval_metrics for r in cat_results) else None')
p.write_text(s,encoding='utf-8')
