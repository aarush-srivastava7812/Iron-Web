"""Frozen 30-question evidence retrieval comparison on isolated real databases.

Expected answers are authored evaluation references, never generated answers.
No production stores are read or written. All systems receive the same prepared
record text; baseline enriched entities are manually supplied, not auto-extracted.
"""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import sys,json,time,hashlib,statistics
from pathlib import Path
from datetime import datetime,timezone
import numpy as np

OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT))
from memory.engine import MemoryEngine
from memory.embeddings.embedder import Embedder
from retriever import GraphReader,read

QUESTIONS=json.loads((OUT/'questions.json').read_text())
m=json.loads((OUT.parent/'graph.json').read_text(encoding='utf-8'))
records=m['old']['records']+m['new_records']
keyids={r['key']:r['id'] for r in records};keyids['C_ORG']='C_ORG'
entities={e['id']:e for e in m['old']['entities']+m['new_entities']}
cards={r['id']:r['title']+'\n'+json.dumps(r['payload'],ensure_ascii=False) for r in records}
cards['C_ORG']='Inditech Systems and Inditech Electrosystems are the same organization. Explicit user confirmation: '+m['identity']['evidence']
now=int(datetime(2026,10,13,tzinfo=timezone.utc).timestamp());old=now-53*86400
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');RUN=OUT/('runs/'+stamp);RUN.mkdir(parents=True)
print('Frozen questions: '+hashlib.sha256((OUT/'questions.json').read_bytes()).hexdigest(),flush=True)

class CachedEmbedder:
    def __init__(self,real):self.real=real;self.dimension=real.dimension;self._providers=real._providers;self.cache={}
    def prepare(self,texts):
        missing=list(dict.fromkeys(t for t in texts if t not in self.cache))
        if missing:
            for t,v in zip(missing,self.real.embed(missing)):self.cache[t]=v
    def embed_single(self,text):
        if text not in self.cache:self.cache[text]=self.real.embed_single(text)
        return self.cache[text]

real=Embedder(use_gpu=False,cache_dir='C:/Users/User/AppData/Local/Temp/fastembed_cache')
embedder=CachedEmbedder(real);embedder.prepare(list(cards.values())+[q['question'] for q in QUESTIONS])
print('Real cached BGE model loaded; no synthetic embeddings.',flush=True)
systems={}
config={'extraction_policy':'none','USE_GPU':False,'retrieval':{'reranker_enabled':False}}
for name,enrich in [('current_default',False),('current_prepared',True)]:
    engine=MemoryEngine(config=config,embedder=embedder,qdrant_path=str(RUN/name/'qdrant'),kuzu_path=str(RUN/name/'graph.db'))
    for r in records:
        eidlist=list(dict.fromkeys([r['subject']]+list(r['refs'].values())))
        extraction=None
        if enrich:
            es=[dict(id=eid,name=entities[eid]['name'],type=entities[eid]['kind']) for eid in eidlist]
            extraction={'entities':es,'relations':[{'from':r['subject'],'to':eid,'type':role.upper(),'confidence':1.} for role,eid in r['refs'].items() if eid!=r['subject']], 'importance':1.,'extractor_name':'manual_prepared_fixture_not_automatic'}
        engine.add(cards[r['id']],memory_id=r['id'],timestamp=old if r['id'].startswith('R') else now,importance=1.,extraction=extraction,metadata={'source':'random_question_check','record_key':r['key']})
    extraction=None
    if enrich:
        extraction={'entities':[{'id':e,'name':entities[e]['name'],'type':entities[e]['kind']} for e in ['inditech_systems','inditech']],
            'relations':[{'from':'inditech_systems','to':'inditech','type':'SAME_AS','confidence':1.}], 'importance':1.,'extractor_name':'explicit_user_alias_fixture'}
    engine.add(cards['C_ORG'],memory_id='C_ORG',timestamp=now,extraction=extraction,metadata={'source':'user_confirmation'})
    systems[name]=engine
    print(name+' ingested 92 shared evidence cards.',flush=True)

