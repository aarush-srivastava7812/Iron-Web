"""Materialize Phase 2 DMR corpus/query files from the official MSC release."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "datasets" / "dmr" / "msc_self_instruct.jsonl"
OUTPUT = ROOT / "data" / "benchmarks" / "dmr"


def dialog_text(dialog: list[dict]) -> str:
    return "\n".join(f"{turn.get('id', 'speaker')}: {turn['text']}" for turn in dialog)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Official DMR source missing: {SOURCE}")
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line]
    corpus, queries = [], []
    for index, row in enumerate(rows):
        conversation_id = f"dmr:{index:04d}"
        dialogs = row.get("previous_dialogs", []) + [{"dialog": row["dialog"], "metadata": row.get("metadata", {})}]
        for session_index, session in enumerate(dialogs):
            corpus.append({
                "id": f"{conversation_id}:session:{session_index}",
                "text": dialog_text(session["dialog"]),
                "metadata": {"benchmark": "dmr", "conversation_id": conversation_id, "session_index": session_index, **session.get("metadata", {})},
            })
        pair = row.get("self_instruct", {})
        if pair.get("B") and pair.get("A"):
            queries.append({"query_id": f"{conversation_id}:qa", "text": pair["B"], "ground_truth_ids": [f"{conversation_id}:session:{session_index}"], "answer": pair["A"]})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    (OUTPUT / "dmr.json").write_text(json.dumps({"queries": queries}, ensure_ascii=False), encoding="utf-8")
    print(f"conversations={len(rows)} queries={len(queries)} documents={len(corpus)}")


if __name__ == "__main__":
    main()
