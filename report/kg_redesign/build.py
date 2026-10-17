"""Isolated proposed claim/evidence/change graph; inputs are hand encoded."""
import json
from pathlib import Path
import kuzu

OUT = Path(__file__).resolve().parent
DB_PATH = OUT / "claims_v2.db"


def query(conn, cypher, params=None):
    result = conn.execute(cypher, params or {})
    cols = result.get_column_names()
    rows = []
    while result.has_next():
        rows.append(dict(zip(cols, result.get_next())))
    return rows


def build():
    if DB_PATH.exists():
        raise RuntimeError("Refusing to overwrite an existing demonstration database.")
    db = kuzu.Database(str(DB_PATH))
    conn = kuzu.Connection(db)
    schemas = [
        "CREATE NODE TABLE Entity(id STRING, name STRING, kind STRING, namespace STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE Source(id STRING, text STRING, sequence INT64, origin STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE Claim(id STRING, predicate STRING, polarity STRING, recorded_sequence INT64, context STRING, valid_from INT64, valid_until INT64, extraction_kind STRING, note STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE Change(id STRING, change_type STRING, summary STRING, recorded_sequence INT64, effective_at INT64, reason STRING, PRIMARY KEY(id))",
        "CREATE REL TABLE SUBJECT(FROM Claim TO Entity)",
        "CREATE REL TABLE OBJECT(FROM Claim TO Entity)",
        "CREATE REL TABLE SUPPORTED_BY(FROM Claim TO Source, quote STRING, span_start INT64, span_end INT64)",
        "CREATE REL TABLE SUPERSEDES(FROM Claim TO Claim, rule STRING, context STRING)",
        "CREATE REL TABLE ENDS_CURRENT_APPLICABILITY(FROM Claim TO Claim, rule STRING)",
        "CREATE REL TABLE CHANGE_SUBJECT(FROM Change TO Entity)",
        "CREATE REL TABLE PREVIOUS(FROM Change TO Claim)",
        "CREATE REL TABLE REPLACEMENT(FROM Change TO Claim)",
        "CREATE REL TABLE CESSATION(FROM Change TO Claim)",
        "CREATE REL TABLE EVIDENCED_BY(FROM Change TO Source, quote STRING)",
    ]
    for schema in schemas:
        conn.execute(schema)
    sources = [
        dict(id="S1", text="Maya maintains Project Atlas.", sequence=1),
        dict(id="S2", text="Project Atlas uses Python and PostgreSQL.", sequence=2),
        dict(id="S3", text="Project Atlas now uses SQLite instead of PostgreSQL.", sequence=3),
    ]
    entities = [dict(id="maya", name="Maya", kind="Person"), dict(id="atlas", name="Project Atlas", kind="Project"),
                dict(id="python", name="Python", kind="ProgrammingLanguage"),
                dict(id="postgres", name="PostgreSQL", kind="DatabaseTechnology"),
                dict(id="sqlite", name="SQLite", kind="DatabaseTechnology")]
    claims = [
        dict(id="C1", subject="maya", predicate="maintains", object="atlas", polarity="positive", source="S1",
             quote=sources[0]["text"], note="Maintenance is asserted. Ownership, employment, and skill are not asserted."),
        dict(id="C2", subject="atlas", predicate="uses", object="python", polarity="positive", source="S2",
             quote=sources[1]["text"], note="Python is last reported in S2. S3 supplies no withdrawal and does not freshly confirm Python."),
        dict(id="C3", subject="atlas", predicate="uses", object="postgres", polarity="positive", source="S2",
             quote=sources[1]["text"], note="Reported in S2; later replaced in the described use by the explicit change in S3. Historically retained."),
        dict(id="C4", subject="atlas", predicate="uses", object="sqlite", polarity="positive", source="S3",
             quote=sources[2]["text"], note="Latest reported database in the described use. No production/test environment is specified."),
        dict(id="C5", subject="atlas", predicate="uses", object="postgres", polarity="negative", source="S3",
             quote="instead of PostgreSQL", note="Explicit replacement implies cessation in the described use; not avoidance, dislike, or a universal ban."),
    ]
    conn.execute("BEGIN TRANSACTION")
    for e in entities:
        conn.execute("CREATE (:Entity {id:$id, name:$name, kind:$kind, namespace:'isolated-demo'})", e)
    for s in sources:
        conn.execute("CREATE (:Source {id:$id, text:$text, sequence:$sequence, origin:'fictional demonstration sentence'})", s)
    for c in claims:
        source = next(s for s in sources if s["id"] == c["source"])
        conn.execute("CREATE (:Claim {id:$id, predicate:$predicate, polarity:$polarity, recorded_sequence:$seq, context:'Atlas, described use; environment unspecified', valid_from:NULL, valid_until:NULL, extraction_kind:'explicit hand-encoded interpretation', note:$note})",
                     dict(id=c["id"], predicate=c["predicate"], polarity=c["polarity"], seq=source["sequence"], note=c["note"]))
        for relation, target in (("SUBJECT", c["subject"]), ("OBJECT", c["object"])):
            conn.execute(f"MATCH (c:Claim {{id:$cid}}), (e:Entity {{id:$eid}}) CREATE (c)-[:{relation}]->(e)", dict(cid=c["id"], eid=target))
        start = source["text"].index(c["quote"])
        conn.execute("MATCH (c:Claim {id:$cid}), (s:Source {id:$sid}) CREATE (c)-[:SUPPORTED_BY {quote:$quote, span_start:$span_start, span_end:$span_end}]->(s)",
                     dict(cid=c["id"], sid=source["id"], quote=c["quote"], span_start=start, span_end=start+len(c["quote"])))
    conn.execute("MATCH (new:Claim {id:'C4'}), (old:Claim {id:'C3'}) CREATE (new)-[:SUPERSEDES {rule:'Explicit instead-of replacement in S3, same project and described use', context:'Atlas, described use; environment unspecified'}]->(old)")
    conn.execute("MATCH (stop:Claim {id:'C5'}), (old:Claim {id:'C3'}) CREATE (stop)-[:ENDS_CURRENT_APPLICABILITY {rule:'Cessation at an undated change, not historical falsity'}]->(old)")
    conn.execute("CREATE (:Change {id:'X1', change_type:'TechnologyReplacement', summary:'Atlas changes from PostgreSQL to SQLite in the described use', recorded_sequence:3, effective_at:NULL, reason:NULL})")
    conn.execute("MATCH (x:Change {id:'X1'}), (e:Entity {id:'atlas'}) CREATE (x)-[:CHANGE_SUBJECT]->(e)")
    for relation, cid in (("PREVIOUS", "C3"), ("REPLACEMENT", "C4"), ("CESSATION", "C5")):
        conn.execute(f"MATCH (x:Change {{id:'X1'}}), (c:Claim {{id:$cid}}) CREATE (x)-[:{relation}]->(c)", {"cid":cid})
    conn.execute("MATCH (x:Change {id:'X1'}), (s:Source {id:'S3'}) CREATE (x)-[:EVIDENCED_BY {quote:'now uses SQLite instead of PostgreSQL'}]->(s)")
    conn.execute("COMMIT")
    conn.close()
    db.close()
    # All viewer data comes from reopening and querying the persisted prototype.
    db = kuzu.Database(str(DB_PATH))
    conn = kuzu.Connection(db)
    exported = dict(
        entities=query(conn,"MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.kind AS kind, e.namespace AS namespace ORDER BY e.id"),
        sources=query(conn,"MATCH (s:Source) RETURN s.id AS id, s.text AS text, s.sequence AS sequence, s.origin AS origin ORDER BY s.sequence"),
        claims=query(conn,"MATCH (a:Entity)<-[:SUBJECT]-(c:Claim)-[:OBJECT]->(b:Entity), (c)-[r:SUPPORTED_BY]->(s:Source) RETURN c.id AS id, a.id AS subject, a.name AS subject_name, c.predicate AS predicate, b.id AS object, b.name AS object_name, c.polarity AS polarity, c.recorded_sequence AS sequence, c.context AS context, c.valid_from AS valid_from, c.valid_until AS valid_until, c.extraction_kind AS extraction_kind, c.note AS note, s.id AS source, r.quote AS quote, r.span_start AS span_start, r.span_end AS span_end ORDER BY c.id"),
        changes=query(conn,"MATCH (x:Change)-[:CHANGE_SUBJECT]->(e:Entity), (x)-[:PREVIOUS]->(old:Claim), (x)-[:REPLACEMENT]->(new:Claim), (x)-[:CESSATION]->(stop:Claim), (x)-[r:EVIDENCED_BY]->(s:Source) RETURN x.id AS id, x.change_type AS type, x.summary AS summary, x.recorded_sequence AS sequence, x.effective_at AS effective_at, x.reason AS reason, e.id AS subject, old.id AS previous, new.id AS replacement, stop.id AS cessation, s.id AS source, r.quote AS quote"),
        claim_links=query(conn,"MATCH (a:Claim)-[r:SUPERSEDES]->(b:Claim) RETURN a.id AS source, b.id AS target, 'SUPERSEDES' AS type, r.rule AS rule, r.context AS context")
          + query(conn,"MATCH (a:Claim)-[r:ENDS_CURRENT_APPLICABILITY]->(b:Claim) RETURN a.id AS source, b.id AS target, 'ENDS_CURRENT_APPLICABILITY' AS type, r.rule AS rule"),
    )
    counts = {label:query(conn,f"MATCH (n:{label}) RETURN count(n) AS n")[0]["n"] for label in ("Entity","Source","Claim","Change")}
    edge_counts = {label:query(conn,f"MATCH ()-[r:{label}]->() RETURN count(r) AS n")[0]["n"] for label in ("SUBJECT","OBJECT","SUPPORTED_BY","SUPERSEDES","ENDS_CURRENT_APPLICABILITY","CHANGE_SUBJECT","PREVIOUS","REPLACEMENT","CESSATION","EVIDENCED_BY")}
    conn.close(); db.close()
    exported["meta"] = dict(proposal=True, production_schema_changed=False, extraction="hand-encoded sample interpretation; not model-generated",
                           persistence_verified=True, database=str(DB_PATH), counts=counts, edge_counts=edge_counts,
                           type_origin="Small explicitly supplied technology taxonomy; not asserted by the three sentences",
                           temporal_policy="relative statement order only; real effective dates unknown",
                           inference_policy="Explainable composition and explicit replacement; no skill, motivation or global single-database inference")
    validate(exported)
    (OUT/"graph.json").write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT/"queries.cypher").write_text("""// Inspect the persisted proposed model in claims_v2.db
MATCH (s:Source) RETURN s.*;
MATCH (a:Entity)<-[:SUBJECT]-(c:Claim)-[:OBJECT]->(b:Entity), (c)-[r:SUPPORTED_BY]->(s:Source)
RETURN c.id, a.name, c.predicate, c.polarity, b.name, s.id, r.quote;
MATCH (new:Claim)-[r:SUPERSEDES]->(old:Claim) RETURN new.id, old.id, r.rule;
MATCH (x:Change)-[:PREVIOUS]->(old:Claim), (x)-[:REPLACEMENT]->(new:Claim)
RETURN x.id, old.id, new.id, x.effective_at, x.reason;
""", encoding="utf-8")
    print(json.dumps(exported["meta"], indent=2))


