"""
Official Upstream Benchmark Runner: 3 Benchmarks x Upstream Memory Architectures.

Evaluates genuine upstream packages in the isolated environment:
1. MemPalace: official local package (v3.10.0) with GPU ONNX Runtime
2. Mem0: official mem0ai SDK (v2.2.1) with Qdrant + FastEmbed + NVIDIA NIM
3. Zep: official zep-cloud SDK (v3.30.0) Graphiti client
4. Hybrid (Ours): IronWeb Hybrid Memory Engine (Qdrant + Kùzu + BGE reranker)

Saves raw stream logs, resumable checkpoints, and summarized comparison matrices into metrics/official_upstream/.
"""
from __future__ import annotations

import os
import sys
import site
import time
import json
import string
import argparse
from pathlib import Path
from typing import Any, Dict, List, Sequence, Optional
import numpy as np

# Ensure root is in path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


# =============================================================================
# Windows CUDA / NVIDIA DLL Setup
# =============================================================================

def register_nvidia_dlls() -> list[object]:
    handles = []
    directories = []
    for root in map(Path, site.getsitepackages()):
        nvidia = root / "nvidia"
        if not nvidia.exists():
            continue
        for dll_dir in nvidia.glob("*/bin"):
            if dll_dir.is_dir():
                directories.append(str(dll_dir))
                handles.append(os.add_dll_directory(str(dll_dir)))
    if directories:
        os.environ["PATH"] = os.pathsep.join(directories + [os.environ.get("PATH", "")])
    return handles


# =============================================================================
# IR and Generation Metrics (Identical to project harness for fair comparison)
# =============================================================================

def normalize_answer(s: str) -> str:
    def remove_articles(text: str) -> str:
        return " ".join([w for w in text.split() if w.lower() not in {"a", "an", "the"}])

    def white_space_fix(text: str) -> str:
        return " ".join(text.split())

    def remove_punc(text: str) -> str:
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    return white_space_fix(remove_articles(remove_punc(s.lower())))


def compute_exact_match(prediction: str, ground_truth: str) -> float:
    return 1.0 if normalize_answer(prediction) == normalize_answer(ground_truth) else 0.0


def compute_token_f1(prediction: str, ground_truth: str) -> float:
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(ground_truth).split()
    if not pred_tokens or not gold_tokens:
        return 1.0 if pred_tokens == gold_tokens else 0.0
    common = set(pred_tokens) & set(gold_tokens)
    if not common:
        return 0.0
    precision = sum(min(pred_tokens.count(w), gold_tokens.count(w)) for w in common) / len(pred_tokens)
    recall = sum(min(pred_tokens.count(w), gold_tokens.count(w)) for w in common) / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return float(2 * (precision * recall) / (precision + recall))


def compute_substring_match(prediction: str, ground_truth: str) -> float:
    norm_gold = normalize_answer(ground_truth)
    norm_pred = normalize_answer(prediction)
    if not norm_gold or not norm_pred:
        return 0.0
    return 1.0 if norm_gold in norm_pred or norm_pred in norm_gold else 0.0


def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    if not relevant:
        return 1.0
    top_k = retrieved[:k]
    hits = 0
    for rel in relevant:
        if any(ret == rel or ret.endswith(f":{rel}") or rel.endswith(f":{ret}") for ret in top_k):
            hits += 1
    return hits / len(relevant)


def precision_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = 0
    for ret in top_k:
        if any(ret == rel or ret.endswith(f":{rel}") or rel.endswith(f":{ret}") for rel in relevant):
            hits += 1
    return hits / k


def mean_reciprocal_rank(retrieved: Sequence[str], relevant: Sequence[str]) -> float:
    if not relevant:
        return 0.0
    for idx, ret in enumerate(retrieved, start=1):
        if any(ret == rel or ret.endswith(f":{rel}") or rel.endswith(f":{ret}") for rel in relevant):
            return 1.0 / idx
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    if not relevant:
        return 1.0
    top_k = retrieved[:k]
    dcg = 0.0
    for idx, ret in enumerate(top_k, start=1):
        if any(ret == rel or ret.endswith(f":{rel}") or rel.endswith(f":{ret}") for rel in relevant):
            dcg += 1.0 / np.log2(idx + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / np.log2(i + 1) for i in range(1, ideal_hits + 1))
    return float(dcg / idcg) if idcg > 0 else 0.0


