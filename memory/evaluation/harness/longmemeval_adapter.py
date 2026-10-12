"""
LongMemEval benchmark adapter.
Parses official LongMemEval cleaned release preserving question types,
dates, evidence sessions, and conversational haystacks.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from memory.evaluation.harness.base import (
    BenchmarkAdapter,
    BenchmarkDocument,
    BenchmarkExample,
)


class LongMemEvalAdapter(BenchmarkAdapter):
    """
    Adapter for the LongMemEval benchmark (Wu et al. 2024).
    Evaluates temporal multi-session needle-in-haystack retrieval and QA.
    """

    def __init__(self, data_path: Optional[str] = None):
        super().__init__(data_path)
        self.resolved_path = self._resolve_path(data_path)

    @property
    def benchmark_name(self) -> str:
        return "longmemeval"

    def _resolve_path(self, path: Optional[str]) -> Path:
        if path and Path(path).exists():
            return Path(path)
        candidates = [
            Path("datasets/longmemeval/data/longmemeval_s_cleaned.json"),
            Path("data/benchmarks/longmemeval/corpus.json"),
        ]
        for c in candidates:
            if c.exists():
                return c
        raise FileNotFoundError("Could not locate LongMemEval dataset files.")

    def _parse_date_to_timestamp(self, date_str: str) -> int:
        """Parse ISO or human date string to Unix timestamp."""
        if not date_str:
            return 0
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d",
            "%d %B %Y",
            "%B %d, %Y"
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return int(dt.timestamp())
            except Exception:
                continue
        return 0

    def load_documents(self, limit: Optional[int] = None) -> List[BenchmarkDocument]:
        """
        Load haystack sessions as BenchmarkDocument instances.
        Each document represents one chat session with its original date and session ID.
        """
        docs_by_id: Dict[str, BenchmarkDocument] = {}

        if self.resolved_path.name.endswith(".json") and "s_cleaned" in self.resolved_path.name:
            records = json.loads(self.resolved_path.read_text(encoding="utf-8"))
            self._loaded_question_ids = []
            for item in records:
                sessions = item.get("haystack_sessions", [])
                dates = item.get("haystack_dates", [])
                session_ids = item.get("haystack_session_ids", [])
                
                for s_id, s_date, turns in zip(session_ids, dates, sessions):
                    doc_id = f"longmemeval:{s_id}"
                    if doc_id in docs_by_id:
                        continue
                    
                    # Format session dialogue turns
                    text_lines = []
                    for turn in turns:
                        speaker = turn.get("speaker", turn.get("role", "Speaker"))
                        content = turn.get("text", turn.get("content", ""))
                        if content:
                            text_lines.append(f"{speaker}: {content}")
                    text = "\n".join(text_lines)
                    
                    ts = self._parse_date_to_timestamp(s_date)
                    doc = BenchmarkDocument(
                        doc_id=doc_id,
                        text=text,
                        session_id=s_id,
                        timestamp=ts,
                        metadata={
                            "benchmark": "longmemeval",
                            "session_id": s_id,
                            "date": s_date
                        }
                    )
                    docs_by_id[doc_id] = doc

                self._loaded_question_ids.append(item["question_id"])
                if limit and len(docs_by_id) >= limit:
                    break
        else:
            # Fallback to materialized corpus.json
            corpus_data = json.loads(self.resolved_path.read_text(encoding="utf-8"))
            for entry in corpus_data:
                meta = entry.get("metadata", {})
                doc = BenchmarkDocument(
                    doc_id=entry["id"],
                    text=entry["text"],
                    session_id=meta.get("session_id", entry["id"]),
                    timestamp=self._parse_date_to_timestamp(meta.get("date", "")),
                    valid_from=meta.get("valid_from", 0),
                    valid_until=meta.get("valid_until", 2**31 - 1),
                    metadata=meta
                )
                docs_by_id[doc.doc_id] = doc
                if limit and len(docs_by_id) >= limit:
                    break

        docs = list(docs_by_id.values())
        return docs[:limit] if limit else docs

    def load_examples(self, limit: Optional[int] = None) -> List[BenchmarkExample]:
        """
        Load evaluation queries, preserving question types and gold answers.
        Prioritizes questions whose session histories were loaded into documents.
        """
        examples: List[BenchmarkExample] = []
        
        if self.resolved_path.name.endswith(".json") and "s_cleaned" in self.resolved_path.name:
            records = json.loads(self.resolved_path.read_text(encoding="utf-8"))
            records_by_qid = {item["question_id"]: item for item in records}
            ordered_items = []
            if hasattr(self, "_loaded_question_ids") and self._loaded_question_ids:
                for qid in self._loaded_question_ids:
                    if qid in records_by_qid:
                        ordered_items.append(records_by_qid[qid])
            for item in records:
                if item not in ordered_items:
                    ordered_items.append(item)

            for item in ordered_items:
                ex = BenchmarkExample(
                    example_id=item["question_id"],
                    query=item["question"],
                    ground_truth_ids=[f"longmemeval:{s_id}" for s_id in item.get("answer_session_ids", [])],
                    gold_answer=str(item.get("answer", "")),
                    category=item.get("question_type", "temporal_qa"),
                    target_date=item.get("question_date"),
                    query_time=self._parse_date_to_timestamp(item.get("question_date", "")),
                    metadata={
                        "raw_answer_session_ids": item.get("answer_session_ids", []),
                        "question_type": item.get("question_type")
                    }
                )
                examples.append(ex)
                if limit and len(examples) >= limit:
                    break
        else:
            # Fallback to data/benchmarks/longmemeval/longmemeval.json
            query_path = Path("data/benchmarks/longmemeval/longmemeval.json")
            if query_path.exists():
                data = json.loads(query_path.read_text(encoding="utf-8"))
                for q in data.get("queries", []):
                    ex = BenchmarkExample(
                        example_id=q["query_id"],
                        query=q["text"],
                        ground_truth_ids=q.get("ground_truth_ids", []),
                        gold_answer=q.get("answer", ""),
                        category="general"
                    )
                    examples.append(ex)
                    if limit and len(examples) >= limit:
                        break

        return examples
