"""Add explicit cross-record links and export them from the prototype database."""
import json
from pathlib import Path
import kuzu
OUT=Path(__file__).resolve().parent
data=json.loads((OUT/'graph.json').read_text(encoding='utf-8'))
by_key={r['key']:r for r in data['v2']['records']}
links=[
    ('tone_recalibration','tone','RECALIBRATES_TO','P04 refers to the response baseline described in P03.','normalized explicit reference'),
    ('roi_response','roi_interpretation','REFERENCES_INTERPRETATION','The policy refers to the attributed ROI explanation; this is not independent causal confirmation.','normalized explicit reference'),
    ('debug_map','debug_stall','RELATED_CONTEXT','Debugging fallback self-description is relevant context, not an additional behavior instruction.','hand-reviewed indexing inference'),
]
db=kuzu.Database(str(OUT/'v2_graph.db'));conn=kuzu.Connection(db)
conn.execute('CREATE REL TABLE IF NOT EXISTS RECORD_LINK(FROM Record TO Record, role STRING, rationale STRING, origin STRING)')
for source,target,role,rationale,origin in links:
    conn.execute('MATCH (a:Record {id:$a}),(b:Record {id:$b}) MERGE (a)-[:RECORD_LINK {role:$role,rationale:$rationale,origin:$origin}]->(b)',
                 dict(a=by_key[source]['id'],b=by_key[target]['id'],role=role,rationale=rationale,origin=origin))
result=conn.execute('MATCH (a:Record)-[r:RECORD_LINK]->(b:Record) RETURN a.id,b.id,r.role,r.rationale,r.origin')
stored=[]
while result.has_next():
    a,b,role,rationale,origin=result.get_next()
    stored.append(dict(source=a,target=b,role=role,rationale=rationale,origin=origin))
assert len(stored)==3
conn.close();db.close()
data['v2']['record_links']=stored
for r in data['v2']['records']:r['record_links']=[x for x in stored if x['source']==r['id']]
data['v2']['meta']['edge_counts']['RECORD_LINK']=3
data['v2']['meta']['edges']=sum(data['v2']['meta']['edge_counts'].values())
(OUT/'graph.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Three stored links added; derived relevance is distinguished from explicit references.')
