"""Read-only Cypher checks against the isolated blog fixture."""
import json
from pathlib import Path
from falkordb import FalkorDB

root = Path(__file__).resolve().parent
fixture = json.loads((root / 'lifecycle-20261018/results.json').read_text(encoding='utf-8'))
client = FalkorDB(host='127.0.0.1', port=6379)
graph = client.select_graph(fixture['graph_name'])
old_id = fixture['old_claim']['claim_id']
new_id = fixture['new_claim']['claim_id']
queries = [
    ('claim_state', 'MATCH(c:MemoryClaim {id:$id}) RETURN properties(c)', {'id': new_id}),
    ('direct_affected_work', 'MATCH(w:MemoryWork)-[:USES]->(c:MemoryClaim) WHERE c.id IN $ids RETURN DISTINCT w.id LIMIT $limit', {'ids': [old_id], 'limit': 101}),
    ('downstream_work', 'MATCH(w:MemoryWork)-[:DEPENDS_ON]->(p:MemoryWork) WHERE p.id IN $ids RETURN DISTINCT w.id LIMIT $limit', {'ids': ['trip_plan'], 'limit': 101}),
    ('source_evidence', 'MATCH(s:MemorySource) WHERE s.id IN $ids RETURN properties(s)', {'ids': [fixture['new_claim']['sources'][0]['id']]}),
    ('inspect_dependency_path', '''MATCH (w:MemoryWork)-[:USES]->(old:MemoryClaim),
      (current:MemoryClaim)-[:SUPERSEDES]->(old),
      (current)-[:SUPPORTED_BY]->(source:MemorySource)
      WHERE w.id = $work_id
      RETURN w.id, old.value_json, current.value_json,
             source.memory_id, w.validation_state''', {'work_id': 'trip_plan'}),
]
records = []
try:
    for name, query, parameters in queries:
        result = graph.ro_query(query, params=parameters)
        records.append(dict(name=name, query=query, parameters=parameters, rows=result.result_set))
finally:
    client.close()
(root / 'query-results.json').write_text(json.dumps({'graph': fixture['graph_name'], 'queries': records}, indent=2), encoding='utf-8')
for record in records:
    print(json.dumps({'name': record['name'], 'rows': record['rows']}))
