"""
DMR (Dialogue Memory Retrieval / Multi-Session Chat) benchmark adapter.
Parses multi-session conversation dialogues and QA pairs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
)


class DMRAdapter(BenchmarkAdapter):
    """
    Adapter for Dialogue Memory Retrieval (DMR) / Multi-Session Chat (MSC).
    Evaluates multi-session conversation memory recall and QA.
    """

    def __init__(self, data_path: Optional[str] = None):
        super().__init__(data_path)
        self.resolved_path = self._resolve_path(data_path)

    @property
    def benchmark_name(self) -> str:
        return "dmr"

    def _resolve_path(self, path: Optional[str]) -> Path:
        if path and Path(path).exists():
            return Path(path)
        candidates = [
            Path("data/benchmarks/dmr"),
            Path("datasets/dmr"),
        ]
        for c in candidates:
            if c.exists():
                return c
        raise FileNotFoundError("Could not locate DMR benchmark directory.")

    def load_documents(self, limit: Optional[int] = None) -> List[BenchmarkDocument]:
        """Load conversation session documents."""
        corpus_path = self.resolved_path / "corpus.json"
        if not corpus_path.exists():
            # Try data/benchmarks/dmr/corpus.json
            corpus_path = Path("data/benchmarks/dmr/corpus.json")
            if not corpus_path.exists():
                raise FileNotFoundError(f"DMR corpus not found at {corpus_path}")

        documents: List[BenchmarkDocument] = []
        data = json.loads(corpus_path.read_text(encoding="utf-8"))
        for entry in data:
            meta = entry.get("metadata", {})
            doc = BenchmarkDocument(
                doc_id=entry["id"],
                text=entry["text"],
                session_id=meta.get("session_index", ""),
                timestamp=meta.get("timestamp", 0),
                metadata=meta
            )
            documents.append(doc)
            if limit and len(documents) >= limit:
                break
        return documents

    def load_examples(self, limit: Optional[int] = None) -> List[BenchmarkExample]:
        """Load DMR question-answering examples with gold answers and ground-truth IDs."""
        dmr_path = self.resolved_path / "dmr.json"
        if not dmr_path.exists():
            dmr_path = Path("data/benchmarks/dmr/dmr.json")
            if not dmr_path.exists():
                raise FileNotFoundError(f"DMR queries file not found at {dmr_path}")

        examples: List[BenchmarkExample] = []
        data = json.loads(dmr_path.read_text(encoding="utf-8"))
        for q in data.get("queries", []):
            ex = BenchmarkExample(
                example_id=q["query_id"],
                query=q["text"],
                ground_truth_ids=q.get("ground_truth_ids", []),
                gold_answer=q.get("answer", ""),
                category="msc_dialogue",
                metadata={"benchmark": "dmr"}
            )
            examples.append(ex)
            if limit and len(examples) >= limit:
                break
        return examples
