"""One local evaluation entry point for live adapters or versioned complete-context slices."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memory.engine import MemoryEngine
from memory.evaluation.harness.runner import BenchmarkRunner
from memory.evaluation.slices import load_slice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", choices=BenchmarkRunner.ADAPTER_REGISTRY)
    parser.add_argument("--dataset")
    parser.add_argument("--slice-version")
    parser.add_argument("--run-id", default=f"local_{int(time.time())}")
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=sorted(MemoryEngine.retrieval_modes),
        default=["vector", "hybrid"],
    )
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--extractor", choices=["none", "nim"], default="none")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Check coverage without opening stores, loading models or contacting a service.",
    )
    options = parser.parse_args()
    adapter = (
        load_slice(options.slice_version, options.benchmark)
        if options.slice_version
        else BenchmarkRunner.ADAPTER_REGISTRY[options.benchmark](options.dataset)
    )
    documents, examples = (
        adapter.load_documents(),
        adapter.load_examples(limit=options.max_examples),
    )
    ids = {d.doc_id for d in documents}
    uncovered = [
        e.example_id
        for e in examples
        if (set(e.ground_truth_ids) | set(e.metadata.get("corpus_ids", []))) - ids
    ]
    if options.inspect:
        print(
            json.dumps(
                dict(
                    benchmark=options.benchmark,
                    documents=len(documents),
                    examples=len(examples),
                    uncovered_examples=uncovered,
                ),
                indent=2,
            )
        )
        return 1 if uncovered else 0
    if uncovered:
        raise ValueError(
            "Selected data has incomplete evidence or conversation histories."
        )
    runner = BenchmarkRunner(str(ROOT / "data/results"), options.run_id)
    for mode in options.modes:
        directory = (
            ROOT / "data/evaluations" / options.run_id / options.benchmark / mode
        )
        with MemoryEngine(
            config={
                "extraction_policy": options.extractor,
                "retrieval": {"reranker_enabled": options.rerank},
            },
            qdrant_path=str(directory / "vectors"),
            kuzu_path=str(directory / "graph.db"),
            use_gpu=options.gpu,
        ) as engine:
            summary = runner.run_benchmark(
                options.benchmark,
                engine,
                adapter=adapter,
                max_examples=options.max_examples,
                retrieval_mode=mode,
                k=options.k,
            )
            print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
