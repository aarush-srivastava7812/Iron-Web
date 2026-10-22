"""Fresh sampled source-retrieval checks; no hosted models or web requests.

Uses the current Iron Web 2 engine and complete histories for a predeclared
release-order sample. This is not official benchmark answer scoring, a
temporal-reasoning evaluation, or a measurement of TinyFish's contribution.
"""

# ruff: noqa: E402 -- Bind the repository and CPU/offline runtime before imports.
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("USE_GPU", "false")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from memory.engine import MemoryEngine
from memory.evaluation.harness.runner import BenchmarkRunner

OUTPUT = ROOT / "report/tinyfish_memory/memory-benchmarks.json"


def terms(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def lexical_index(docs):
    counts = [collections.Counter(terms(d.text)) for d in docs]
    lengths = [sum(c.values()) for c in counts]
    average = statistics.mean(lengths)
    frequencies = collections.Counter(t for c in counts for t in c)

    def search(query, allowed):
        scores = []
        for d, count, size in zip(docs, counts, lengths):
            if allowed is not None and d.doc_id not in allowed:
                continue
            score = 0.0
            for token in set(terms(query)):
                tf = count[token]
                if tf:
                    df = frequencies[token]
                    idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
                    score += (
                        idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * size / average))
                    )
            scores.append((score, d.doc_id))
        return [
            identifier
            for _, identifier in sorted(scores, key=lambda x: (-x[0], x[1]))[:5]
        ]

    return search


def quality(ids, gold):
    gold = set(gold)
    return dict(
        recall_at_5=len(set(ids) & gold) / len(gold),
        hit_at_5=float(bool(set(ids) & gold)),
        mrr=next(
            (1 / i for i, identifier in enumerate(ids, 1) if identifier in gold), 0.0
        ),
    )


def run():
    report = dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        schema="presentation-memory-source-retrieval-v1",
        scope="Fresh CPU source retrieval on real local datasets; first 20 LoCoMo, 20 project DMR/MSC and 5 LongMemEval questions in release order, retaining complete selected histories. Not official full-dataset answer accuracy. No TinyFish requests or improvement attribution. Historical query_time is not applied: current source retrieval only.",
        selection={"locomo": 20, "dmr": 20, "longmemeval": 5},
        k=5,
        baseline="BM25 lexical retrieval (k1=1.5, b=0.75), identical documents and scope",
        engine="Current ApplicationMemoryEngine / Iron Web 2 / FalkorDB / cached CPU embeddings / no reranker",
        datasets=[],
        reproduction=".venv/Scripts/python.exe scripts/measure_memory_presentation.py",
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for benchmark, count in report["selection"].items():
        adapter = BenchmarkRunner.ADAPTER_REGISTRY[benchmark]()
        all_docs = adapter.load_documents()
        examples = adapter.load_examples(limit=count)
        if any(
            not e.ground_truth_ids or e.metadata.get("unmapped_evidence")
            for e in examples
        ):
            raise ValueError("Sample has missing evidence; do not silently skip cases")
        needed = set().union(
            *(
                set(e.ground_truth_ids) | set(e.metadata.get("corpus_ids", []))
                for e in examples
            )
        )
        if benchmark == "dmr":
            prefixes = {
                e.example_id.rsplit(":qa", 1)[0] + ":session:" for e in examples
            }
            needed |= {
                d.doc_id
                for d in all_docs
                if any(d.doc_id.startswith(p) for p in prefixes)
            }
        docs = [d for d in all_docs if d.doc_id in needed]
        if needed - {d.doc_id for d in docs}:
            raise ValueError("Incomplete sample history")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "documents": [(d.doc_id, d.text) for d in docs],
                    "questions": [
                        (e.example_id, e.query, e.ground_truth_ids) for e in examples
                    ],
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        lexical = lexical_index(docs)
        name = "test_presentation_" + benchmark + "_" + uuid.uuid4().hex
        engine = MemoryEngine(graph_name=name, use_gpu=False)
        rows = []
        started = time.perf_counter()
        try:
            for index, doc in enumerate(docs):
                engine.add(
                    doc.text,
                    memory_id=doc.doc_id,
                    metadata=doc.metadata,
                    timestamp=doc.timestamp,
                    valid_from=doc.valid_from,
                    valid_until=doc.valid_until,
                )
                if (index + 1) % 25 == 0:
                    print(f"{benchmark}: ingested {index+1}/{len(docs)}", flush=True)
            ingestion_ms = (time.perf_counter() - started) * 1000
            for example in examples:
                allowed = example.metadata.get("corpus_ids")
                t = time.perf_counter()
                baseline_ids = lexical(
                    example.query, set(allowed) if allowed is not None else None
                )
                baseline_ms = (time.perf_counter() - t) * 1000
                t = time.perf_counter()
                hits = engine.search(example.query, k=5, document_ids=allowed)
                native_ms = (time.perf_counter() - t) * 1000
                rows.append(
                    dict(
                        example_id=example.example_id,
                        ground_truth_ids=example.ground_truth_ids,
                        lexical_ids=baseline_ids,
                        native_ids=[h.memory_id for h in hits],
                        lexical=quality(baseline_ids, example.ground_truth_ids),
                        native=quality(
                            [h.memory_id for h in hits], example.ground_truth_ids
                        ),
                        lexical_ms=round(baseline_ms, 3),
                        native_ms=round(native_ms, 3),
                    )
                )
            entry = dict(
                benchmark=benchmark,
                questions=len(examples),
                documents=len(docs),
                input_sha256=fingerprint,
                ingestion_ms=round(ingestion_ms, 2),
                rows=rows,
            )
            for mode in ["lexical", "native"]:
                entry[mode] = {
                    metric: statistics.mean(r[mode][metric] for r in rows)
                    for metric in ["recall_at_5", "hit_at_5", "mrr"]
                }
                entry[mode]["median_ms"] = statistics.median(
                    r[mode + "_ms"] for r in rows
                )
            report["datasets"].append(entry)
            print(
                json.dumps({k: v for k, v in entry.items() if k != "rows"}), flush=True
            )
        finally:
            # This graph was created with a fresh UUID above; no application store is touched.
            if not engine.graph_name.startswith("iron_web_2_test_"):
                raise RuntimeError("Unexpected graph namespace; refusing cleanup")
            engine.graph_store.graph.delete()
            engine.close()
        OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["status"] = "passed"
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
