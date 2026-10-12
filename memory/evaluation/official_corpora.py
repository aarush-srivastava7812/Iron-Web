"""Adapters that expose official benchmark releases as Phase 2 documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LOCOMO_PATH = ROOT / "datasets" / "locomo" / "data" / "locomo10.json"
LONGMEMEVAL_PATH = ROOT / "datasets" / "longmemeval" / "data" / "longmemeval_s_cleaned.json"


def _session_text(turns: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{turn.get('speaker', turn.get('role', 'unknown'))}: {turn['text' if 'text' in turn else 'content']}"
        for turn in turns
        if turn.get("text") or turn.get("content")
    )


def load_official_locomo() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return all official LoCoMo session documents and QA annotations."""
    if not LOCOMO_PATH.exists():
        raise FileNotFoundError(f"Official LoCoMo release not found: {LOCOMO_PATH}")
    records = json.loads(LOCOMO_PATH.read_text(encoding="utf-8"))
    corpus: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    for record in records:
        sample_id, conversation = record["sample_id"], record["conversation"]
        for key, turns in conversation.items():
            if key.startswith("session_") and isinstance(turns, list):
                corpus.append({"id": f"locomo:{sample_id}:{key}", "text": _session_text(turns), "metadata": {"sample_id": sample_id, "session": key, "benchmark": "locomo"}})
        for index, qa in enumerate(record.get("qa", [])):
            queries.append({"query_id": f"locomo:{sample_id}:qa:{index}", "text": qa["question"], "ground_truth_ids": []})
    return corpus, queries


def load_official_longmemeval(question_limit: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Return unique history sessions for the first official LongMemEval questions."""
    if not LONGMEMEVAL_PATH.exists():
        raise FileNotFoundError(f"Official LongMemEval S-cleaned release not found: {LONGMEMEVAL_PATH}")
    records = json.loads(LONGMEMEVAL_PATH.read_text(encoding="utf-8"))
    corpus_by_id: dict[str, dict[str, Any]] = {}
    queries: list[dict[str, Any]] = []
    for item in records[:question_limit]:
        queries.append({"query_id": item["question_id"], "text": item["question"], "ground_truth_ids": [f"longmemeval:{session_id}" for session_id in item["answer_session_ids"]]})
        for session_id, date, turns in zip(item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]):
            corpus_by_id.setdefault(f"longmemeval:{session_id}", {"id": f"longmemeval:{session_id}", "text": _session_text(turns), "metadata": {"session_id": session_id, "date": date, "benchmark": "longmemeval"}})
    return list(corpus_by_id.values()), queries, len(records)
