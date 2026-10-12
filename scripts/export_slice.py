import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory.evaluation.harness.runner import BenchmarkRunner
from memory.evaluation.slices import export_slice


def main():
    parser = argparse.ArgumentParser(
        description="Create a new complete-context slice version without overwriting historical inputs."
    )
    parser.add_argument("benchmark", choices=BenchmarkRunner.ADAPTER_REGISTRY)
    parser.add_argument("destination")
    parser.add_argument("--dataset")
    parser.add_argument("--fraction", type=float, default=0.2)
    options = parser.parse_args()
    adapter = BenchmarkRunner.ADAPTER_REGISTRY[options.benchmark](options.dataset)
    print(
        json.dumps(
            export_slice(adapter, options.destination, options.fraction), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
