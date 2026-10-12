from pathlib import Path
root=Path(__file__).resolve().parents[1]
(root/'datasets/README.md').write_text('''# Benchmark inputs and provenance

The original input files are local, excluded from Git, and recorded in `provenance.json`. Their declared SHA-256 hashes and source repository revisions were checked during the cleanup and matched the existing files.

| Input | Retained path | Source |
|---|---|---|
| LoCoMo | `locomo/data/locomo10.json` | Snap Research LoCoMo, revision `3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376` |
| LongMemEval S-cleaned | `longmemeval/data/longmemeval_s_cleaned.json` | LongMemEval cleaned release; source repository revision `9e0b455f4ef0e2ab8f2e582289761153549043fc` |
| MSC-Self-Instruct | `dmr/msc_self_instruct.jsonl` | `MemGPT/MSC-Self-Instruct`, revision `5138f416f8fa76b75b2e080da87e8a8e346e1500` |

The project's `dmr` adapter reads the existing derived MSC corpus/query files under `data/benchmarks/dmr`. This is a project conversion, not an implementation of an official answer-scoring protocol. Raw input and conversion hashes remain recorded.

LoCoMo evaluator reference code under `locomo/task_eval`, LongMemEval evaluator/helper reference code under `longmemeval/src/evaluation` and `src/utils`, and their licenses remain available. Unrelated checkout code and the unused Letta application were moved to recoverable local archives.

## Acquisition and conversion

Acquisition downloads a declared file to a new destination, checks its content hash, and writes an adjacent provenance receipt. It does not update or reset existing repositories.

```powershell
python datasets/acquire_datasets.py locomo datasets/downloads/new-version/locomo10.json
python datasets/acquire_datasets.py longmemeval datasets/downloads/new-version/longmemeval_s_cleaned.json
python scripts/build_dmr_benchmark.py data/benchmarks/msc-new-version
```

Existing destinations are rejected. Download URLs and expected hashes come from the existing provenance record. A changed upstream file is rejected if it differs from the declared hash. No acquisition or hosted model request was made during the cleanup.

## Selection and evaluation

```powershell
python scripts/evaluate.py locomo --inspect
python scripts/export_slice.py locomo data/benchmark_slices/v2/locomo
```

The exporter selects a declared fraction of questions and retains complete histories. It writes a new version and manifest. Historical files in `data/official_upstream/slices` are preserved and must not be overwritten. The local evaluator records exact input fingerprints and coverage; missing evidence does not produce a perfect score.
''',encoding='utf-8')
for name in ('full_specification_report.md','cleanup_plan.md','cleanup_file_review.md'):
    p=root/'report'/name
    s=p.read_text(encoding='utf-8')
    lines=s.splitlines(True)
    lines.insert(2,'**Historical review:** This document describes the pre-cleanup baseline, Git commit `724c551`. See [current implementation](../docs/specification.md) and [applied cleanup report](cleanup_implementation_report.md) for the updated behavior.\n\n')
    p.write_text(''.join(lines),encoding='utf-8')