def extract_extractive_answer(retrieved_contents: List[str]) -> str:
    if not retrieved_contents:
        return ""
    top_text = retrieved_contents[0]
    for line in top_text.split("\n"):
        line = line.strip()
        if line and not line.lower().startswith("speaker") and not line.lower().startswith("benchmark document id"):
            parts = line.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
            return line
    return top_text[:200].strip()


# =============================================================================
# Upstream Adapters
# =============================================================================

class MemPalaceUpstream:
    def __init__(self, benchmark: str):
        self.benchmark = benchmark
        self.palace_path = str(ROOT / "data" / "official_upstream" / "mempalace" / benchmark)
        self.input_dir = str(ROOT / "data" / "official_upstream" / "mempalace_inputs" / benchmark)
        manifest_file = ROOT / "data" / "official_upstream" / "slices" / f"{benchmark}_20percent_mempalace_manifest.json"
        if manifest_file.exists():
            self.manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        else:
            self.manifest = {}
        os.environ["MEMPALACE_EMBEDDING_DEVICE"] = "cuda"

    def setup_and_ingest(self, documents: List[Dict[str, Any]]):
        chroma_file = Path(self.palace_path) / "chroma.sqlite3"
        if chroma_file.exists():
            print(f"[MemPalace] Palace already mined at {self.palace_path}")
            return
        print(f"[MemPalace] Mining {len(documents)} documents from {self.input_dir} -> {self.palace_path} on GPU...")
        from mempalace.miner import mine
        t0 = time.time()
        mine(project_dir=self.input_dir, palace_path=self.palace_path)
        print(f"[MemPalace] Mining complete in {time.time()-t0:.2f}s")

    def search(self, query: str, k: int = 10) -> tuple[List[str], List[str], float]:
        from mempalace.searcher import search_memories
        t0 = time.perf_counter()
        res = search_memories(query=query, palace_path=self.palace_path, n_results=k)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        hits = res.get("results", [])
        retrieved_ids = []
        retrieved_contents = []
        for h in hits:
            source_file = h.get("source_file", "")
            doc_id = self.manifest.get(source_file, "")
            if not doc_id:
                # Fallback to doc_id in text
                text = h.get("text", "")
                if "Benchmark document ID:" in text:
                    doc_id = text.split("Benchmark document ID:", 1)[1].split("\n", 1)[0].strip()
            retrieved_ids.append(doc_id)
            retrieved_contents.append(h.get("text", ""))
        return retrieved_ids, retrieved_contents, latency_ms


class Mem0Upstream:
    def __init__(self, benchmark: str):
        self.benchmark = benchmark
        self.db_path = str(ROOT / "data" / "official_upstream" / "mem0_dbs" / benchmark)
        os.makedirs(self.db_path, exist_ok=True)
        self.checkpoint_path = Path(self.db_path) / "ingestion_checkpoint.json"

        from mem0 import Memory
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "path": self.db_path,
                    "on_disk": True,
                    "embedding_model_dims": 384
                }
            },
            "embedder": {
                "provider": "fastembed",
                "config": {
                    "model": "BAAI/bge-small-en-v1.5"
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "meta/llama-3.2-11b-vision-instruct",
                    "api_key": os.environ.get("NVIDIA_API_KEY"),
                    "openai_base_url": "https://integrate.api.nvidia.com/v1"
                }
            },
            "version": "v1.1"
        }
        self.memory = Memory.from_config(config)

    def setup_and_ingest(self, documents: List[Dict[str, Any]]):
        ingested_ids = set()
        if self.checkpoint_path.exists():
            try:
                ingested_ids = set(json.loads(self.checkpoint_path.read_text(encoding="utf-8")))
            except Exception:
                pass
        
        remaining = [d for d in documents if d["doc_id"] not in ingested_ids]
        print(f"[Mem0] Already ingested: {len(ingested_ids)} / {len(documents)}. Remaining to ingest: {len(remaining)}")
        if not remaining:
            return

        t0 = time.time()
        for idx, doc in enumerate(remaining, start=1):
            doc_t0 = time.time()
            try:
                self.memory.add(
                    doc["text"],
                    metadata={"doc_id": doc["doc_id"]},
                    user_id=f"user_{self.benchmark}",
                    infer=False
                )
                ingested_ids.add(doc["doc_id"])
                if idx % 20 == 0 or idx == len(remaining):
                    self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")
                    print(f"[Mem0] Ingested {len(ingested_ids)}/{len(documents)} ({time.time()-doc_t0:.3f}s last doc)", flush=True)
            except Exception as e:
                print(f"[Mem0] Warning: failed adding doc {doc['doc_id']}: {e}", flush=True)
                self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")

        self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")
        print(f"[Mem0] Ingestion phase finished in {time.time()-t0:.2f}s", flush=True)

    def search(self, query: str, k: int = 10) -> tuple[List[str], List[str], float]:
        t0 = time.perf_counter()
        try:
            res = self.memory.search(query, filters={"user_id": f"user_{self.benchmark}"}, limit=k)
        except Exception as e:
            print(f"[Mem0] Search error: {e}")
            res = {"results": []}
        latency_ms = (time.perf_counter() - t0) * 1000.0
        
        hits = res.get("results", [])
        retrieved_ids = []
        retrieved_contents = []
        for h in hits:
            meta = h.get("metadata") or {}
            doc_id = meta.get("doc_id", "")
            if not doc_id:
                mem_txt = h.get("memory", "")
                if "Benchmark document ID:" in mem_txt:
                    doc_id = mem_txt.split("Benchmark document ID:", 1)[1].split("\n", 1)[0].strip()
            retrieved_ids.append(doc_id)
            retrieved_contents.append(h.get("memory", ""))
        return retrieved_ids, retrieved_contents, latency_ms


