"""Freeze the official upstream slices: verify contents, record SHA-256 hashes.

Freezing means the slice files in data/official_upstream/slices/ become the
single immutable source of truth for every ablation and benchmark run.
Any later re-export must be a new version, never an overwrite of a frozen file.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLICES_DIR = ROOT / "data" / "official_upstream" / "slices"
BENCHMARKS = ("locomo", "dmr", "longmemeval")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    manifest = {
        "purpose": "Frozen official 20% upstream slices - immutable evaluation input",
        "frozen_at": int(time.time()),
        "frozen_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "slices": {},
    }
    ok = True
    for bench in BENCHMARKS:
        path = SLICES_DIR / f"{bench}_20percent.json"
        if not path.exists():
            print(f"MISSING: {path}")
            ok = False
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        doc_ids = [d["doc_id"] for d in data["documents"]]
        example_ids = [e["example_id"] for e in data["examples"]]
        if len(set(doc_ids)) != len(doc_ids) or len(set(example_ids)) != len(example_ids):
            print(f"DUPLICATE IDS in {bench} slice - NOT frozen")
            ok = False
            continue
        manifest["slices"][bench] = {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "num_documents": len(doc_ids),
            "num_examples": len(example_ids),
            "first_doc_id": doc_ids[0],
            "last_doc_id": doc_ids[-1],
        }
        print(f"{bench}: {len(doc_ids)} docs, {len(example_ids)} examples "
              f"sha256={manifest['slices'][bench]['sha256'][:16]}...")

    if not ok:
        print("ABORTED: freeze manifest not written.")
        return 1

    out = SLICES_DIR / "freeze_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Frozen -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
