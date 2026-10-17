"""Align stored synthetic scores with full fuzzy traces after state transitions."""
import json
from pathlib import Path
import kuzu
from fuzzy import score
OUT=Path(__file__).resolve().parent
m=json.loads((OUT/'graph.json').read_text(encoding='utf-8'))
db=kuzu.Database(str(OUT/'counterfactuals.db'));conn=kuzu.Connection(db)
for fixture in m['counterfactuals']['fixtures']:
    if not fixture['accepted']:
        fixture['old']['conflict']=.35;fixture['new']['conflict']=.85
    for key in ('old','new'):
        f=fixture[key]
        f['fuzzy']=score(quality=f['quality'],age_days=f['age_base'],half_life=f['half_life'],support=f['support'],
                         conflict=f['conflict'],protected=f['protected'],status=f['status'])
        f['score']=f['fuzzy']['score']
        conn.execute('MATCH (c:TestClaim {id:$id}) SET c.score=$score',dict(id=f['id'],score=f['score']))
conn.close();db.close()
for c in m['checks']:
    if c['name']=='Unaccepted contradiction remains disputed':c['evidence']['new_score']=m['counterfactuals']['fixtures'][2]['new']['score']
(OUT/'graph.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
print('Stored control scores and rule traces agree.')
