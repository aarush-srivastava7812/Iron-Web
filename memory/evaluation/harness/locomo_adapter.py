"""
LoCoMo benchmark adapter.
Parses official Snap Research LoCoMo release (10 annotated multi-session conversations)
preserving QA categories, session boundaries, and evidence references.
"""

from __future__ import annotations

import json
from memory.evaluation.harness.dates import parse_timestamp
from pathlib import Path
from typing import List, Optional

from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
)

CATEGORY_NAMES = {
    1: "multi_hop_reasoning",
    2: "temporal",
    3: "factual",
    4: "open_domain",
    5: "adversarial",
}


class LoCoMoAdapter(BenchmarkAdapter):
    """
    Adapter for the LoCoMo benchmark (Maharana et al. 2024).
    Evaluates long-form multi-session conversation memory.
    """

    def __init__(self, data_path: Optional[str] = None):
        super().__init__(data_path)
        self.resolved_path = self._resolve_path(data_path)

    @property
    def benchmark_name(self) -> str:
        return "locomo"

    def _resolve_path(self, path: Optional[str]) -> Path:
        if path is not None:
            explicit = Path(path).resolve()
            if not explicit.exists():
                raise FileNotFoundError(explicit)
            return explicit
        root = Path(__file__).resolve().parents[3]
        candidates = [
            (root / "datasets/locomo/data/locomo10.json"),
            (
                Path(__file__).resolve().parents[3]
                / "data/benchmarks/locomo/corpus.json"
            ),
        ]
        for c in candidates:
            if c.exists():
                return c
        raise FileNotFoundError("Could not locate LoCoMo dataset files.")

    def _read_data(self):
        if not hasattr(self, "_data"):
            self._data = json.loads(self.resolved_path.read_text(encoding="utf-8"))
            if not isinstance(self._data, list):
                raise ValueError("Benchmark source must be a records array.")
        return self._data

    @property
    def _official_format(self):
        records = self._read_data()
        return bool(records and "conversation" in records[0])

    def _parse_date_to_timestamp(self, date_str: str) -> int:
        return parse_timestamp(date_str)

    def load_documents(self, limit: Optional[int] = None) -> List[BenchmarkDocument]:
        """
        Load LoCoMo conversation sessions as BenchmarkDocument instances.
        """
        documents: List[BenchmarkDocument] = []

        if self._official_format:
            records = self._read_data()
            for record in records:
                sample_id = record.get("sample_id", "sample")
                conversation = record.get("conversation", {})

                # Iterate through session keys
                for key, val in conversation.items():
                    if key.startswith("session_") and isinstance(val, list):
                        session_num = key.split("_")[1]
                        date_key = f"session_{session_num}_date_time"
                        date_str = conversation.get(date_key, "")
                        ts = self._parse_date_to_timestamp(date_str)

                        turn_lines = []
                        for turn in val:
                            speaker = turn.get("speaker", "Speaker")
                            text = turn.get("text", "")
                            if text:
                                turn_lines.append(f"{speaker}: {text}")
                        session_text = "\n".join(turn_lines)

                        doc_id = f"locomo:{sample_id}:session_{session_num}"
                        doc = BenchmarkDocument(
                            doc_id=doc_id,
                            text=session_text,
                            session_id=f"session_{session_num}",
                            timestamp=ts,
                            metadata={
                                "benchmark": "locomo",
                                "sample_id": sample_id,
                                "session": key,
                                "date": date_str,
                            },
                        )
                        documents.append(doc)
                        if limit and len(documents) >= limit:
                            break
                if limit and len(documents) >= limit:
                    break
        else:
            # Fallback to data/benchmarks/locomo/corpus.json
            corpus_data = self._read_data()
            for entry in corpus_data:
                meta = entry.get("metadata", {})
                doc = BenchmarkDocument(
                    doc_id=entry["id"],
                    text=entry["text"],
                    session_id=entry["id"],
                    timestamp=meta.get("valid_from", 0),
                    valid_from=meta.get("valid_from", 0),
                    valid_until=meta.get("valid_until", 2**63 - 1),
                    metadata=meta,
                )
                documents.append(doc)
                if limit and len(documents) >= limit:
                    break

        return documents

    def load_examples(self, limit: Optional[int] = None) -> List[BenchmarkExample]:
        """
        Load LoCoMo QA examples with categories, evidence sessions, and gold answers.
        """
        examples: List[BenchmarkExample] = []

        if self._official_format:
            records = self._read_data()
            for record in records:
                sample_id = record.get("sample_id", "sample")
                qa_list = record.get("qa", [])

                for idx, qa_item in enumerate(qa_list):
                    ex_id = f"locomo:{sample_id}:qa:{idx}"
                    category_num = qa_item.get("category", 1)
                    category_name = CATEGORY_NAMES.get(
                        category_num, f"category_{category_num}"
                    )

                    evidence_turns = qa_item.get("evidence", [])
                    # Evidence format e.g. ["D1:3", "D2:12"] -> maps to sessions ["session_1", "session_2"]
                    evidence_to_session = {}
                    for session_key, turns in record.get("conversation", {}).items():
                        if session_key.startswith("session_") and isinstance(
                            turns, list
                        ):
                            for turn in turns:
                                if turn.get("dia_id"):
                                    evidence_to_session[turn["dia_id"]] = (
                                        f"locomo:{sample_id}:{session_key}"
                                    )
                    evidence_sessions = [
                        evidence_to_session[ev]
                        for ev in evidence_turns
                        if ev in evidence_to_session
                    ]
                    unmapped = [
                        ev for ev in evidence_turns if ev not in evidence_to_session
                    ]

                    ex = BenchmarkExample(
                        example_id=ex_id,
                        query=qa_item["question"],
                        ground_truth_ids=sorted(set(evidence_sessions)),
                        gold_answer=str(qa_item.get("answer", "")),
                        category=category_name,
                        metadata={
                            "sample_id": sample_id,
                            "category_num": category_num,
                            "raw_evidence": evidence_turns,
                            "unmapped_evidence": unmapped,
                            "corpus_ids": [
                                f"locomo:{sample_id}:{key}"
                                for key, value in record.get("conversation", {}).items()
                                if key.startswith("session_")
                                and isinstance(value, list)
                            ],
                        },
                    )
                    examples.append(ex)
                    if limit and len(examples) >= limit:
                        break
                if limit and len(examples) >= limit:
                    break
        else:
            # Fallback to data/benchmarks/locomo/locomo.json
            query_path = self.resolved_path.parent / "locomo.json"
            if query_path.exists():
                data = json.loads(query_path.read_text(encoding="utf-8"))
                for q in data.get("queries", []):
                    ex = BenchmarkExample(
                        example_id=q["query_id"],
                        query=q["text"],
                        ground_truth_ids=q.get("ground_truth_ids", []),
                        gold_answer="",
                        category="general",
                    )
                    examples.append(ex)
                    if limit and len(examples) >= limit:
                        break

        return examples