def state(data, claim, step):
    if claim["sequence"] > step:
        return "not-yet-reported"
    for change in data["changes"]:
        if change["previous"] == claim["id"] and change["sequence"] <= step:
            return "historical"
    return "latest-reported" if claim["sequence"] == step else "last-known"


def answer(data, question, step=3):
    claims = {c["id"]:c for c in data["claims"] if c["sequence"] <= step}
    latest = [c for c in claims.values() if c["polarity"] == "positive" and state(data,c,step) != "historical"]
    if question == "maintainer":
        premises = [c for c in latest if c["predicate"] == "maintains" and c["object"] == "atlas"]
        return dict(answer="Maya is the last reported maintainer of Project Atlas." if premises else "No maintainer has been reported.", claims=[c["id"] for c in premises])
    if question == "database":
        db_ids = {e["id"] for e in data["entities"] if e["kind"] == "DatabaseTechnology"}
        premises = [c for c in latest if c["subject"]=="atlas" and c["predicate"]=="uses" and c["object"] in db_ids]
        return dict(answer=("Latest reported database in the described use: "+", ".join(c["object_name"] for c in premises)+". Environment and exact effective date are unspecified.") if premises else "No database has been reported.", claims=[c["id"] for c in premises], type_source="explicitly supplied technology taxonomy")
    if question == "change":
        events = [e for e in data["changes"] if e["sequence"] <= step]
        return dict(answer="PostgreSQL was replaced by SQLite in the described use; reason and exact date are unknown." if events else "No replacement has been reported yet.", claims=[cid for e in events for cid in (e["previous"],e["replacement"],e["cessation"])], changes=[e["id"] for e in events])
    if question == "context":
        maintenance = [c for c in latest if c["predicate"]=="maintains" and c["subject"]=="maya"]
        technology = [c for c in latest if c["predicate"]=="uses" and c["subject"] in {m["object"] for m in maintenance}]
        return dict(answer=("Maya maintains Atlas; that project's reported technologies are "+", ".join(c["object_name"] for c in technology)+". This is project context, not evidence of Maya's personal skills. Python is last known from S2, not freshly confirmed by S3.") if technology else "The maintained project's technologies have not been reported.", claims=[c["id"] for c in maintenance+technology], rule="maintains(person,project) AND uses(project,technology) => maintained-project technology context; no HAS_SKILL conclusion")
    if question == "skill":
        return dict(answer="Unknown. Maintaining a project does not establish expertise in its technologies.", claims=[], blocked_rule="No rule converts project maintenance into personal expertise.")
    if question == "why":
        return dict(answer="Unknown. No sentence supplies a motivation for the change.", claims=[], missing_field="Change.reason")
    if question == "when":
        return dict(answer="Exact date unknown. 'Now' establishes a reported change, not a calendar timestamp in these samples.", claims=[], missing_field="Change.effective_at")
    raise ValueError(question)


