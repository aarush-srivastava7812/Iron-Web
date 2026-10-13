"""Report software and device state; optional checks must be selected explicitly."""

import argparse
import importlib.metadata
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memory.device import inspect_device_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        action="store_true",
        help="Initialize and exercise real models; uncached files may download.",
    )
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument(
        "--nim",
        action="store_true",
        help="Make one explicitly selected hosted extraction request.",
    )
    options = parser.parse_args()
    packages = {}
    for name in (
        "qdrant-client",
        "falkordb",
        "numpy",
        "pydantic",
        "PyYAML",
        "fastembed",
        "fastembed-gpu",
        "onnxruntime",
        "onnxruntime-gpu",
        "openai",
        "tenacity",
        "pytest",
        "mem0ai",
        "zep-cloud",
        "mempalace",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    result = {
        "packages": packages,
        "credentials_present": {
            name: bool(os.getenv(name)) for name in ("NVIDIA_API_KEY", "ZEP_API_KEY")
        },
    }
    embedder, reranker = None, None
    if options.models:
        import numpy as np
        from memory import get_embedder, get_reranker

        embedder, reranker = (
            get_embedder(use_gpu=options.gpu),
            get_reranker(use_gpu=options.gpu),
        )
        vectors = embedder.embed(["Paris is in France", "Lima is in Peru"])
        ranked = reranker.rerank(
            "Capital of France",
            [
                dict(memory_id="paris", text="Paris is the capital of France."),
                dict(memory_id="lima", text="Lima is the capital of Peru."),
            ],
        )
        if (
            vectors.shape != (2, embedder.dimension)
            or not np.isfinite(vectors).all()
            or len(ranked) != 2
        ):
            raise RuntimeError("Real model check returned invalid outputs.")
        result["model_check"] = dict(
            embedding_shape=list(vectors.shape),
            reranked_ids=[h["memory_id"] for h in ranked],
        )
    if options.nim:
        from memory.ingestion.nim_extractor import NIMExtractor

        extracted = NIMExtractor().extract_entities_and_relations(
            "Fixture statement: Alice uses Python."
        )
        result["nim_check"] = dict(
            is_mock=extracted["is_mock"],
            entities=len(extracted["entities"]),
            extractor=extracted["extractor_name"],
        )
    result["device"] = inspect_device_status(
        options.gpu, embedder, reranker
    ).model_dump()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
