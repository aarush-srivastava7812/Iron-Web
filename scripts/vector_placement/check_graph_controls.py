"""Graph-rich, hand-authored control checks for both vector placements.

These checks are not a held-out benchmark or automatic extraction. They verify
that current graph joins, explicit change edges, scopes and historical filtering
still work while the vector store changes. Missing data is reported as missing,
not inferred from an empty reference list in a public benchmark.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ["HF_HUB_OFFLINE"]="1"
os.environ["TOKENIZERS_PARALLELISM"]="false"

from memory.embeddings.embedder import Embedder
from memory.engine import MemoryEngine
from memory.graph import FalkorDBGraphStore
from memory.vector_store.qdrant_store import QdrantVectorStore
from scripts.vector_placement.falkor_vector import FalkorVectorExperiment


FACTS=[
    ("preferred_name","North prefers to be addressed as North.",0,2**63-1),
    ("response_style","North prefers concise and direct explanations without filler.",0,2**63-1),
    ("organization","Inditech Systems and Inditech Electrosystems are the same organization; user-confirmed alias.",0,2**63-1),
    ("employment","North works at Inditech Electrosystems.",0,2**63-1),
    ("budget_old","North's approved travel budget was 1000 units before the accepted correction.",0,199),
    ("budget_new","North's approved travel budget is now 600 units after the accepted correction.",200,2**63-1),
    ("hotel_quiet","An agent says North wants a quiet hotel. This claim is disputed.",0,2**63-1),
    ("hotel_lively","Another agent says North wants a lively hotel. This claim is disputed.",0,2**63-1),
    ("procedure","For international travel, check passport validity before selecting flights.",0,2**63-1),
]
QUESTIONS=[
    dict(id="name",query="What should North be called?",gold=["preferred_name"],mode="now",at=250),
    dict(id="style",query="How should North receive explanations?",gold=["response_style"],mode="now",at=250),
    dict(id="alias",query="Is Inditech Systems the same organization as Inditech Electrosystems?",gold=["organization"],mode="now",at=250),
    dict(id="work",query="Which organization does North work at?",gold=["employment"],mode="now",at=250),
    dict(id="current_budget",query="What is North's current approved travel budget?",gold=["budget_new"],mode="now",at=250,forbidden=["budget_old"]),
    dict(id="past_budget",query="What was North's earlier approved travel budget?",gold=["budget_old"],mode="historical",at=250,forbidden=["budget_new"]),
    dict(id="before_change",query="What was North's approved travel budget at time 150?",gold=["budget_old"],mode="now",at=150,forbidden=["budget_new"]),
    dict(id="dispute",query="Does North want a quiet hotel or a lively hotel?",gold=["hotel_quiet","hotel_lively"],mode="now",at=250),
    dict(id="procedure",query="What must be checked before choosing international flights?",gold=["procedure"],mode="now",at=250),
    dict(id="missing_phone",query="What is North's phone number?",gold=[],mode="now",at=250,answer_exists=False),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",required=True,type=Path)
    args=parser.parse_args(); out=args.report.resolve()
    if out.exists() or not out.is_relative_to(ROOT):
        parser.error("Choose a fresh report directory inside the workspace.")
    out.mkdir(parents=True)
    (out/"frozen_controls.json").write_text(json.dumps(dict(facts=FACTS,questions=QUESTIONS),indent=2),encoding="utf-8")
    real=Embedder(use_gpu=False,cache_dir="C:/Users/User/AppData/Local/Temp/fastembed_cache")
    token=uuid.uuid4().hex[:12]
    output={"manual_graph_fixture":True,"automatic_extraction_tested":False,"fuzzy_scoring_tested":False,"backends":{}}
    for backend in ["qdrant","falkor"]:
        graph=FalkorDBGraphStore("vector_bench_"+token+"_controls_"+backend)
        store=(QdrantVectorStore(str(out/"vectors"),embedder=real) if backend=="qdrant"
               else FalkorVectorExperiment(graph,embedder=real))
        engine=MemoryEngine(config={"extraction_policy":"none","retrieval":{"reranker_enabled":False}},
                            vector_store=store,graph_store=graph,embedder=real,use_gpu=False)
        try:
            for mid,text,start,end in FACTS:
                engine.add(text,memory_id=mid,entity_ids=["north"],timestamp=100 if mid!="budget_new" else 200,
                           valid_from=start,valid_until=end,metadata={"source":"hand_authored_vector_control"})
            def obs(mid):return graph.get_memory_observations(mid)[0]["id"]
            graph.add_supersession(obs("budget_old"),obs("budget_new"),1.0,"Explicit fixture correction",superseded_at=200)
            graph.add_contradiction(obs("hotel_quiet"),obs("hotel_lively"),.8,detected_at=100)
            checks=[]
            for q in QUESTIONS:
                hits=engine.search(q["query"],k=10,temporal_mode=q["mode"],query_time=q["at"])
                ids=[h.memory_id for h in hits]
                checks.append(dict(question=q,ids=ids,
                    coverage=all(mid in ids for mid in q["gold"]),
                    forbidden_absent=not(set(q.get("forbidden",[]))&set(ids)),
                    missing_answer_is_present=False if q.get("answer_exists") is False else None,
                    related_evidence_returned_for_missing_answer=bool(ids) if q.get("answer_exists") is False else None,
                    hits=[h.model_dump() for h in hits]))
            scoped=engine.search("North approved travel budget",k=10,document_ids=["budget_new"],query_time=250)
            assert [h.memory_id for h in scoped]==["budget_new"]
            assert engine.get("budget_old") is not None and engine.get("budget_new") is not None
            assert all(c["coverage"] and c["forbidden_absent"] for c in checks if c["question"].get("answer_exists") is not False)
            output["backends"][backend]=dict(nodes=graph.get_node_counts(),edges=graph.get_edge_counts(),
                scoped_ids=[h.memory_id for h in scoped],retained_both_budget_versions=True,checks=checks)
        finally:
            engine.close();store.close()
            name=graph.graph_name
            assert name.startswith("vector_bench_"+token)
            if graph.db.connection.exists(name):graph.graph.delete()
            graph.db.connection.delete("{"+name+"}:revision","{"+name+"}:lock","{"+name+"}:publication")
            graph.close()
    output["ordered_result_parity"]=all(q["ids"]==f["ids"] for q,f in zip(output["backends"]["qdrant"]["checks"],output["backends"]["falkor"]["checks"]))
    (out/"results.json").write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(dict(report=str(out),ordered_result_parity=output["ordered_result_parity"],history_and_scope_checks="passed")),flush=True)


if __name__=="__main__":main()