class ZepUpstream:
    def __init__(self, benchmark: str):
        self.benchmark = benchmark
        self.user_id = f"eval_official_{benchmark}_20pct"
        db_dir = ROOT / "data" / "official_upstream" / "zep_dbs"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = db_dir / f"{benchmark}_ingested.json"

        from zep_cloud.client import Zep
        self.client = Zep(api_key=os.environ.get("ZEP_API_KEY"))
        # Ensure user exists
        try:
            self.client.user.add(user_id=self.user_id)
        except Exception:
            pass

    def setup_and_ingest(self, documents: List[Dict[str, Any]]):
        ingested_ids = set()
        if self.checkpoint_path.exists():
            try:
                ingested_ids = set(json.loads(self.checkpoint_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        remaining = [d for d in documents if d["doc_id"] not in ingested_ids]
        print(f"[Zep] Already ingested: {len(ingested_ids)} / {len(documents)}. Remaining: {len(remaining)}")
        if not remaining:
            return

        t0 = time.time()
        for idx, doc in enumerate(remaining, start=1):
            max_retries = 4
            for attempt in range(max_retries):
                try:
                    self.client.graph.add(
                        user_id=self.user_id,
                        data=doc["text"],
                        type="text",
                        document_id=doc["doc_id"],
                        metadata={"doc_id": doc["doc_id"]}
                    )
                    ingested_ids.add(doc["doc_id"])
                    if idx % 10 == 0 or idx == len(remaining):
                        self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")
                        print(f"[Zep] Ingested {len(ingested_ids)}/{len(documents)} ({time.time()-t0:.1f}s)", flush=True)
                    break  # success
                except Exception as e:
                    err_str = str(e)
                    # Parse retry-after from the error body if rate-limited
                    retry_after = 60  # default backoff
                    if "429" in err_str or "Rate limit" in err_str:
                        import re
                        m = re.search(r"retry-after':\s*'(\d+)'", err_str)
                        if m:
                            retry_after = int(m.group(1)) + 2
                        if attempt < max_retries - 1:
                            print(f"[Zep] Rate-limited on doc {doc['doc_id']} (attempt {attempt+1}/{max_retries}). Sleeping {retry_after}s...", flush=True)
                            time.sleep(retry_after)
                            continue
                    # Non-429 error or final attempt — skip
                    print(f"[Zep] Warning: giving up on doc {doc['doc_id']} after {attempt+1} attempts: {err_str[:120]}", flush=True)
                    self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")
                    break

        print(f"[Zep] Ingestion finished in {time.time()-t0:.2f}s")

    def search(self, query: str, k: int = 10) -> tuple[List[str], List[str], float]:
        t0 = time.perf_counter()
        try:
            res = self.client.graph.search(user_id=self.user_id, query=query, scope="episodes", limit=k)
        except Exception as e:
            print(f"[Zep] Search error: {e}")
            res = None
        latency_ms = (time.perf_counter() - t0) * 1000.0

        retrieved_ids = []
        retrieved_contents = []
        if res and res.episodes:
            for ep in res.episodes:
                meta = ep.metadata or {}
                doc_id = meta.get("doc_id", "") or ep.document_id or ""
                if not doc_id and "Benchmark document ID:" in ep.content:
                    doc_id = ep.content.split("Benchmark document ID:", 1)[1].split("\n", 1)[0].strip()
                retrieved_ids.append(doc_id)
                retrieved_contents.append(ep.content)
        return retrieved_ids, retrieved_contents, latency_ms


class HybridUpstream:
    """
    Adapter for our own IronWeb Hybrid Memory Engine.
    Uses an isolated Qdrant + Kùzu store per benchmark under
    data/official_upstream/hybrid_dbs/<benchmark>/.
    Runs in the project .venv (same process), so no cross-venv issues.
    """

    def __init__(self, benchmark: str):
        self.benchmark = benchmark
        db_dir = ROOT / "data" / "official_upstream" / "hybrid_dbs" / benchmark
        db_dir.mkdir(parents=True, exist_ok=True)
        qdrant_path = str(db_dir / "qdrant")
        kuzu_path = str(db_dir / "kuzu" / "memory.db")
        self.checkpoint_path = db_dir / "ingestion_checkpoint.json"

        # Import from project root (already on sys.path)
        from memory.engine import MemoryEngine
        self.engine = MemoryEngine(
            qdrant_path=qdrant_path,
            kuzu_path=kuzu_path,
            use_gpu=True,
        )

    def setup_and_ingest(self, documents: List[Dict[str, Any]]):
        ingested_ids: set = set()
        if self.checkpoint_path.exists():
            try:
                ingested_ids = set(json.loads(self.checkpoint_path.read_text(encoding="utf-8")))
            except Exception:
                pass

        remaining = [d for d in documents if d["doc_id"] not in ingested_ids]
        print(f"[Hybrid] Already ingested: {len(ingested_ids)}/{len(documents)}. Remaining: {len(remaining)}")
        if not remaining:
            return

        t0 = time.time()

        # ── STEP 1: GPU BATCH EMBED — one forward pass for all docs ───────
        texts = [d["text"] for d in remaining]
        print(f"[Hybrid] Batch-embedding {len(texts)} docs on GPU...", flush=True)
        embeddings = self.engine.embedder.embed(texts)   # (N, 384) — single CUDA kernel
        print(f"[Hybrid] Embedding complete in {time.time()-t0:.1f}s", flush=True)

        # ── STEP 2: BULK QDRANT UPSERT — direct vector store writes ───────
        # Skips slow per-doc Kùzu graph writes; vector+reranker search still
        # fully active. Graph expansion returns empty (no-op) during search.
        BATCH = 256
        ts_now = int(time.time())
        for batch_start in range(0, len(remaining), BATCH):
            batch_docs = remaining[batch_start: batch_start + BATCH]
            batch_embs = embeddings[batch_start: batch_start + BATCH]
            for doc, emb in zip(batch_docs, batch_embs):
                mem_id = doc["doc_id"].replace(":", "_").replace("-", "_")[:64]
                try:
                    self.engine.vector_store.upsert_memory(
                        memory_id=mem_id,
                        text=doc["text"],
                        embedding=emb,
                        entity_ids=[],
                        valid_from=doc.get("valid_from", 0),
                        valid_until=doc.get("valid_until", 2**31 - 1),
                        importance=1.0,
                        metadata={"doc_id": doc["doc_id"], **doc.get("metadata", {})},
                        timestamp=doc.get("timestamp") or ts_now,
                    )
                    ingested_ids.add(doc["doc_id"])
                except Exception as e:
                    print(f"[Hybrid] Upsert error {doc['doc_id']}: {e}", flush=True)
            # checkpoint after each batch
            self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")
            done = min(batch_start + BATCH, len(remaining))
            print(f"[Hybrid] Upserted {done}/{len(remaining)} ({time.time()-t0:.1f}s)", flush=True)

        self.checkpoint_path.write_text(json.dumps(list(ingested_ids)), encoding="utf-8")
        print(f"[Hybrid] Ingestion finished in {time.time()-t0:.2f}s total", flush=True)

    def search(self, query: str, k: int = 10) -> tuple[List[str], List[str], float]:
        t0 = time.perf_counter()
        try:
            results = self.engine.search(query=query, k=k, retrieval_mode="hybrid")
        except Exception as e:
            print(f"[Hybrid] Search error: {e}")
            results = []
        latency_ms = (time.perf_counter() - t0) * 1000.0

        retrieved_ids = []
        retrieved_contents = []
        for r in results:
            # doc_id was stored in metadata
            meta = r.metadata or {}
            doc_id = meta.get("doc_id", "")
            if not doc_id:
                # Fallback: parse from content header
                text = r.content or ""
                if "Benchmark document ID:" in text:
                    doc_id = text.split("Benchmark document ID:", 1)[1].split("\n", 1)[0].strip()
                else:
                    # memory_id was sanitised — try to reverse
                    doc_id = r.memory_id
            retrieved_ids.append(doc_id)
            retrieved_contents.append(r.content or "")
        return retrieved_ids, retrieved_contents, latency_ms


# =============================================================================
# Benchmark Evaluation Loop
# =============================================================================

def evaluate_architecture_on_benchmark(
    arch_name: str,
    arch_adapter: Any,
    benchmark_name: str,
    slice_data: Dict[str, Any],
    k: int = 10,
    output_dir: Path = None,
    max_eval_examples: Optional[int] = None
) -> Dict[str, Any]:
    print(f"\n" + "=" * 70)
    print(f"EVALUATING: {arch_name.upper()} on {benchmark_name.upper()}")
    print("=" * 70)

    bench_out_dir = output_dir / benchmark_name
    bench_out_dir.mkdir(parents=True, exist_ok=True)
    raw_file = bench_out_dir / f"{arch_name}_eval_results.jsonl"
    summary_file = bench_out_dir / f"{arch_name}_summary.json"

    # Step 1: Ingest
    arch_adapter.setup_and_ingest(slice_data["documents"])

    # Step 2: Evaluate queries with checkpointing
    examples = slice_data["examples"]
    if max_eval_examples:
        examples = examples[:max_eval_examples]

    processed_ids = set()
    existing_records = []
    if raw_file.exists():
        for line in raw_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    processed_ids.add(rec["example_id"])
                    existing_records.append(rec)
                except Exception:
                    pass
        print(f"[{arch_name}] Resuming: found {len(processed_ids)} previously evaluated examples.")

    results = list(existing_records)
    with open(raw_file, "a", encoding="utf-8") as f_out:
        for idx, ex in enumerate(examples, start=1):
            ex_id = ex["example_id"]
            if ex_id in processed_ids:
                continue

            query = ex["query"]
            rel_ids = ex["ground_truth_ids"]
            gold_ans = ex.get("gold_answer", "")
            cat = ex.get("category", "default")

            ret_ids, ret_contents, latency_ms = arch_adapter.search(query=query, k=k)
            pred_ans = extract_extractive_answer(ret_contents)

            rec_10 = recall_at_k(ret_ids, rel_ids, k=10)
            prec_10 = precision_at_k(ret_ids, rel_ids, k=10)
            mrr_val = mean_reciprocal_rank(ret_ids, rel_ids)
            ndcg_10 = ndcg_at_k(ret_ids, rel_ids, k=10)
            em_val = compute_exact_match(pred_ans, gold_ans)
            f1_val = compute_token_f1(pred_ans, gold_ans)
            sub_val = compute_substring_match(pred_ans, gold_ans)

            record = {
                "benchmark": benchmark_name,
                "architecture": arch_name,
                "example_id": ex_id,
                "category": cat,
                "query": query,
                "retrieved_ids": ret_ids,
                "relevant_ids": rel_ids,
                "prediction": pred_ans,
                "gold_answer": gold_ans,
                "recall@10": rec_10,
                "precision@10": prec_10,
                "mrr": mrr_val,
                "ndcg@10": ndcg_10,
                "exact_match": em_val,
                "token_f1": f1_val,
                "substring_match": sub_val,
                "latency_ms": latency_ms
            }

            results.append(record)
            f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
            f_out.flush()

            if idx % 50 == 0 or idx == len(examples):
                print(f"[{arch_name}] Evaluated {len(results)}/{len(examples)} examples (current R@10: {rec_10:.2f}, Latency: {latency_ms:.1f}ms)")

    # Aggregate metrics
    n = len(results)
    if n == 0:
        return {}

    mean_recall = float(np.mean([r["recall@10"] for r in results]))
    mean_precision = float(np.mean([r["precision@10"] for r in results]))
    mean_mrr = float(np.mean([r["mrr"] for r in results]))
    mean_ndcg = float(np.mean([r["ndcg@10"] for r in results]))
    mean_em = float(np.mean([r["exact_match"] for r in results]))
    mean_f1 = float(np.mean([r["token_f1"] for r in results]))
    mean_sub = float(np.mean([r["substring_match"] for r in results]))
    mean_latency = float(np.mean([r["latency_ms"] for r in results]))

    # By category
    cats: Dict[str, Dict[str, Any]] = {}
    for r in results:
        c = r["category"]
        if c not in cats:
            cats[c] = {"recalls": [], "mrrs": [], "f1s": []}
        cats[c]["recalls"].append(r["recall@10"])
        cats[c]["mrrs"].append(r["mrr"])
        cats[c]["f1s"].append(r["token_f1"])

    by_category = {}
    for c, data in cats.items():
        by_category[c] = {
            "count": len(data["recalls"]),
            "recall@10": float(np.mean(data["recalls"])),
            "mrr": float(np.mean(data["mrrs"])),
            "token_f1": float(np.mean(data["f1s"]))
        }

    summary = {
        "benchmark": benchmark_name,
        "architecture": arch_name,
        "num_examples": n,
        "recall@10": mean_recall,
        "precision@10": mean_precision,
        "mrr": mean_mrr,
        "ndcg@10": mean_ndcg,
        "exact_match": mean_em,
        "token_f1": mean_f1,
        "substring_match": mean_sub,
        "mean_retrieval_ms": mean_latency,
        "by_category": by_category
    }

    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== SUMMARY: {arch_name.upper()} on {benchmark_name.upper()} ===")
    print(f"Recall@10:       {mean_recall:.4f}")
    print(f"Precision@10:    {mean_precision:.4f}")
    print(f"MRR:             {mean_mrr:.4f}")
    print(f"NDCG@10:         {mean_ndcg:.4f}")
    print(f"Token F1:        {mean_f1:.4f}")
    print(f"Mean Latency:    {mean_latency:.2f} ms")
    print(f"Summary saved to: {summary_file}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Official Upstream Benchmark Evaluation")
    parser.add_argument("--benchmarks", nargs="+", default=["locomo", "dmr", "longmemeval"])
    parser.add_argument("--architectures", nargs="+", default=["mempalace", "mem0", "zep", "hybrid"])
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output-dir", type=str, default="metrics/official_upstream")
    parser.add_argument("--max-eval-examples", type=int, default=None)
    args = parser.parse_args()

    # Preflight registration
    register_nvidia_dlls()

    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    slices_dir = ROOT / "data" / "official_upstream" / "slices"
    all_summaries: Dict[str, Dict[str, Any]] = {}

    for bench in args.benchmarks:
        slice_path = slices_dir / f"{bench}_20percent.json"
        if not slice_path.exists():
            print(f"Error: slice file {slice_path} not found. Run export_official_20percent_slice.py first.")
            continue

        slice_data = json.loads(slice_path.read_text(encoding="utf-8"))
        all_summaries[bench] = {}

        for arch in args.architectures:
            if arch == "mempalace":
                adapter = MemPalaceUpstream(bench)
            elif arch == "mem0":
                adapter = Mem0Upstream(bench)
            elif arch == "zep":
                adapter = ZepUpstream(bench)
            elif arch == "hybrid":
                adapter = HybridUpstream(bench)
            else:
                print(f"Unknown architecture: {arch}")
                continue

            summary = evaluate_architecture_on_benchmark(
                arch_name=arch,
                arch_adapter=adapter,
                benchmark_name=bench,
                slice_data=slice_data,
                k=args.k,
                output_dir=out_dir,
                max_eval_examples=args.max_eval_examples
            )
            all_summaries[bench][arch] = summary

        # Write per-benchmark combined matrix
        bench_combined = out_dir / f"{bench}_upstream_comparison.json"
        bench_combined.write_text(json.dumps(all_summaries[bench], indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate Unified Markdown Table
    md_file = out_dir / "summary_table.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# Empirical Evaluation Matrix: Official Upstream Baselines (20% Slice)\n\n")
        f.write("| Benchmark | Architecture | Recall@10 | Precision@10 | MRR | NDCG@10 | Token F1 | Mean Latency |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for b_name, b_data in all_summaries.items():
            for a_name, data in b_data.items():
                if not data:
                    continue
                f.write(
                    f"| {b_name.upper()} | {a_name.upper()} | "
                    f"{data['recall@10']:.4f} | "
                    f"{data['precision@10']:.4f} | "
                    f"{data['mrr']:.4f} | "
                    f"{data['ndcg@10']:.4f} | "
                    f"{data['token_f1']:.4f} | "
                    f"{data['mean_retrieval_ms']:.2f} ms |\n"
                )
            f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")

    print(f"\nAll evaluations complete. Markdown table: {md_file}")


if __name__ == "__main__":
    main()
