"""Paired same-data evidence-read check; no persistent cache is introduced."""

# ruff: noqa: E402
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
from memory.engine import MemoryEngine
from memory.embeddings.embedder import Embedder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    saved = json.loads((args.demo / "results.json").read_text(encoding="utf-8"))
    model = Embedder(
        use_gpu=False, cache_dir="C:/Users/User/AppData/Local/Temp/fastembed_cache"
    )
    engine = MemoryEngine(
        config={"extraction_policy": "none"},
        qdrant_path=str(args.demo / "vectors"),
        graph_name=saved["graph_name"],
        embedder=model,
    )
    layer = engine.lifecycle
    batched = layer.views

    def per_claim(claims, at, known_at=None):
        return [layer.view(c, at, known_at) for c in claims]

    at = int(time.time())
    timings = {"per_claim": [], "batched": []}
    signature = None
    try:
        for round_number in range(12):
            for name in (
                ["per_claim", "batched"]
                if round_number % 2 == 0
                else ["batched", "per_claim"]
            ):
                layer.views = per_claim if name == "per_claim" else batched
                start = time.perf_counter()
                hits = engine.search("Traveller budget", k=3, query_time=at)
                duration = (time.perf_counter() - start) * 1000
                found = [
                    (
                        h.memory_id,
                        h.content,
                        sorted(
                            (
                                e["claim_id"],
                                e["status"],
                                e["fuzzy_score"],
                                tuple(sorted(s["id"] for s in e["sources"])),
                            )
                            for e in h.metadata.get("memory_evidence", [])
                        ),
                    )
                    for h in hits
                ]
                if signature is None:
                    signature = found
                assert (
                    found == signature
                ), "Batching changed ranked evidence or its state."
                if round_number >= 2:
                    timings[name].append(duration)
        summary = {
            name: dict(
                samples=len(values),
                median_ms=statistics.median(values),
                p95_ms=sorted(values)[-1],
            )
            for name, values in timings.items()
        }
        result = dict(
            graph=saved["graph_name"],
            identical_ranked_evidence=True,
            full_retrieval=summary,
            rounds=10,
            method="Same graph/vectors/model/query/time/budget, alternating execution order, two warmup rounds. Only within-request batched views versus individual views vary. Small local fixture, not a scale claim.",
        )
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        layer.views = batched
        engine.close()


if __name__ == "__main__":
    main()
