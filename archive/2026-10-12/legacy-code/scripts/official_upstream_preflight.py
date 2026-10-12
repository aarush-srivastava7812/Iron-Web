"""Preflight the isolated, official-upstream benchmark environment.

This intentionally makes no network requests to Mem0, Zep, or NVIDIA NIM.
It protects the existing in-project architecture-inspired baselines from being
presented as upstream results, and reports the exact deterministic 20% slice
before a billable/cloud run is authorized.
"""
from __future__ import annotations

import importlib.metadata
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

@dataclass(frozen=True)
class UpstreamTarget:
    name: str
    package: str
    environment_variable: str | None
    local_only: bool


UPSTREAM_TARGETS = (
    UpstreamTarget("Mem0", "mem0ai", "NVIDIA_API_KEY", False),
    UpstreamTarget("Zep Cloud", "zep-cloud", "ZEP_API_KEY", False),
    UpstreamTarget("MemPalace", "mempalace", None, True),
)


def _installed_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


# These totals come from the benchmark adapters over the pinned official source
# files, not the small illustrative ``corpus.json`` artifacts beside them.
PINNED_TOTALS = {
    "locomo": (272, 1986),
    "dmr": (2500, 500),
    "longmemeval": (19195, 500),
}


def main() -> int:
    print("Official upstream baseline preflight (no external requests)\n")
    print("20% deterministic benchmark slice")
    print("benchmark     documents  questions")
    for benchmark in ("locomo", "dmr", "longmemeval"):
        documents, examples = PINNED_TOTALS[benchmark]
        print(f"{benchmark:<13} {round(documents * .2):>9} {round(examples * .2):>10}")

    print("\nIsolated upstream packages")
    for target in UPSTREAM_TARGETS:
        version = _installed_version(target.package)
        if version is None:
            state = "MISSING"
        elif target.environment_variable and not os.getenv(target.environment_variable):
            state = f"installed {version}; requires {target.environment_variable}"
        else:
            state = f"installed {version}; ready for explicit run authorization"
        print(f"{target.name:<13} {state}")

    print(
        "\nNo upstream ingestion/search was attempted. A real run must use the "
        "isolated interpreter and must not be merged with the in-project "
        "architecture-inspired retrievers."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
