"""A small KG-only improvement: field labels and bounded role/entity context.

Reads no questions or gold answers. No synonym rules tailored to question IDs.
"""
import json
from collections import Counter
from retriever import GraphReader,read,tokens

class ImprovedGraphReader(GraphReader):
    def __init__(self,path):
        super().__init__(path)
        for rid in self.index:
            fields=[f for f in self.facets if f['rid']==rid]
            self.index[rid]+=tokens(' '.join(f['slot'].replace('.',' ').replace('_',' ')+' '+f['scope'] for f in fields))
        self.counts={rid:Counter(ts) for rid,ts in self.index.items()};self.df=Counter(t for ts in self.index.values() for t in set(ts))
        self.avg=sum(len(x) for x in self.index.values())/len(self.index)

    def search(self,query,k=5):
        p=super().search(query,k)
        selected=[e['id'] for e in p['evidence']];seeds=p['top5']
        if not seeds:return p
        # Specific project, organization or episode entities connect related facts.
        # Exclude broad person/persona/technology hubs to avoid retrieving everything.
        ids=[r['id'] for r in read(self.c,"MATCH (r:Record)-[:SUBJECT|REFERENCES]->(e:Entity) WHERE r.id IN $ids AND e.kind IN ['Project','Organization','OrganizationMention','Episode'] RETURN DISTINCT e.id AS id",{'ids':seeds})]
        aliases=read(self.c,'MATCH (a:Entity)-[:SAME_AS]->(b:Entity) WHERE a.id IN $ids OR b.id IN $ids RETURN a.id AS a,b.id AS b',{'ids':ids})
        ids=list(dict.fromkeys(ids+[e[x] for e in aliases for x in ['a','b']]))
        neighbors=read(self.c,'MATCH (r:Record)-[:SUBJECT|REFERENCES]->(e:Entity) WHERE e.id IN $ids RETURN DISTINCT r.id AS id',{'ids':ids}) if ids else []
        q=set(tokens(query));neighbors.sort(key=lambda r:(-len(q&set(self.index[r['id']])),r['id']))
        for item in neighbors:
            rid=item['id']
            # Reserve an evidence item for an alias clarification if needed.
            reserve=1 if aliases else 0
            if rid not in selected and len(selected)<2*k-reserve:
                r=self.records[rid]
                p['evidence'].append({'id':rid,'key':r['key'],'title':r['title'],'payload':r['payload'],'kind':r['kind'],
                    'framework':r['framework'],'modality':r['modality'],'fields':[f for f in self.facets if f['rid']==rid],
                    'sources':read(self.c,'MATCH (r:Record {id:$id})-[:SUPPORTED_BY]->(s:Source) RETURN s.id AS id,s.text AS text',{'id':rid}),
                    'expanded':True,'expansion_reason':'specific project, episode or accepted organization identity path'})
                selected.append(rid)
        p['method']='KG-only: lexical field/record lookup plus bounded project, episode, policy and identity evidence paths'
        p['improvement']='Adds field labels and related role records; still lacks general paraphrase understanding or an answerability gate.'
        return p
