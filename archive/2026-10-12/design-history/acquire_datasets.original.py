#!/usr/bin/env python3
"""
Official dataset acquisition for DMR, LoCoMo, and LongMemEval benchmarks.

This script downloads/clones the official benchmark datasets from their
canonical sources. Datasets are stored in datasets/ (gitignored) and are
NOT committed to this repository.

Sources:
- LoCoMo: https://github.com/snap-research/locomo (Maharana et al. 2024)
- LongMemEval: https://github.com/xiaowu0162/LongMemEval (Wu et al. 2024)
- DMR: Hugging Face dataset linked from Letta repo README (Packer et al. 2023)

Usage:
    python acquire_datasets.py
    python acquire_datasets.py --benchmark locomo
    python acquire_datasets.py --benchmark longmemeval
    python acquire_datasets.py --benchmark dmr
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import requests

DATASETS_DIR = Path(__file__).parent
DATASETS_DIR.mkdir(exist_ok=True)

# Benchmark metadata
BENCHMARKS = {
    "locomo": {
        "repo_url": "https://github.com/snap-research/locomo",
        "data_file": "data/locomo10.json",
        "paper": "Maharana et al. 2024 - LoCoMo: Long-form Conversation Memory",
        "commit": None,  # Will be set after clone
    },
    "longmemeval": {
        "repo_url": "https://github.com/xiaowu0162/LongMemEval",
        "hf_dataset": "xiaowu0162/longmemeval-cleaned",  # Official HF dataset
        "paper": "Wu et al. 2024 - LongMemEval: Long-term Memory Evaluation",
        "commit": None,
    },
    "dmr": {
        "repo_url": "https://github.com/letta-ai/letta",
        "hf_dataset": "MemGPT/MSC-Self-Instruct",  # Official MemGPT MSC dataset (DMR source)
        "paper": "Packer et al. 2023 - MemGPT: Towards LLMs as Operating Systems (DMR/MSC dataset)",
        "commit": None,
    },
}


def run_command(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nStderr: {result.stderr}")
    return result


def get_git_commit_hash(repo_path: Path) -> str:
    """Get the current commit hash of a git repository."""
    result = run_command(["git", "rev-parse", "HEAD"], cwd=repo_path)
    return result.stdout.strip()


def clone_or_update_repo(repo_url: str, target_dir: Path) -> str:
    """Clone a repository or update it if it exists. Returns commit hash."""
    if target_dir.exists():
        print(f"  Repository exists at {target_dir}, updating...")
        run_command(["git", "fetch", "origin"], cwd=target_dir)
        run_command(["git", "reset", "--hard", "origin/main"], cwd=target_dir)
    else:
        print(f"  Cloning {repo_url} to {target_dir}...")
        run_command(["git", "clone", repo_url, str(target_dir)])
    commit_hash = get_git_commit_hash(target_dir)
    print(f"  Commit: {commit_hash}")
    return commit_hash


def download_hf_dataset(dataset_id: str, target_dir: Path) -> None:
    """Download a dataset from Hugging Face Hub."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise RuntimeError("datasets library not installed. Run: pip install datasets")

    print(f"  Downloading {dataset_id} from Hugging Face...")
    dataset = load_dataset(dataset_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Save each split
    for split_name, split_data in dataset.items():
        output_file = target_dir / f"{split_name}.jsonl"
        split_data.to_json(str(output_file), orient="records", lines=True)
        print(f"  Saved {split_name} split to {output_file} ({len(split_data)} examples)")


def verify_file_exists(file_path: Path, description: str) -> None:
    """Verify a required file exists, raise if not."""
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required {description} not found at {file_path}. "
            f"Run acquisition script first: python acquire_datasets.py"
        )
    print(f"  ✓ Found {description}: {file_path}")


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def acquire_locomo() -> Dict:
    """Acquire LoCoMo dataset from snap-research/locomo."""
    print("\n=== Acquiring LoCoMo ===")
    repo_dir = DATASETS_DIR / "locomo"
    commit_hash = clone_or_update_repo(BENCHMARKS["locomo"]["repo_url"], repo_dir)
    BENCHMARKS["locomo"]["commit"] = commit_hash

    data_file = repo_dir / BENCHMARKS["locomo"]["data_file"]
    verify_file_exists(data_file, "LoCoMo data file (locomo10.json)")

    file_hash = compute_file_hash(data_file)
    print(f"  File hash (SHA256): {file_hash}")

    return {
        "benchmark": "locomo",
        "repo_url": BENCHMARKS["locomo"]["repo_url"],
        "commit_hash": commit_hash,
        "data_file": str(data_file),
        "file_hash": file_hash,
        "paper": BENCHMARKS["locomo"]["paper"],
    }


