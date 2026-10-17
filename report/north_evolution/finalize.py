"""Update the prototype's formatting-policy DSL and rerun graph checks in place."""
import json
import kuzu
from model import OUT
from build import verify

m=json.loads((OUT/'graph.json').read_text(encoding='utf-8'))
r=next(r for r in m['new_records'] if r['key']=='compact_documents')
r['payload']['trigger']={'field':'task','eq':'document_generation'}
db=kuzu.Database(str(OUT/'evolution.db'));c=kuzu.Connection(db)
c.execute('MATCH (r:Record {id:$id}) SET r.payload=$payload',{'id':r['id'],'payload':json.dumps(r['payload'])})
c.close();db.close()
verify(m)
(OUT/'graph.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
print('Updated document-policy trigger; all 14 behavior checks passed.')
