# Official Benchmark Datasets

This directory contains third-party benchmark datasets acquired from their
official sources. These datasets are **not vendored** in this repository —
they are downloaded/cloned at build time.

## Datasets

### LoCoMo
- **Source**: https://github.com/snap-research/locomo
- **Paper**: Maharana et al. 2024, "LoCoMo: Long-form Conversation Memory"
- **File**: `data/locomo10.json` (10 annotated conversations with official QA pairs)
- **License**: See source repository

### LongMemEval
- **Source**: https://github.com/xiaowu0162/LongMemEval
- **Paper**: Wu et al. 2024, "LongMemEval: Long-term Memory Evaluation"
- **Files**: Multiple QA formats in `data/` directory
  - `longmemeval_q_qa.json` - Question-Answering format
  - `longmemeval_q_mc.json` - Multiple Choice format
  - `longmemeval_q_hc.json` - Hard Core format
- **License**: See source repository

### DMR (Multi-Session Chat / MSC)
- **Source**: Hugging Face dataset `letta/dmr` (linked from https://github.com/letta-ai/letta)
- **Paper**: Packer et al. 2023, "MemGPT: Towards LLMs as Operating Systems"
- **Format**: JSONL splits (train/validation/test)
- **License**: See Hugging Face dataset page

## Acquisition

Run the acquisition script:

```bash
python acquire_datasets.py
```

Or acquire individual benchmarks:

```bash
python acquire_datasets.py --benchmark locomo
python acquire_datasets.py --benchmark longmemeval
python acquire_datasets.py --benchmark dmr
```

## Provenance Tracking

After acquisition, `provenance.json` is generated with:
- Repository URLs and commit hashes
- File hashes (SHA256) for data integrity verification
- Paper citations

This ensures reproducibility and traceability of the exact dataset versions used.

## Usage in Evaluation

The evaluation harness loads datasets directly from this directory.
**It fails loudly if datasets are missing** — no synthetic fallbacks.
