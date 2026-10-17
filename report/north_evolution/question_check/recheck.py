"""Retest the changed KG and use ten held-out questions without further tuning."""
import os
os.environ['HF_HUB_OFFLINE']='1'
import sys,json,time,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT.parents[2]))
from retriever import GraphReader
from improve import ImprovedGraphReader
from memory.engine import MemoryEngine
from memory.embeddings.embedder import Embedder

latest=json.loads((OUT/'latest.json').read_text());path=Path(latest['results']);report=json.loads(path.read_text(encoding='utf-8'))
m=json.loads((OUT.parent/'graph.json').read_text(encoding='utf-8'));keyids={r['key']:r['id'] for r in m['old']['records']+m['new_records']};keyids['C_ORG']='C_ORG'
held=json.loads((OUT/'holdout.json').read_text());report['holdout_hash']=hashlib.sha256((OUT/'holdout.json').read_bytes()).hexdigest()
def evaluate(ids,q):
    groups=[{keyids[k] for k in group} for group in q['gold']]
    if not groups:return {'complete':not ids,'covered':None,'expected_groups':0,'missing':[],'abstention_check':True}
    got=[bool(g&set(ids)) for g in groups]
    return {'complete':all(got),'covered':sum(got)/len(groups),'expected_groups':len(groups),'missing':[q['gold'][i] for i,v in enumerate(got) if not v]}
def kg_result(reader,q):
    start=time.perf_counter();p=reader.search(q['question']);ids=[e['id'] for e in p['evidence']]+list(dict.fromkeys(a['source'] for a in p['aliases']))
    assert len(ids)<=10
    return {'top5':p['top5'],'evidence_ids':ids,'core':evaluate(p['top5'],q),'expanded':evaluate(ids,q),'ms':(time.perf_counter()-start)*1000,'packet':p}
initial=GraphReader(OUT.parent/'evolution.db');improved=ImprovedGraphReader(OUT.parent/'evolution.db')
for r in report['results']:r['runs']['improved_kg']=kg_result(improved,r['question'])
real=Embedder(use_gpu=False,cache_dir='C:/Users/User/AppData/Local/Temp/fastembed_cache')
config={'extraction_policy':'none','USE_GPU':False,'retrieval':{'reranker_enabled':False}}
engine=MemoryEngine(config=config,embedder=real,qdrant_path=str(Path(report['run'])/'current_default/qdrant'),kuzu_path=str(Path(report['run'])/'current_default/graph.db'))
report['holdout']=[]
for q in held:
    r={'question':q,'runs':{'prototype_kg':kg_result(initial,q),'improved_kg':kg_result(improved,q)}}
    start=time.perf_counter();hits=[x.model_dump() for x in engine.search(q['question'],k=10,retrieval_mode='hybrid',temporal_mode='now',query_time=1791849600)];ids=[h['memory_id'] for h in hits]
    r['runs']['default_hybrid']={'top5':ids[:5],'evidence_ids':ids,'core':evaluate(ids[:5],q),'expanded':evaluate(ids,q),'ms':(time.perf_counter()-start)*1000,'hits':hits}
    report['holdout'].append(r)
def summary(rs,name):
    supported=[r for r in rs if r['question']['gold']]
    return {'questions_with_reference_evidence':len(supported),'complete_top5':sum(r['runs'][name]['core']['complete'] for r in supported),'complete_evidence_budget10':sum(r['runs'][name]['expanded']['complete'] for r in supported),
        'unsupported_query_abstentions':sum(r['runs'][name]['expanded']['complete'] for r in rs if not r['question']['gold']), 'unsupported_queries':sum(not r['question']['gold'] for r in rs)}
report['summary']['improved_kg']=summary(report['results'],'improved_kg')
report['holdout_summary']={n:summary(report['holdout'],n) for n in ['prototype_kg','improved_kg','default_hybrid']}
report['improvements_tested']=['Field labels are searchable.','Bounded context expansion follows specific projects, episodes, and accepted organization identity.','Broad person/persona/technology hubs are excluded from that extra expansion.']
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
engine.close();initial.close();improved.close()
print(json.dumps({'improved_initial':report['summary']['improved_kg'],'holdout':report['holdout_summary']},indent=2))
