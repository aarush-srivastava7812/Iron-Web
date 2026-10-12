"""Versioned, complete-context slices; existing inputs are never overwritten."""

import json
import math
from dataclasses import asdict
from pathlib import Path
from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
)
from memory.evaluation.harness.persistence import fingerprint, write_atomic


class FrozenSliceAdapter(BenchmarkAdapter):
    def __init__(self, payload):
        self.payload = payload
        self._documents = [BenchmarkDocument(**d) for d in payload["documents"]]
        self._examples = [BenchmarkExample(**e) for e in payload["examples"]]

    @property
    def benchmark_name(self):
        return self.payload["benchmark"]

    def load_documents(self, limit=None):
        return self._documents[:limit]

    def load_examples(self, limit=None):
        return self._examples[:limit]


def validate_slice(payload):
    documents, examples = payload["documents"], payload["examples"]
    ids = {d["doc_id"] for d in documents}
    if (
        not documents
        or not examples
        or len(ids) != len(documents)
        or len({e["example_id"] for e in examples}) != len(examples)
    ):
        raise ValueError("Slice is empty or contains duplicate identifiers.")
    for example in examples:
        if example.get("metadata", {}).get("unmapped_evidence"):
            raise ValueError("Slice contains unmapped evidence annotations.")
        needed = set(example["ground_truth_ids"]) | set(
            example.get("metadata", {}).get("corpus_ids", [])
        )
        if needed - ids:
            raise ValueError(
                f"Incomplete evidence or conversation history: {example['example_id']}"
            )
    for document in documents:
        if not document["text"].strip() or document.get("valid_from", 0) > document.get(
            "valid_until", 2**63 - 1
        ):
            raise ValueError("Invalid document text or validity.")
    return payload


def export_slice(adapter, destination, fraction=0.2):
    if not 0 < fraction <= 1:
        raise ValueError("Question fraction must be greater than zero and at most one.")
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Slice version already exists; choose a new destination.")
    documents = adapter.load_documents()
    examples = adapter.load_examples()
    selected = examples[: max(1, math.ceil(len(examples) * fraction))]
    # Preserve each selected question's complete history. Unscoped datasets keep the full corpus.
    ids = set()
    if any("corpus_ids" not in e.metadata for e in selected):
        ids = {d.doc_id for d in documents}
    else:
        for example in selected:
            ids.update(example.metadata["corpus_ids"])
            ids.update(example.ground_truth_ids)
    payload = dict(
        benchmark=adapter.benchmark_name,
        profile="complete_context_v2",
        selection=dict(
            question_fraction=fraction,
            rule="first_questions_in_release_order_with_complete_context",
            source_questions=len(examples),
            source_documents=len(documents),
        ),
        documents=[asdict(d) for d in documents if d.doc_id in ids],
        examples=[asdict(e) for e in selected],
    )
    validate_slice(payload)
    destination.mkdir(parents=True)
    path = destination / (adapter.benchmark_name + ".json")
    write_atomic(path, json.dumps(payload, ensure_ascii=False))
    manifest = dict(
        schema_version=2,
        slices={
            adapter.benchmark_name: dict(
                path=path.name,
                fingerprint=fingerprint(payload),
                documents=len(payload["documents"]),
                examples=len(payload["examples"]),
            )
        },
    )
    write_atomic(destination / "manifest.json", json.dumps(manifest, indent=2))
    return manifest


def load_slice(directory, benchmark):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["slices"][benchmark]
    path = (directory / entry["path"]).resolve()
    if path.parent != directory.resolve():
        raise ValueError("Slice path leaves its version directory.")
    payload = validate_slice(json.loads(path.read_text(encoding="utf-8")))
    if fingerprint(payload) != entry["fingerprint"]:
        raise ValueError("Frozen slice contents differ from their manifest.")
    return FrozenSliceAdapter(payload)
