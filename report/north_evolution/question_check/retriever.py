"""Prototype KG-only retrieval: text anchors, then actual graph evidence paths.

No embeddings, generative model, question-ID lookup or gold-answer routing.
This is small-corpus lexical lookup plus graph traversal, not general language understanding.
"""
import json,math,re,unicodedata
from collections import Counter
import kuzu
from pathlib import Path

STOP=set('a an the of for to in on at as is are was were be been being it its this that those these do does did has have had how what which who when why should can could would will if and or with by from than only all every my i me you your his him he north aarush srivastava reported report statement new earlier old mean means'.split())
def tokens(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(text).lower()) if not unicodedata.combining(c))
    return [w for w in re.findall(r'[a-z0-9]+',text) if w not in STOP and len(w)>1]
def read(c,q,args=None):
    r=c.execute(q,args or {});out=[];cols=r.get_column_names()
    while r.has_next():out.append(dict(zip(cols,r.get_next())))
    return out

class GraphReader:
    def __init__(self,path):
        self.db=kuzu.Database(str(path),read_only=True);self.c=kuzu.Connection(self.db)
        rows=read(self.c,'MATCH (r:Record) RETURN r.id AS id,r.record_key AS key,r.title AS title,r.payload AS payload,r.kind AS kind,r.modality AS modality,r.framework AS framework')
        self.records={r['id']:{**r,'payload':json.loads(r['payload'])} for r in rows}
        self.facets=read(self.c,'MATCH (r:Record)-[:HAS_FACET]->(f:Facet) RETURN r.id AS rid,f.id AS id,f.slot AS slot,f.value AS value,f.scope AS scope,f.status AS status,f.score AS score')
        self.index={rid:tokens(r['title']+' '+json.dumps(r['payload'],ensure_ascii=False)+' '+r['kind']) for rid,r in self.records.items()}
        self.counts={rid:Counter(ts) for rid,ts in self.index.items()};self.df=Counter(t for ts in self.index.values() for t in set(ts))
        self.avg=sum(len(x) for x in self.index.values())/len(self.index)
        self.entities=read(self.c,'MATCH (e:Entity) RETURN e.id AS id,e.name AS name')
    def search(self,query,k=5):
        q=tokens(query);N=len(self.index);scores=[]
        for rid,terms in self.counts.items():
            s=0
            for t in set(q):
                tf=terms[t]
                if tf:
                    idf=math.log(1+(N-self.df[t]+.5)/(self.df[t]+.5))
                    s+=idf*tf*2.2/(tf+1.2*(.25+.75*len(self.index[rid])/self.avg))
            if s>0:scores.append((s,rid))
        # Acceptance must not dominate relevance; average only breaks exact lexical ties.
        average={rid:sum(f['score'] for f in self.facets if f['rid']==rid)/max(1,sum(f['rid']==rid for f in self.facets)) for rid in self.records}
        ranked=sorted(scores,key=lambda z:(-z[0],-average[z[1]],z[1]))[:k]
        selected=[rid for _,rid in ranked];seed_ids=set(selected)
        # Follow explicit record references, once, under a fixed evidence budget of 10 records.
        links=read(self.c,'MATCH (a:Record)-[r:RECORD_LINK]->(b:Record) RETURN a.id AS a,b.id AS b,r.role AS reason')
        for e in links:
            if e['a'] in seed_ids and e['b'] not in selected and len(selected)<2*k:selected.append(e['b'])
        evidence=[]
        for rid in selected:
            r=self.records[rid]
            sources=read(self.c,'MATCH (r:Record {id:$id})-[:SUPPORTED_BY]->(s:Source) RETURN s.id AS id,s.text AS text',{'id':rid})
            fields=[f for f in self.facets if f['rid']==rid]
            evidence.append({'id':rid,'key':r['key'],'title':r['title'],'payload':r['payload'],'kind':r['kind'],'framework':r['framework'],'modality':r['modality'],'fields':fields,'sources':sources,'expanded':rid not in seed_ids})
        aliases=[];hypotheses=[];confirmations=[]
        if selected:
            entity_ids=read(self.c,'MATCH (r:Record)-[:SUBJECT|REFERENCES]->(e:Entity) WHERE r.id IN $ids RETURN DISTINCT e.id AS id',{'ids':selected})
            ids=[e['id'] for e in entity_ids]
            aliases=read(self.c,'MATCH (a:Entity)-[r:SAME_AS]->(b:Entity) WHERE a.id IN $ids OR b.id IN $ids RETURN a.name AS from_name,b.name AS to_name,r.source_id AS source,r.status AS status',{'ids':ids})
            hypotheses=read(self.c,'MATCH (a:Record)-[r:POSSIBLE_RELATION]->(b:Record) WHERE a.id IN $ids OR b.id IN $ids RETURN a.id AS source,b.id AS target,r.reason AS reason,r.status AS status',{'ids':selected})
            for h in hypotheses:
                # Don't automatically pull unrelated project records into the answer budget.
                h['both_endpoints_retrieved']=h['source'] in selected and h['target'] in selected
            confirmations=read(self.c,'MATCH (a:Facet)-[r:CONFIRMS]->(b:Facet) WHERE a.record_id IN $ids OR b.record_id IN $ids RETURN a.record_id AS source_record,b.record_id AS target_record,b.slot AS slot,r.independence AS independence',{'ids':selected})
        return {'top5':[rid for _,rid in ranked],'evidence':evidence,'aliases':aliases,'hypotheses':hypotheses,'confirmations':confirmations,'abstained':not ranked,'method':'lexical lookup over graph-stored records plus explicit graph links; no vectors or LLM','evidence_budget':2*k}
    def close(self):self.c.close();self.db.close()