graph=GraphReader(OUT.parent/'evolution.db')
results=[]
def evaluate(ids,q):
    groups=[{keyids[k] for k in group} for group in q['gold']]
    if not groups:return {'complete':len(ids)==0,'covered':None,'expected_groups':0,'missing':[],'abstention_check':True}
    got=[bool(g&set(ids)) for g in groups]
    return {'complete':all(got),'covered':sum(got)/len(groups),'expected_groups':len(groups),'missing':[q['gold'][i] for i,v in enumerate(got) if not v]}

for q in QUESTIONS:
    result={'question':q,'runs':{}}
    start=time.perf_counter();hits=graph.search(q['question']);ms=(time.perf_counter()-start)*1000
    expanded=[e['id'] for e in hits['evidence']]+list(dict.fromkeys(a['source'] for a in hits['aliases']))
    assert len(expanded)<=10
    result['runs']['prototype_kg']={'top5':hits['top5'],'evidence_ids':expanded,'core':evaluate(hits['top5'],q),'expanded':evaluate(expanded,q),'ms':ms,'packet':hits}
    for name,mode in [('default_graph','graph'),('default_hybrid','hybrid'),('prepared_graph','graph'),('prepared_hybrid','hybrid')]:
        engine=systems['current_default' if name.startswith('default') else 'current_prepared']
        start=time.perf_counter();retrieved=engine.search(q['question'],k=10,retrieval_mode=mode,temporal_mode='now',query_time=now);elapsed=(time.perf_counter()-start)*1000
        data=[h.model_dump() for h in retrieved];ids=[h['memory_id'] for h in data]
        result['runs'][name]={'top5':ids[:5],'evidence_ids':ids,'core':evaluate(ids[:5],q),'expanded':evaluate(ids,q),'ms':elapsed,'hits':data}
    results.append(result)
    print(q['id']+' | KG '+str(result['runs']['prototype_kg']['expanded']['complete'])+' | current hybrid '+str(result['runs']['default_hybrid']['expanded']['complete']),flush=True)

def summary(name):
    supported=[r for r in results if r['question']['gold']]
    return {'questions_with_reference_evidence':len(supported),'complete_top5':sum(r['runs'][name]['core']['complete'] for r in supported),
        'complete_evidence_budget10':sum(r['runs'][name]['expanded']['complete'] for r in supported),
        'unsupported_query_abstentions':sum(r['runs'][name]['expanded']['complete'] for r in results if not r['question']['gold']),
        'unsupported_queries':sum(not r['question']['gold'] for r in results),
        'median_single_pass_ms':statistics.median(r['runs'][name]['ms'] for r in results),
        'groups':{group:{'n':len(rs),'complete_top5':sum(r['runs'][name]['core']['complete'] for r in rs),'complete_budget10':sum(r['runs'][name]['expanded']['complete'] for r in rs)} for group in sorted({r['question']['group'] for r in supported}) if (rs:=[r for r in supported if r['question']['group']==group])}}

report={'run':str(RUN),'question_hash':hashlib.sha256((OUT/'questions.json').read_bytes()).hexdigest(),'questions_frozen_before_retriever':True,
        'model':real.model_name,'real_embeddings':True,'no_generated_answers':True,'corpus':'same 91 manually prepared record cards plus one user-confirmed alias card',
        'prototype':'graph-stored text lookup plus graph traversal; no embedding model or generative model',
        'limitations':['Small curated test, no statistical significance or scale claim.','Prepared normalized text is shared, not automatically extracted from raw paragraphs.','Gold answer references are authored; the metric measures retrieval evidence, not generated answer accuracy.','Median timings are one local pass, not controlled performance comparisons.','Expanded evidence budget is ten items for each system; prototype core starts with five.','Default config and prepared graph represent different ingestion settings, not different neural models.'],
        'summary':{name:summary(name) for name in results[0]['runs']},'results':results}
(RUN/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'latest.json').write_text(json.dumps({'run':str(RUN),'results':str(RUN/'results.json')},indent=2))
for engine in systems.values():engine.close()
graph.close()
print(json.dumps(report['summary'],indent=2),flush=True)
