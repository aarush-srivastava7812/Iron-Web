from pathlib import Path
root=Path(__file__).resolve().parents[1]
for name in ('longmemeval','locomo'):
    p=root/f'memory/evaluation/harness/{name}_adapter.py'
    s=p.read_text(encoding='utf-8')
    s=s.replace('from datetime import datetime', 'from memory.evaluation.harness.dates import parse_timestamp')
    s=s.replace('        if path and Path(path).exists():\n            return Path(path)', '        if path is not None:\n            explicit = Path(path).resolve()\n            if not explicit.exists():\n                raise FileNotFoundError(explicit)\n            return explicit\n        root = Path(__file__).resolve().parents[3]')
    s=s.replace('Path("datasets/', '(root / "datasets/').replace('Path("data/benchmarks/', '(Path(__file__).resolve().parents[3] / "data/benchmarks/')
    a=s.index('        """Parse ISO',s.index('    def _parse_date_to_timestamp(')) if name=='longmemeval' else s.index('        if not date_str:',s.index('    def _parse_date_to_timestamp('))
    b=s.index('    def load_documents(',a)
    s=s[:a]+'        return parse_timestamp(date_str)\n\n'+s[b:]
    if name=='longmemeval':
        s=s.replace('                for s_id, s_date, turns in zip(session_ids, dates, sessions):', '                if not (len(session_ids) == len(dates) == len(sessions)):\n                    raise ValueError("LongMemEval session IDs, dates and dialogues have different lengths.")\n                for s_id, s_date, turns in zip(session_ids, dates, sessions):')
        s=s.replace('query_path = (Path(__file__).resolve().parents[3] / "data/benchmarks/longmemeval/longmemeval.json")', 'query_path = self.resolved_path.parent / "longmemeval.json"')
    else:
        s=s.replace('    1: "factual",\n    2: "temporal",\n    3: "multi_hop_reasoning",\n    4: "preference"', '    1: "multi_hop_reasoning",\n    2: "temporal",\n    3: "factual",\n    4: "open_domain",\n    5: "adversarial"')
        s=s.replace('ground_truth_ids=evidence_sessions', 'ground_truth_ids=sorted(set(evidence_sessions))')
        s=s.replace('query_path = (Path(__file__).resolve().parents[3] / "data/benchmarks/locomo/locomo.json")', 'query_path = self.resolved_path.parent / "locomo.json"')
    s=s.replace('2**31 - 1','2**63 - 1')
    p.write_text(s,encoding='utf-8')
p=root/'memory/evaluation/harness/dmr_adapter.py'
s=p.read_text(encoding='utf-8')
s=s.replace('        if path and Path(path).exists():\n            return Path(path)', '        if path is not None:\n            explicit = Path(path).resolve()\n            if not explicit.is_dir():\n                raise FileNotFoundError(explicit)\n            return explicit\n        root = Path(__file__).resolve().parents[3]')
s=s.replace('Path("data/benchmarks/dmr")','root / "data/benchmarks/dmr"').replace('Path("datasets/dmr")','root / "datasets/dmr"')
a=s.index('        if not corpus_path.exists():');b=s.index('        documents:',a)
s=s[:a]+'        if not corpus_path.exists():\n            raise FileNotFoundError(corpus_path)\n\n'+s[b:]
a=s.index('        if not dmr_path.exists():');b=s.index('        examples:',a)
s=s[:a]+'        if not dmr_path.exists():\n            raise FileNotFoundError(dmr_path)\n\n'+s[b:]
s=s.replace('meta.get("timestamp", 0)','meta.get("timestamp")')
p.write_text(s,encoding='utf-8')
