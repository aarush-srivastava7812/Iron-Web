"""Compare existing local Qdrant with native FalkorDB vectors on retained slices.

Run from the workspace with --report PATH --datasets dmr locomo longmemeval.
Only isolated graph names and copied Qdrant stores are written. The actual current
MemoryEngine supplies full retrieval and mixed reads/writes. No LLM answers,
framework integrations, production config changes or cache experiments occur.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from threading import Barrier
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import numpy as np

from memory.engine import MemoryEngine
from memory.embeddings.embedder import Embedder
from memory.evaluation.retrieval_metrics import compute_retrieval_metrics
from memory.evaluation.slices import load_slice
from memory.graph import FalkorDBGraphStore
from memory.vector_store.qdrant_store import QdrantVectorStore, create_search_filter
from scripts.migrate_kuzu_to_falkordb import import_graph, falkor_snapshot, snapshot_hash
from scripts.vector_placement.falkor_vector import FalkorVectorExperiment


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def emit(**value):
    print(json.dumps(value), flush=True)


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def tree_digest(path):
    return {str(p.relative_to(path)):digest(p) for p in sorted(path.rglob("*")) if p.is_file()}


def stats(rows):
    ms = [r["ms"] for r in rows]
    return dict(samples=len(rows), errors=sum(bool(r.get("error")) for r in rows),
                p50_ms=float(np.percentile(ms, 50)), p95_ms=float(np.percentile(ms, 95)),
                mean_ms=float(np.mean(ms)))


def aggregate(rows):
    referenced = [r for r in rows if r["gold"]]
    unlabelled = [r for r in rows if not r["gold"]]
    keys = ["recall@5", "precision@5", "ndcg@5", "recall@10", "precision@10", "ndcg@10"]
    return dict(questions_with_reference_evidence=len(referenced), questions_without_reference_evidence=len(unlabelled),
                empty_results_without_reference_evidence=sum(not r["ids"] for r in unlabelled),
                **{key:float(np.mean([r["metrics"][key] for r in referenced])) if referenced else None for key in keys})


def bootstrap_ratio(base, candidate, kind, seed=4913):
    """Paired question-block resampling; repeated timings are not independent QAs."""
    if not len(base) or not np.mean(base):
        return None
    rng = np.random.default_rng(seed)
    ratios = []
    for _ in range(1000):
        chosen = rng.integers(0, len(base), len(base))
        if kind == "p50":
            b, c = np.percentile(base[chosen],50), np.percentile(candidate[chosen],50)
        elif kind == "p95":
            b, c = np.percentile(base[chosen],95), np.percentile(candidate[chosen],95)
        else:
            b, c = np.mean(base[chosen]), np.mean(candidate[chosen])
        if b > 0:
            ratios.append(c/b)
    return [float(x) for x in np.percentile(ratios,[2.5,97.5])] if ratios else None


def compare(records, rounds, tolerance):
    output = {}
    for path in ("vector_lookup", "complete_retrieval"):
        b = [r for r in records if r["backend"]=="qdrant" and r["path"]==path]
        c = [r for r in records if r["backend"]=="falkor" and r["path"]==path]
        b.sort(key=lambda r:(r["question_id"],r["round"]))
        c.sort(key=lambda r:(r["question_id"],r["round"]))
        assert [(r["question_id"],r["round"]) for r in b] == [(r["question_id"],r["round"]) for r in c]
        quality_b, quality_c = [r for r in b if r["round"]==0], [r for r in c if r["round"]==0]
        checks = {}
        for metric,kind in (("p50_ms","p50"),("p95_ms","p95")):
            bv, cv = stats(b)[metric], stats(c)[metric]
            ba = np.array([r["ms"] for r in b]).reshape(-1,rounds)
            ca = np.array([r["ms"] for r in c]).reshape(-1,rounds)
            ci = bootstrap_ratio(ba, ca, kind)
            checks[metric] = dict(qdrant=bv, falkor=cv, ratio=cv/bv,
                                 paired_bootstrap_95pct_ratio_interval=ci,
                                 provisional_point_check="pass" if cv <= bv*(1+tolerance) else "fail",
                                 provisional_interval_check=("pass" if ci[1] <= 1+tolerance else "fail" if ci[0] > 1+tolerance else "inconclusive") if ci else "inconclusive")
        for metric in ("recall@10","precision@10","ndcg@10"):
            ab=[r for r in quality_b if r["gold"]]
            ac=[r for r in quality_c if r["gold"]]
            bv,cv=aggregate(quality_b)[metric],aggregate(quality_c)[metric]
            ci = bootstrap_ratio(np.array([r["metrics"][metric] for r in ab]),
                                 np.array([r["metrics"][metric] for r in ac]),"mean") if bv else None
            checks[metric] = dict(qdrant=bv, falkor=cv, ratio=cv/bv if bv else None,
                                 paired_bootstrap_95pct_ratio_interval=ci,
                                 provisional_point_check=("pass" if cv >= bv*(1-tolerance) else "fail") if bv else "uninformative",
                                 provisional_interval_check=("pass" if ci[0] >= 1-tolerance else "fail" if ci[1] < 1-tolerance else "inconclusive") if ci else "inconclusive")
        output[path] = dict(qdrant=dict(latency=stats(b),quality=aggregate(quality_b)),
                            falkor=dict(latency=stats(c),quality=aggregate(quality_c)),
                            checks=checks, same_ordered_results=sum(x["ids"]==y["ids"] for x,y in zip(quality_b,quality_c)),
                            unique_questions=len(quality_b))
    return output


def measure(engine, vector_store, embedder, example, path, backend, round_id):
    qt=example.query_time or 1791849600  # Fixed 2026-10-13 UTC for missing query times.
    row=dict(backend=backend,path=path,round=round_id,question_id=example.example_id,
             gold=list(example.ground_truth_ids),category=example.category)
    start=time.perf_counter()
    try:
        if path=="vector_lookup":
            hits=vector_store.search(embedder[example.query], k=100,
                    filter_condition=create_search_filter(qt,"auto",example.metadata.get("corpus_ids")))
            ids=[h["payload"]["memory_id"] for h in hits]
        else:
            hits=engine.search(example.query,k=10,query_time=qt,retrieval_mode="hybrid",
                               document_ids=example.metadata.get("corpus_ids"))
            ids=[h.memory_id for h in hits]
        row.update(ids=ids,ms=(time.perf_counter()-start)*1000,error=None)
    except Exception as error:
        row.update(ids=[],ms=(time.perf_counter()-start)*1000,error=repr(error))
    row["metrics"]=compute_retrieval_metrics(row["ids"],row["gold"],[5,10])
    if backend=="falkor":
        row["native_candidates_requested"]=vector_store.last_overfetch
    return row


def concurrent_workload(engine, backend, examples, workers, mixed):
    barrier=Barrier(workers+1 if mixed else workers)
    def read(worker):
        barrier.wait(); rows=[]
        for i in range(12):
            e=examples[(worker*12+i)%len(examples)]; start=time.perf_counter()
            try:
                hits=engine.search(e.query,k=10,query_time=e.query_time or 1791849600,
                                  document_ids=e.metadata.get("corpus_ids"))
                rows.append(dict(ms=(time.perf_counter()-start)*1000, ids=[h.memory_id for h in hits],error=None))
            except Exception as error:
                rows.append(dict(ms=(time.perf_counter()-start)*1000,ids=[],error=repr(error)))
        return rows
    def write():
        barrier.wait(); rows=[]
        for i in range(4):
            mid="vector_workload_"+str(i)
            start=time.perf_counter()
            try:
                engine.add(f"Experiment update {i}: the travel budget is {600+i} units.", memory_id=mid,
                           timestamp=1791849600+i,metadata={"source":"vector_placement_control"})
                ready=time.perf_counter()
                hits=engine.search(f"Experiment update {i}: the travel budget is {600+i} units.",
                                   k=1,retrieval_mode="vector",document_ids=[mid])
                rows.append(dict(ms=(ready-start)*1000, first_visible_check_ms=(time.perf_counter()-ready)*1000,
                                 visible=bool(hits and hits[0].memory_id==mid),error=None))
            except Exception as error:
                rows.append(dict(ms=(time.perf_counter()-start)*1000,visible=False,error=repr(error)))
        return rows
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers+int(mixed)) as pool:
        readers=[pool.submit(read,i) for i in range(workers)]
        writer=pool.submit(write) if mixed else None
        rows=[r for f in readers for r in f.result()]
        writes=writer.result() if writer else []
    elapsed=time.perf_counter()-started
    return dict(backend=backend,workers=workers,mixed=mixed,reads=stats(rows),write_samples=writes,
                wall_seconds=elapsed,reads_per_second=len(rows)/elapsed,raw_reads=rows,
                receipt_ack_separate=False, readiness="synchronous engine.add commit; no async ingestion claim")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",required=True)
    parser.add_argument("--datasets",nargs="+",default=["dmr","locomo","longmemeval"])
    parser.add_argument("--rounds",type=int,default=5)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--order",choices=["grouped","paired"],default="paired")
    parser.add_argument("--provisional-tolerance",type=float,default=.05)
    args=parser.parse_args()
    if args.rounds < 2 or args.workers < 1 or not 0<=args.provisional_tolerance<1:
        parser.error("Use at least two rounds, positive workers and a valid tolerance.")
    out=Path(args.report).resolve()
    if out.exists():
        parser.error("Choose a fresh report directory; existing experiments are never overwritten.")
    if not out.is_relative_to(ROOT):
        parser.error("The report must be inside the workspace.")
    out.mkdir(parents=True); work=out/"work"; work.mkdir()
    source=ROOT/"data/reevaluation/reevaluation_20261013"
    token=uuid.uuid4().hex[:12]
    packages={name:importlib.metadata.version(name) for name in ["falkordb","redis","qdrant-client","fastembed","numpy","kuzu"]}
    manifest=dict(created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),packages=packages,
                  platform=platform.platform(),python=sys.version,rounds=args.rounds,workers=args.workers,
                  execution_order=args.order,
                  dataset_slice="retained p5; full histories; previously evaluated, not held out",
                  tolerance_provisional=args.provisional_tolerance,threshold_confirmed=False,
                  index_options=dict(dimension=384,similarityFunction="cosine",M=16,efConstruction=200,efRuntime=100),
                  native_distance_to_similarity="1.0 - cosine_distance, verified with identical/orthogonal/opposite vectors",
                  generation_tested=False,production_backend_modified=False,cache_research=False,
                  source_revision=subprocess.check_output(["git","-c","safe.directory="+ROOT.as_posix(),"rev-parse","HEAD"],text=True).strip(),
                  source_hashes={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/"memory/engine.py", ROOT/"memory/retrieval/hybrid.py",ROOT/"memory/vector_store/qdrant_store.py",ROOT/"memory/graph/falkordb_store.py", ROOT/"config.yaml",Path(__file__),ROOT/"scripts/vector_placement/falkor_vector.py"]})
    save(out/"manifest.json",manifest)
    for relative in manifest["source_hashes"]:
        snapshot=out/"source_snapshot"/relative
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,snapshot)
    real=Embedder(use_gpu=False,cache_dir="C:/Users/User/AppData/Local/Temp/fastembed_cache")
    manifest["embedding_model"]=real.model_name
    manifest["providers"]=real._providers
    summaries, all_rows, workloads = {}, [], {}
    for dataset in args.datasets:
        emit(stage="prepare",dataset=dataset)
        adapter=load_slice(source/"inputs/p5"/dataset,dataset)
        examples=adapter.load_examples(); docs=adapter.load_documents()
        save(out/(dataset+"_questions.json"),[asdict(e) if is_dataclass(e) else vars(e) for e in examples])
        vectors={q:v for q,v in zip([e.query for e in examples],real.embed([e.query for e in examples]))}
        source_store=source/"stores/p5"/dataset
        before=tree_digest(source_store)
        save(out/(dataset+"_input_hashes.json"),before)
        target=work/dataset/"qdrant"
        shutil.copytree(source_store/"vectors",target)
        baseline=FalkorDBGraphStore("vector_bench_"+token+"_"+dataset+"_q")
        candidate=FalkorDBGraphStore("vector_bench_"+token+"_"+dataset+"_f")
        qdrant=QdrantVectorStore(str(target),collection_name="semantic_memory",embedder=real)
        engines=[]
        try:
            imported_q=import_graph(source_store/"graph.db",baseline)
            imported_f=import_graph(source_store/"graph.db",candidate)
            assert snapshot_hash(falkor_snapshot(baseline))==snapshot_hash(falkor_snapshot(candidate))
            native=FalkorVectorExperiment(candidate,embedder=real)
            points=[]; offset=None
            while True:
                batch,offset=qdrant.scroll(limit=100,offset=offset,with_vectors=True)
                points.extend(batch)
                if offset is None: break
            start=time.perf_counter(); native.load_points(points); build_seconds=time.perf_counter()-start
            assert qdrant.count()==native.count()
            mismatches=[]
            for point in points:
                stored=native.get_memory(point.payload["memory_id"])
                if point.payload != stored["payload"] or not np.array_equal(np.asarray(point.vector,dtype=np.float32),np.asarray(stored["vector"],dtype=np.float32)):
                    mismatches.append(point.payload["memory_id"])
            assert not mismatches,mismatches
            save(out/(dataset+"_index.json"),dict(indexes=candidate.graph.query("CALL db.indexes()").result_set,
                query="CALL db.idx.vector.queryNodes('MemoryVector','embedding',100,vecf32($vector)) YIELD node,score RETURN node.id,score",
                explain=str(candidate.graph.explain("CALL db.idx.vector.queryNodes('MemoryVector','embedding',100,vecf32("+json.dumps(next(iter(vectors.values())).tolist())+")) YIELD node,score RETURN node.id,score"))))
            for store,graph in [(qdrant,baseline),(native,candidate)]:
                engines.append(MemoryEngine(config={"extraction_policy":"none","retrieval":{"reranker_enabled":False}},
                                            vector_store=store,graph_store=graph,embedder=real,use_gpu=False))
            pair={"qdrant":(engines[0],qdrant),"falkor":(engines[1],native)}
            records=[]
            for round_id in range(-1,args.rounds):
                names=["qdrant","falkor"] if round_id%2 else ["falkor","qdrant"]
                if args.order=="paired":
                    selected=examples[:3] if round_id==-1 else examples
                    for path in ("vector_lookup","complete_retrieval"):
                        runs={name:[] for name in names}
                        for index,example in enumerate(selected):
                            for name in (names if index%2==0 else list(reversed(names))):
                                engine,store=pair[name]
                                row=measure(engine,store,vectors,example,path,name,round_id)
                                runs[name].append(row)
                                if round_id>=0: records.append(row)
                        for name,run in runs.items():
                            emit(dataset=dataset,round=round_id,backend=name,path=path,order="paired",**stats(run))
                    continue
                for name in names:
                    engine,store=pair[name]
                    for path in ("vector_lookup","complete_retrieval"):
                        selected=examples[:3] if round_id==-1 else examples
                        run=[measure(engine,store,vectors,e,path,name,round_id) for e in selected]
                        if round_id>=0: records.extend(run)
                        emit(dataset=dataset,round=round_id,backend=name,path=path,**stats(run))
            all_rows.extend(dict(dataset=dataset,**r) for r in records)
            summaries[dataset]=dict(documents=len(docs),stored_vectors=len(points),questions=len(examples),
                graph_imports=dict(qdrant=imported_q,falkor=imported_f),vector_payload_bitwise_parity=True,
                native_vector_build_seconds=build_seconds,
                graph_nodes=baseline.get_node_counts(),comparison=compare(records,args.rounds,args.provisional_tolerance))
            save(out/(dataset+"_raw.json"),records)
            workloads[dataset]=[]
            for mixed in (False,True):
                for name in (["qdrant","falkor"] if not mixed else ["falkor","qdrant"]):
                    workloads[dataset].append(concurrent_workload(pair[name][0],name,examples,args.workers,mixed))
                    emit(stage="concurrency",dataset=dataset,backend=name,mixed=mixed,
                         reads=workloads[dataset][-1]["reads"])
            assert before==tree_digest(source_store),"Original evaluation store changed during this run."
            summaries[dataset]["original_store_hashes_unchanged"]=True
        finally:
            for engine in engines: engine.close()
            qdrant.close()
            for graph in (baseline,candidate):
                name=graph.graph_name
                assert name.startswith("vector_bench_"+token)
                try:
                    if graph.db.connection.exists(name): graph.graph.delete()
                    graph.db.connection.delete("{"+name+"}:revision", "{"+name+"}:lock", "{"+name+"}:publication")
                finally: graph.close()
        save(out/"comparison.json",summaries); save(out/"workloads.json",workloads)
    manifest["source_unchanged_at_finish"]={path:digest(ROOT/path)==sha for path,sha in manifest["source_hashes"].items()}
    save(out/"manifest.json",manifest)
    save(out/"raw.json",all_rows)
    emit(stage="complete",report=str(out),questions=sum(v["questions"] for v in summaries.values()))


if __name__=="__main__":
    main()
