// Run against supplied/graph.db
MATCH (e:Entity) RETURN e.*;
MATCH (o:Observation) RETURN o.id, o.content, o.entity_id, o.source_memory_id;
MATCH (a:Entity)-[r:RELATES]->(b:Entity) RETURN a.name, r.relation_type, b.name, r.confidence;
MATCH (o:Observation)-[r:ABOUT]->(e:Entity) RETURN o.source_memory_id, o.id, e.name;
MATCH (a:Observation)-[r:CONTRADICTS]->(b:Observation) RETURN a.id, r.*, b.id;
MATCH (a:Observation)-[r:SUPERSEDES]->(b:Observation) RETURN a.id, r.*, b.id;