def validate(data):
    assert data["meta"]["counts"] == {"Entity":5,"Source":3,"Claim":5,"Change":1}
    assert sum(data["meta"]["edge_counts"].values()) == 22
    sources={s["id"]:s for s in data["sources"]}
    for c in data["claims"]:
        assert sources[c["source"]]["text"][c["span_start"]:c["span_end"]]==c["quote"]
    assert "PostgreSQL" in answer(data,"database",2)["answer"]
    assert "SQLite" in answer(data,"database",3)["answer"]
    assert answer(data,"context",3)["claims"] == ["C1","C2","C4"]
    assert state(data,next(c for c in data["claims"] if c["id"]=="C3"),3)=="historical"
    assert answer(data,"skill")["claims"] == []
    assert data["changes"][0]["effective_at"] is None and data["changes"][0]["reason"] is None
    checks={"persisted_counts_and_edges":True,"source_spans_exact":True,"replacement_scoped_to_database":True,
            "python_and_maintainer_preserved":True,"unsupported_skill_inference_blocked":True,"unknown_time_and_reason_preserved":True}
    data["verification"] = checks
    data["answers"] = {str(step):{q:answer(data,q,step) for q in ("maintainer","database","change","context","skill","why","when")} for step in (1,2,3)}


if __name__ == "__main__":
    build()
