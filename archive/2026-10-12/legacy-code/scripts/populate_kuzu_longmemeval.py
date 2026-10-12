"""
Targeted Kuzu graph populator for LongMemEval hybrid benchmark.
Qdrant already has all 3839 docs. This adds missing Kuzu graph data
by calling engine.add() for docs not yet in Kuzu.
Run: .venv\Scripts\python.exe scripts\populate_kuzu_longmemeval.py
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SLICE_PATH = ROOT / "data" / "official_upstream" / "slices" / "longmemeval_20percent.json"
DB_DIR     = ROOT / "data" / "official_upstream" / "hybrid_dbs" / "longmemeval"
KUZU_CKPT  = DB_DIR / "kuzu_ingestion_checkpoint.json"

def main():
    print("Loading slice...", flush=True)
    documents = json.loads(SLICE_PATH.read_text(encoding="utf-8"))["documents"]
    print(f"Total docs: {len(documents)}", flush=True)

    kuzu_done: set = set()
    if KUZU_CKPT.exists():
        try:
            kuzu_done = set(json.loads(KUZU_CKPT.read_text(encoding="utf-8")))
        except Exception:
            pass
    print(f"Already in Kuzu: {len(kuzu_done)}", flush=True)

    remaining = [d for d in documents if d["doc_id"] not in kuzu_done]
    print(f"To populate: {len(remaining)}", flush=True)
    if not remaining:
        print("Kuzu already fully populated. Done.")
        return

    from memory.engine import MemoryEngine
    engine = MemoryEngine(
        qdrant_path=str(DB_DIR / "qdrant"),
        kuzu_path=str(DB_DIR / "kuzu" / "memory.db"),
        use_gpu=True,
    )

    t0 = time.time()
    for idx, doc in enumerate(remaining, start=1):
        try:
            engine.add(
                content=doc["text"],
                metadata={"doc_id": doc["doc_id"], **doc.get("metadata", {})},
                memory_id=doc["doc_id"].replace(":", "_").replace("-", "_")[:64],
                valid_from=doc.get("valid_from", 0),
                valid_until=doc.get("valid_until", 2**31 - 1),
                timestamp=doc.get("timestamp") or int(time.time()),
            )
            kuzu_done.add(doc["doc_id"])
        except Exception as e:
            print(f"[WARN] Failed {doc['doc_id']}: {e}", flush=True)

        if idx % 50 == 0 or idx == len(remaining):
            elapsed = time.time() - t0
            rate = idx / elapsed
            eta_min = (len(remaining) - idx) / rate / 60
            KUZU_CKPT.write_text(json.dumps(list(kuzu_done)), encoding="utf-8")
            print(f"[{idx}/{len(remaining)}] {elapsed:.0f}s | {rate:.2f} doc/s | ETA: {eta_min:.1f} min", flush=True)

    KUZU_CKPT.write_text(json.dumps(list(kuzu_done)), encoding="utf-8")
    print(f"Done! {len(kuzu_done)} docs in Kuzu. Total: {(time.time()-t0)/3600:.2f}hrs")
    print("Re-run eval: .venv\\Scripts\\python.exe scripts\\run_official_upstream_benchmarks.py --benchmarks longmemeval --architectures hybrid")

if __name__ == "__main__":
    main()
