"""Separate, explicitly synthetic status/history probes; no QA-accuracy claim."""
import os
os.environ['HF_HUB_OFFLINE']='1'
import sys,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(OUT.parents[2]))
from memory.engine import MemoryEngine
from memory.embeddings.embedder import Embedder
from memory.maintenance.maintenance import MemoryDecay
from retriever import read
import kuzu

latest=json.loads((OUT/'latest.json').read_text());path=Path(latest['results']);report=json.loads(path.read_text(encoding='utf-8'))
m=json.loads((OUT.parent/'graph.json').read_text(encoding='utf-8'));now=1791849600
engine=MemoryEngine(config={'extraction_policy':'none'},embedder=Embedder(use_gpu=False,cache_dir='C:/Users/User/AppData/Local/Temp/fastembed_cache'),
    qdrant_path=str(Path(report['run'])/'change_probes/qdrant'),kuzu_path=str(Path(report['run'])/'change_probes/graph.db'))
ex={'entities':[{'id':'north','name':'North','type':'Person'}],'relations':[],'importance':1.,'extractor_name':'manual_synthetic_control'}
db=kuzu.Database(str(OUT.parent/'counterfactuals.db'),read_only=True);c=kuzu.Connection(db)
cases=[]
for fixture in m['counterfactuals']['fixtures']:
    a,b=fixture['old'],fixture['new'];case=fixture['case']
    for claim,timestamp in [(a,now-53*86400),(b,now)]:
        text='Synthetic control about North. '+claim['slot'].replace('.',' ')+': '+str(claim['value'])+'.'
        engine.add(text,memory_id=claim['id'],timestamp=timestamp,extraction=ex,metadata={'source':'separate_synthetic_case','protected_in_proposed_model':True if claim is a else fixture['accepted']})
    if 'CONTRADICTS' in fixture['relation']:engine.graph_store.add_contradiction(a['id'],b['id'],detected_at=now)
    if fixture['accepted']:engine.graph_store.add_supersession(a['id'],b['id'],confidence=1.,superseded_at=now,reason='Explicit accepted synthetic control')
    query='What name should North be addressed by?' if a['slot']=='response.preferred_address' else 'Which study year was reported for North?'
    scope=[a['id'],b['id']]
    current=[x.model_dump() for x in engine.search(query,k=10,retrieval_mode='hybrid',temporal_mode='now',query_time=now,document_ids=scope)]
    historical=[x.model_dump() for x in engine.search(query,k=10,retrieval_mode='hybrid',temporal_mode='historical',query_time=now,document_ids=scope)]
    stored=read(c,'MATCH (n:TestClaim) WHERE n.case_id=$case_key RETURN n.id AS id,n.value AS value,n.status AS status,n.score AS score,n.protected AS protected,n.prior_acceptance AS prior_acceptance',{'case_key':case})
    out={'case':case,'synthetic':True,'query':query,'current_link_only_results':current,'current_link_only_historical':historical,
        'proposed_current_eligible':[x for x in stored if x['status'] in ['active','disputed']],
        'proposed_retained_audit':stored,'proposed_needs_resolution':any(x['status']=='disputed' for x in stored)}
    if fixture['accepted']:
        assert len(current)==2 and any(h['is_superseded'] for h in current)
        assert len(out['proposed_current_eligible'])==1
        engine.update(a['id'],valid_until=now-1)
        out['current_after_explicit_expiry']=[x.model_dump() for x in engine.search(query,k=10,retrieval_mode='hybrid',temporal_mode='now',query_time=now,document_ids=scope)]
        out['current_history_after_explicit_expiry']=[x.model_dump() for x in engine.search(query,k=10,retrieval_mode='hybrid',temporal_mode='historical',query_time=now,document_ids=scope)]
        assert [h['memory_id'] for h in out['current_after_explicit_expiry']]==[b['id']]
        assert [h['memory_id'] for h in out['current_history_after_explicit_expiry']]==[a['id']]
    cases.append(out)
decay=MemoryDecay(engine.vector_store,engine.graph_store)
report['change_probes']={'cases':cases,'current_importance_one_after_53_days':decay.compute_decayed_importance(1.,now-53*86400,now),
    'proposed_protected_acceptance':1.,'note':'Importance/recency and acceptance are different signals; this is a feature comparison, not a truth-probability comparison.'}
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
c.close();db.close();engine.close()
print(json.dumps({'synthetic_cases_verified':len(cases),'explicit_expiry_works_in_current':True,'link_alone_excludes_old_in_current':False,'protected_score_in_current':False},indent=2))
