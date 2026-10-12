"""Materialize identical, adapter-derived 20% slices for upstream baselines."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.evaluation.harness import DMRAdapter, LoCoMoAdapter, LongMemEvalAdapter


LIMITS = {
    "locomo": (54, 397),
    "dmr": (500, 100),
    "longmemeval": (3839, 100),
}


def main() -> int:
    out_dir = ROOT / "data" / "official_upstream" / "slices"
    out_dir.mkdir(parents=True, exist_ok=True)
    for adapter in (LoCoMoAdapter(), DMRAdapter(), LongMemEvalAdapter()):
        max_documents, max_examples = LIMITS[adapter.benchmark_name]
        payload = {
            "benchmark": adapter.benchmark_name,
            "profile": "20percent",
            "documents": [asdict(doc) for doc in adapter.load_documents(limit=max_documents)],
            "examples": [asdict(ex) for ex in adapter.load_examples(limit=max_examples)],
        }
        target = out_dir / f"{adapter.benchmark_name}_20percent.json"
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        # MemPalace mines files. Use stable numeric names (Windows-safe) and
        # keep an explicit source-file-to-benchmark-ID map for fair scoring.
        input_dir = ROOT / "data" / "official_upstream" / "mempalace_inputs" / adapter.benchmark_name
        input_dir.mkdir(parents=True, exist_ok=True)
        manifest = {}
        for index, doc in enumerate(payload["documents"]):
            filename = f"{index:05d}.txt"
            (input_dir / filename).write_text(
                f"Benchmark document ID: {doc['doc_id']}\n\n{doc['text']}",
                encoding="utf-8",
            )
            manifest[filename] = doc["doc_id"]
        # Keep the mapping outside the mined directory: it is evaluation
        # metadata, never a benchmark document.
        (out_dir / f"{adapter.benchmark_name}_20percent_mempalace_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print(f"{adapter.benchmark_name}: {len(payload['documents'])} documents, "
              f"{len(payload['examples'])} questions -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
