"""Compare optional genuine SDKs using the shared local metrics and complete-context cohorts."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memory.evaluation.harness.persistence import fingerprint
from memory.evaluation.harness.runner import BenchmarkRunner
from memory.evaluation.slices import FrozenSliceAdapter, load_slice
from research.upstream.backend import SDKBackend
from research.upstream.packages import PACKAGES


def cohorts(adapter, max_examples=None):
    documents = adapter.load_documents()
    examples = adapter.load_examples(limit=max_examples)
    grouped = {}
    for example in examples:
        ids = tuple(
            sorted(example.metadata.get("corpus_ids", [d.doc_id for d in documents]))
        )
        grouped.setdefault(ids, []).append(example)
    from dataclasses import asdict

    for ids, selected in grouped.items():
        wanted = set(ids)
        yield FrozenSliceAdapter(
            dict(
                benchmark=adapter.benchmark_name,
                documents=[asdict(d) for d in documents if d.doc_id in wanted],
                examples=[asdict(e) for e in selected],
            )
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", choices=BenchmarkRunner.ADAPTER_REGISTRY)
    parser.add_argument("package", choices=PACKAGES)
    parser.add_argument("--slice-version", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--gpu", action="store_true")
    options = parser.parse_args()
    if (
        not 1 <= options.k <= 100
        or options.max_examples is not None
        and options.max_examples < 1
    ):
        raise ValueError("Evaluation limits must be positive; k cannot exceed 100.")
    source = load_slice(options.slice_version, options.benchmark)
    selected = list(cohorts(source, options.max_examples))
    summaries = []
    # Validate run IDs and inputs before constructing clients that can contact an external service.
    for index, adapter in enumerate(selected):
        runner = BenchmarkRunner(
            str(ROOT / "data/research_results"), f"{options.run_id}_{index}"
        )
        namespace = (
            "memory_eval_"
            + fingerprint(
                dict(
                    run=runner.run_id,
                    benchmark=options.benchmark,
                    package=options.package,
                    data=adapter.payload,
                )
            )[:24]
        )
        directory = ROOT / "data/sdk_evaluations" / namespace
        directory.mkdir(parents=True, exist_ok=True)
        package = PACKAGES[options.package](namespace, directory, options.gpu)
        backend = SDKBackend(package, options.gpu)
        summaries.append(
            runner.run_benchmark(
                options.benchmark,
                backend,
                adapter=adapter,
                retrieval_mode=package.name,
                k=options.k,
            )
        )
    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
