// Run these against evolution.db with a Kuzu connection.
MATCH (r:Record)-[:HAS_FACET]->(f:Facet)-[:FACET_EVIDENCE]->(s:Source)
WHERE r.id = 'R014'
RETURN r.id, f.slot, f.value, f.score, f.fuzzy_trace, s.id, s.text;

MATCH (newer:Facet)-[change:CONFIRMS]->(earlier:Facet)
RETURN newer.id, newer.slot, earlier.id, change.reason, change.independence;

MATCH (mention:Entity)-[alias:SAME_AS]->(canonical:Entity)
RETURN mention.name, canonical.name, alias.status, alias.source_id;

MATCH (newer:Record)-[candidate:POSSIBLE_RELATION]->(earlier:Record)
RETURN newer.title, earlier.title, candidate.reason, candidate.status;

// Run these separately against counterfactuals.db.
MATCH (newer:TestClaim)-[change:CONTRADICTS]->(earlier:TestClaim)
RETURN newer.case_id, newer.value, earlier.value, change.resolved,
       earlier.score, earlier.status, newer.score, newer.status;

MATCH (newer:TestClaim)-[change:SUPERSEDES]->(earlier:TestClaim)
RETURN newer.case_id, change.accepted, earlier.score, earlier.prior_acceptance,
       newer.score, newer.protected;
