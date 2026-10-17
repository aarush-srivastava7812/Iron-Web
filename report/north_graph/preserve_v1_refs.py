"""Retain role/entity links in the first projection, then recheck growth."""
import json
import shutil
from pathlib import Path
import kuzu
import build
from model import v1_claims
OUT=Path(__file__).resolve().parent
data=json.loads((OUT/'graph.json').read_text(encoding='utf-8'))
claims,values=v1_claims(data['v2'])
present={c['id'] for c in data['v1']['claims']}
entity_names={e['id']:e['name'] for e in data['v1']['entities']}
db=kuzu.Database(str(OUT/'v1_graph.db'));conn=kuzu.Connection(db)
conn.execute('BEGIN TRANSACTION')
for c in claims:
    if c['id'] in present:continue
    conn.execute("CREATE (:Claim {id:$id,predicate:$predicate,context:$context,owner:'north',valid_from:NULL,valid_until:NULL})",{k:c[k] for k in ('id','predicate','context')})
    for rel,eid in (('SUBJECT',c['subject']),('OBJECT',c['object'])):
        conn.execute(f'MATCH (c:Claim {{id:$cid}}),(e:Entity {{id:$eid}}) CREATE (c)-[:{rel}]->(e)',dict(cid=c['id'],eid=eid))
    conn.execute('MATCH (c:Claim {id:$cid}),(s:Source {id:$sid}) CREATE (c)-[:SUPPORTED_BY]->(s)',dict(cid=c['id'],sid=c['source']))
conn.execute('COMMIT')
data['v1']['claims']=build.rows(conn,'MATCH (a:Entity)<-[:SUBJECT]-(c:Claim)-[:OBJECT]->(b:Entity),(c)-[:SUPPORTED_BY]->(s:Source) RETURN c.id AS id,a.id AS subject,b.id AS object,b.name AS value,c.predicate AS predicate,c.context AS context,s.id AS source ORDER BY c.id')
assert len(data['v1']['claims'])==len(claims)
conn.close();db.close()
data['v1']['meta']['nodes']=len(data['v1']['entities'])+len(claims)+38
data['v1']['meta']['edges']=len(claims)*3
data['v1']['meta']['description']='Minimal v1: generic claims and literal value entities, with real entity-role and framework references and original evidence retained; no typed rule/value binding.'
db=kuzu.Database(str(OUT/'v1_graph.db'));conn=kuzu.Connection(db)
assert build.rows(conn,'MATCH (c:Claim) RETURN count(c) AS n')[0]['n']==len(claims)
conn.close();db.close()
data['checks']=build.probes(data['v1'],data['v2'])
bench=OUT/'benchmark_final';bench.mkdir()
for name in ('v1_graph.db','v2_graph.db'):shutil.copy2(OUT/name,bench/name)
build.OUT=bench
data['scale']=build.synthetic_scale(data['v1'],data['v2'])
(OUT/'graph.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
doc=(OUT/'DESIGN.md').read_text(encoding='utf-8').replace('| Minimal v1 projection | 479 | 672 | 224 generic claims, literal values represented as entities |',
    f"| Minimal v1 projection | {data['v1']['meta']['nodes']} | {data['v1']['meta']['edges']} | {len(claims)} generic claims, literal values represented as entities, role references retained |")
doc=doc.replace('`benchmark_routed/`','`benchmark_final/`')
(OUT/'DESIGN.md').write_text(doc,encoding='utf-8')
print(json.dumps(dict(v1_nodes=data['v1']['meta']['nodes'],v1_edges=data['v1']['meta']['edges'],v1_claims=len(claims),v2_nodes=data['v2']['meta']['nodes'],v2_edges=data['v2']['meta']['edges'],scale=data['scale']),indent=2))
