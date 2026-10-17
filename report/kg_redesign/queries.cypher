// Inspect the persisted proposed model in claims_v2.db
MATCH (s:Source) RETURN s.*;
MATCH (a:Entity)<-[:SUBJECT]-(c:Claim)-[:OBJECT]->(b:Entity), (c)-[r:SUPPORTED_BY]->(s:Source)
RETURN c.id, a.name, c.predicate, c.polarity, b.name, s.id, r.quote;
MATCH (new:Claim)-[r:SUPERSEDES]->(old:Claim) RETURN new.id, old.id, r.rule;
MATCH (x:Change)-[:PREVIOUS]->(old:Claim), (x)-[:REPLACEMENT]->(new:Claim)
RETURN x.id, old.id, new.id, x.effective_at, x.reason;
