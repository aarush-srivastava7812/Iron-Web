"""Create a new derived MSC corpus/query version; preserves raw source and prior versions."""

from __future__ import annotations

import json
import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "datasets" / "dmr" / "msc_self_instruct.jsonl"


def dialog_text(dialog: list[dict]) -> str:
    return "\n".join(f"{turn.get('id', 'speaker')}: {turn['text']}" for turn in dialog)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="A new derived dataset directory.")
    output_dir = Path(parser.parse_args().destination)
    if output_dir.exists():
        raise FileExistsError("Derived dataset version already exists.")
    if not SOURCE.exists():
        raise FileNotFoundError(f"Official DMR source missing: {SOURCE}")
    rows = [
        json.loads(line)
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line
    ]
    corpus, queries = [], []
    for index, row in enumerate(rows):
        conversation_id = f"dmr:{index:04d}"
        dialogs = row.get("previous_dialogs", []) + [
            {"dialog": row["dialog"], "metadata": row.get("metadata", {})}
        ]
        for session_index, session in enumerate(dialogs):
            corpus.append(
                {
                    "id": f"{conversation_id}:session:{session_index}",
                    "text": dialog_text(session["dialog"]),
                    "metadata": {
                        "benchmark": "dmr",
                        "conversation_id": conversation_id,
                        "session_index": session_index,
                        **session.get("metadata", {}),
                    },
                }
            )
        pair = row.get("self_instruct", {})
        if pair.get("B") and pair.get("A"):
            queries.append(
                {
                    "query_id": f"{conversation_id}:qa",
                    "text": pair["B"],
                    "ground_truth_ids": [f"{conversation_id}:session:{session_index}"],
                    "answer": pair["A"],
                }
            )
    output_dir.mkdir(parents=True)
    (output_dir / "corpus.json").write_text(
        json.dumps(corpus, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "dmr.json").write_text(
        json.dumps({"queries": queries}, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "conversion_manifest.json").write_text(
        json.dumps(
            dict(
                source=str(SOURCE),
                source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                converter_sha256=hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
                source_rows=len(rows),
                documents=len(corpus),
                questions=len(queries),
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"conversations={len(rows)} queries={len(queries)} documents={len(corpus)}")


if __name__ == "__main__":
    main()