def acquire_longmemeval() -> Dict:
    """Acquire LongMemEval dataset from Hugging Face (official)."""
    print("\n=== Acquiring LongMemEval ===")
    
    hf_dataset_id = BENCHMARKS["longmemeval"]["hf_dataset"]
    target_dir = DATASETS_DIR / "longmemeval"
    download_hf_dataset(hf_dataset_id, target_dir)

    # Verify downloaded files
    file_hashes = {}
    for f in target_dir.glob("*.jsonl"):
        file_hashes[f.name] = compute_file_hash(f)
        print(f"  ✓ {f.name} (SHA256: {file_hashes[f.name]})")

    return {
        "benchmark": "longmemeval",
        "repo_url": BENCHMARKS["longmemeval"]["repo_url"],
        "hf_dataset": hf_dataset_id,
        "data_dir": str(target_dir),
        "file_hashes": file_hashes,
        "paper": BENCHMARKS["longmemeval"]["paper"],
    }


def acquire_dmr() -> Dict:
    """Acquire DMR dataset from Hugging Face (official MemGPT MSC dataset)."""
    print("\n=== Acquiring DMR ===")

    hf_dataset_id = BENCHMARKS["dmr"]["hf_dataset"]
    target_dir = DATASETS_DIR / "dmr"
    download_hf_dataset(hf_dataset_id, target_dir)

    # Verify downloaded files
    file_hashes = {}
    for f in target_dir.glob("*.jsonl"):
        file_hashes[f.name] = compute_file_hash(f)
        print(f"  ✓ {f.name} (SHA256: {file_hashes[f.name]})")

    return {
        "benchmark": "dmr",
        "repo_url": BENCHMARKS["dmr"]["repo_url"],
        "hf_dataset": hf_dataset_id,
        "data_dir": str(target_dir),
        "file_hashes": file_hashes,
        "paper": BENCHMARKS["dmr"]["paper"],
    }


def write_provenance(provenance: List[Dict]) -> None:
    """Write dataset provenance to JSON file."""
    provenance_file = DATASETS_DIR / "provenance.json"
    with open(provenance_file, "w") as f:
        json.dump(provenance, f, indent=2)
    print(f"\n=== Provenance written to {provenance_file} ===")


def write_readme() -> None:
    """Write datasets/README.md with citations."""
    readme_content = """# Official Benchmark Datasets

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
- **Source**: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned (official HF dataset)
- **Repository**: https://github.com/xiaowu0162/LongMemEval
- **Paper**: Wu et al. 2024, "LongMemEval: Long-term Memory Evaluation"
- **Files**: JSONL splits (train/validation/test) with 500 QA pairs
- **License**: See Hugging Face dataset page

### DMR (Multi-Session Chat / MSC)
- **Source**: https://huggingface.co/datasets/MemGPT/MSC-Self-Instruct (official MemGPT dataset)
- **Repository**: https://github.com/letta-ai/letta (MemGPT origin)
- **Paper**: Packer et al. 2023, "MemGPT: Towards LLMs as Operating Systems"
- **Format**: JSONL with 500 multi-session conversations
- **License**: Apache-2.0 (see Hugging Face dataset page)

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
"""
    readme_path = DATASETS_DIR / "README.md"
    readme_path.write_text(readme_content)
    print(f"README written to {readme_path}")


def main():
    parser = argparse.ArgumentParser(description="Acquire official benchmark datasets")
    parser.add_argument(
        "--benchmark",
        choices=["locomo", "longmemeval", "dmr", "all"],
        default="all",
        help="Which benchmark to acquire (default: all)",
    )
    args = parser.parse_args()

    provenance = []

    if args.benchmark in ("locomo", "all"):
        provenance.append(acquire_locomo())

    if args.benchmark in ("longmemeval", "all"):
        provenance.append(acquire_longmemeval())

    if args.benchmark in ("dmr", "all"):
        provenance.append(acquire_dmr())

    write_provenance(provenance)
    write_readme()

    print("\n=== All datasets acquired successfully ===")
    print(f"Datasets stored in: {DATASETS_DIR}")
    print("Add 'datasets/' to .gitignore to avoid committing data.")


if __name__ == "__main__":
    main()