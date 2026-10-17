"""Persist both graph designs and run bounded-neighborhood/semantic probes."""
import json
import statistics
import time
from pathlib import Path
import kuzu
from model import build_model,v1_claims,applicable_policies,OUT


def rows(conn,sql,args=None):
    result=conn.execute(sql,args or {});keys=result.get_column_names();out=[]
    while result.has_next():out.append(dict(zip(keys,result.get_next())))
    return out


def open_new(path,schemas):
    if path.exists():raise RuntimeError(f'Refusing to overwrite {path.name}')
    db=kuzu.Database(str(path));conn=kuzu.Connection(db)
    for sql in schemas:conn.execute(sql)
    return db,conn


def v1(model):
    claims,values=v1_claims(model)
    db,conn=open_new(OUT/'v1_graph.db',[
        'CREATE NODE TABLE Entity(id STRING, name STRING, kind STRING, PRIMARY KEY(id))',
        'CREATE NODE TABLE Source(id STRING, text STRING, section STRING, updated STRING, evidence_group STRING, PRIMARY KEY(id))',
        'CREATE NODE TABLE Claim(id STRING, predicate STRING, context STRING, owner STRING, valid_from INT64, valid_until INT64, PRIMARY KEY(id))',
        'CREATE REL TABLE SUBJECT(FROM Claim TO Entity)',
        'CREATE REL TABLE OBJECT(FROM Claim TO Entity)',
        'CREATE REL TABLE SUPPORTED_BY(FROM Claim TO Source)',
    ])
    conn.execute('BEGIN TRANSACTION')
    for e in model['entities']+values:conn.execute('CREATE (:Entity {id:$id,name:$name,kind:$kind})',{k:e[k] for k in ('id','name','kind')})
    for s in model['sources']:conn.execute('CREATE (:Source {id:$id,text:$text,section:$section,updated:$updated,evidence_group:$evidence_group})',{k:s[k] for k in ('id','text','section','updated','evidence_group')})
    for c in claims:
        conn.execute("CREATE (:Claim {id:$id,predicate:$predicate,context:$context,owner:'north',valid_from:NULL,valid_until:NULL})",{k:c[k] for k in ('id','predicate','context')})
        for table,eid in [('SUBJECT',c['subject']),('OBJECT',c['object'])]:
            conn.execute(f'MATCH (c:Claim {{id:$cid}}),(e:Entity {{id:$eid}}) CREATE (c)-[:{table}]->(e)',dict(cid=c['id'],eid=eid))
        conn.execute('MATCH (c:Claim {id:$cid}),(s:Source {id:$sid}) CREATE (c)-[:SUPPORTED_BY]->(s)',dict(cid=c['id'],sid=c['source']))
    conn.execute('COMMIT');conn.close();db.close()
    db=kuzu.Database(str(OUT/'v1_graph.db'));conn=kuzu.Connection(db)
    exported=dict(entities=rows(conn,'MATCH (e:Entity) RETURN e.id AS id,e.name AS name,e.kind AS kind ORDER BY e.id'),
                  claims=rows(conn,'MATCH (a:Entity)<-[:SUBJECT]-(c:Claim)-[:OBJECT]->(b:Entity),(c)-[:SUPPORTED_BY]->(s:Source) RETURN c.id AS id,a.id AS subject,b.id AS object,b.name AS value,c.predicate AS predicate,c.context AS context,s.id AS source ORDER BY c.id'))
    assert len(exported['claims'])==len(claims)
    conn.close();db.close()
    exported['meta']=dict(nodes=len(model['entities'])+len(values)+len(claims)+len(model['sources']),edges=3*len(claims),
                          description='Minimal v1 projection: claim nodes, literal-as-entity leaves, original evidence retained; no typed rule/value bindings',persistence_verified=True)
    return exported


def v2(model):
    domains=sorted({c['domain'] for c in model['contexts']})
    db,conn=open_new(OUT/'v2_graph.db',[
        'CREATE NODE TABLE Entity(id STRING,name STRING,kind STRING,aliases STRING,namespace STRING,PRIMARY KEY(id))',
        'CREATE NODE TABLE Domain(id STRING,name STRING,owner STRING,PRIMARY KEY(id))',
        'CREATE NODE TABLE Context(id STRING,name STRING,domain STRING,owner STRING,PRIMARY KEY(id))',
        'CREATE NODE TABLE Source(id STRING,text STRING,section STRING,updated STRING,origin STRING,evidence_group STRING,span_start INT64,span_end INT64,PRIMARY KEY(id))',
        'CREATE NODE TABLE Record(id STRING,record_key STRING,kind STRING,title STRING,payload STRING,context STRING,domain STRING,owner STRING,modality STRING,source_updated STRING,valid_from INT64,valid_until INT64,numeric_value DOUBLE,unit STRING,metric_name STRING,framework STRING,extraction STRING,PRIMARY KEY(id))',
        'CREATE REL TABLE HAS_DOMAIN(FROM Entity TO Domain)',
        'CREATE REL TABLE HAS_CONTEXT(FROM Domain TO Context)',
        'CREATE REL TABLE CONTAINS(FROM Context TO Record)',
        'CREATE REL TABLE SUBJECT(FROM Record TO Entity)',
        'CREATE REL TABLE REFERENCES(FROM Record TO Entity,role STRING)',
        'CREATE REL TABLE USING_FRAMEWORK(FROM Record TO Entity)',
        'CREATE REL TABLE SUPPORTED_BY(FROM Record TO Source,quote STRING)',
    ])
    conn.execute('BEGIN TRANSACTION')
    for e in model['entities']:
        conn.execute('CREATE (:Entity {id:$id,name:$name,kind:$kind,aliases:$aliases,namespace:$namespace})',{**e,'aliases':json.dumps(e['aliases'])})
    for d in domains:
        conn.execute("CREATE (:Domain {id:$id,name:$name,owner:'north'})",dict(id=d,name=d))
        conn.execute('MATCH (e:Entity {id:\'north\'}),(d:Domain {id:$id}) CREATE (e)-[:HAS_DOMAIN]->(d)',{'id':d})
    for c in model['contexts']:
        conn.execute('CREATE (:Context {id:$id,name:$name,domain:$domain,owner:$owner})',c)
        conn.execute('MATCH (d:Domain {id:$did}),(c:Context {id:$cid}) CREATE (d)-[:HAS_CONTEXT]->(c)',dict(did=c['domain'],cid=c['id']))
    for s in model['sources']:
        conn.execute('CREATE (:Source {id:$id,text:$text,section:$section,updated:$updated,origin:$origin,evidence_group:$evidence_group,span_start:$span_start,span_end:$span_end})',s)
    source_map={s['id']:s for s in model['sources']}
    for r in model['records']:
        args={k:r[k] for k in ('id','kind','title','context','domain','modality','source_updated','numeric_value','unit','framework','extraction')}
        args.update(record_key=r['key'],payload=json.dumps(r['payload'],ensure_ascii=False),metric_name=r['payload'].get('metric'))
        conn.execute("CREATE (:Record {id:$id,record_key:$record_key,kind:$kind,title:$title,payload:$payload,context:$context,domain:$domain,owner:'north',modality:$modality,source_updated:$source_updated,valid_from:NULL,valid_until:NULL,numeric_value:$numeric_value,unit:$unit,metric_name:$metric_name,framework:$framework,extraction:$extraction})",args)
        conn.execute('MATCH (c:Context {id:$cid}),(r:Record {id:$rid}) CREATE (c)-[:CONTAINS]->(r)',dict(cid=r['context'],rid=r['id']))
        conn.execute('MATCH (r:Record {id:$rid}),(e:Entity {id:$eid}) CREATE (r)-[:SUBJECT]->(e)',dict(rid=r['id'],eid=r['subject']))
        for role,eid in r['refs'].items():conn.execute('MATCH (r:Record {id:$rid}),(e:Entity {id:$eid}) CREATE (r)-[:REFERENCES {role:$role}]->(e)',dict(rid=r['id'],eid=eid,role=role))
        if r['framework']:conn.execute('MATCH (r:Record {id:$rid}),(e:Entity {id:$eid}) CREATE (r)-[:USING_FRAMEWORK]->(e)',dict(rid=r['id'],eid=r['framework']))
        for sid in r['sources']:conn.execute('MATCH (r:Record {id:$rid}),(s:Source {id:$sid}) CREATE (r)-[:SUPPORTED_BY {quote:$quote}]->(s)',dict(rid=r['id'],sid=sid,quote=source_map[sid]['text']))
    conn.execute('COMMIT');conn.close();db.close()
    db=kuzu.Database(str(OUT/'v2_graph.db'));conn=kuzu.Connection(db)
    records=rows(conn,'MATCH (r:Record)-[:SUBJECT]->(e:Entity) RETURN r.id AS id,r.record_key AS key,r.kind AS kind,r.title AS title,r.payload AS payload,r.context AS context,r.domain AS domain,r.modality AS modality,r.source_updated AS source_updated,r.valid_from AS valid_from,r.valid_until AS valid_until,r.numeric_value AS numeric_value,r.unit AS unit,r.framework AS framework,r.extraction AS extraction,e.id AS subject ORDER BY r.id')
    for r in records:
        r['payload']=json.loads(r['payload'])
        r['sources']=[x['sid'] for x in rows(conn,'MATCH (r:Record {id:$id})-[:SUPPORTED_BY]->(s:Source) RETURN s.id AS sid ORDER BY s.id',{'id':r['id']})]
        r['refs']={x['role']:x['id'] for x in rows(conn,'MATCH (r:Record {id:$id})-[ref:REFERENCES]->(e:Entity) RETURN ref.role AS role,e.id AS id',{'id':r['id']})}
    assert len(records)==len(model['records'])
    counts={table:rows(conn,f'MATCH (n:{table}) RETURN count(n) AS n')[0]['n'] for table in ('Entity','Domain','Context','Record','Source')}
    edge_counts={table:rows(conn,f'MATCH ()-[e:{table}]->() RETURN count(e) AS n')[0]['n'] for table in ('HAS_DOMAIN','HAS_CONTEXT','CONTAINS','SUBJECT','REFERENCES','USING_FRAMEWORK','SUPPORTED_BY')}
    result=dict(entities=model['entities'],domains=domains,contexts=model['contexts'],records=records,sources=model['sources'],
                meta={**model['meta'],'nodes':sum(counts.values()),'edges':sum(edge_counts.values()),'counts':counts,'edge_counts':edge_counts,'persistence_verified':True})
    conn.close();db.close();return result


def probes(v1_data,v2_data):
    by_key={r['key']:r for r in v2_data['records']}
    checks=[]
    def check(name,passed,evidence,baseline):
        assert passed,name
        checks.append(dict(name=name,passed=passed,evidence=evidence,v1_limitation=baseline))
    db=kuzu.Database(str(OUT/'v1_graph.db'));conn=kuzu.Connection(db)
    ambiguous=rows(conn,"MATCH (m:Entity)<-[:OBJECT]-(cm:Claim)-[:SUPPORTED_BY]->(s:Source {id:'S08'}), (s)<-[:SUPPORTED_BY]-(cv:Claim)-[:OBJECT]->(v:Entity) WHERE cm.predicate='metric' AND m.name='Mind' AND cv.predicate='value' RETURN DISTINCT v.name AS candidate ORDER BY candidate")
    conn.close();db.close()
    db=kuzu.Database(str(OUT/'v2_graph.db'));conn=kuzu.Connection(db)
    bound=rows(conn,"MATCH (r:Record) WHERE r.framework='sheet' AND r.metric_name='Mind' RETURN r.numeric_value AS value,r.unit AS unit,r.id AS id")
    assert len(ambiguous)==6 and len(bound)==1 and bound[0]['value']==88
    check('Metric and framework binding',True,{'v1_native_candidates':ambiguous,'v2_native_result':bound},'Flattened metric/value leaves share S08 and no explicit pairing; original sentence can repair it but native binding is ambiguous.')
    units=rows(conn,"MATCH (r:Record) WHERE r.numeric_value IS NOT NULL RETURN r.numeric_value AS value,r.unit AS unit,r.framework AS framework ORDER BY r.id")
    check('SIH percentage is separate from personal scores',len(units)==7 and sum(u['unit']=='percent' for u in units)==1,units,'Generic numeric literals require reconstruction of units, task and framework.')
    conn.close();db.close()
    scenarios=[('simple debugging',{'task':'debugging','errors_uninterpretable':False,'mental_map_lost':False},False),
               ('lost debugging map',{'task':'debugging','errors_uninterpretable':True,'mental_map_lost':True},True),
               ('one condition missing',{'task':'debugging','errors_uninterpretable':True},False)]
    policy_results=[]
    for name,context,expected in scenarios:
        applicable=applicable_policies(v2_data,context);active=any(r['key']=='debug_map' for r in applicable)
        assert active==expected
        policy_results.append(dict(scenario=name,context=context,debug_map_applies=active,record_ids=[r['id'] for r in applicable]))
    check('Conditional debugging policy',True,policy_results,'Action/condition leaves do not provide an executable grouped AND rule; retrieval alone is not applicability.')
    vel=applicable_policies(v2_data,{'persona':'Vel'});kael=applicable_policies(v2_data,{'persona':'Kael'})
    check('Persona-specific rules stay scoped',not any(r['key']=='kael_style' for r in vel) and any(r['key']=='kael_style' for r in kael),{'vel_keys':[r['key'] for r in vel],'kael_keys':[r['key'] for r in kael]},'Flat neighborhood does not itself distinguish rule scope from arbitrary associated traits.')
    check('Duplicate evidence does not create independent confirmation',set(by_key['address']['sources'])=={'C02','P01'} and v2_data['meta']['evidence_group_count']==1,{'one_address_policy':by_key['address']['id'],'sources':by_key['address']['sources'],'independent_groups':1},'Repeated claim leaves are stored separately; same snapshot is not independent corroboration.')
    check('Character mechanics are not agent policies',all(r['kind']=='Mechanism' and r['payload']['executable_agent_instruction'] is False for r in v2_data['records'] if r['key'].startswith('mechanic_')),{'mechanisms':[r['id'] for r in v2_data['records'] if r['kind']=='Mechanism']},'Words such as activates and sustains can be confused with response instructions without modality/type checks.')
    check('Framework labels are attributed descriptions',by_key['narrative']['modality'].startswith('metaphorical') and by_key['roi_interpretation']['payload']['truth_status'].startswith('attributed'),{'narrative':by_key['narrative']['modality'],'roi':by_key['roi_interpretation']['payload']['truth_status']},'A generic fact graph needs explicit attribution to prevent literal biographical or causal conclusions.')
    check('Client is distinct from employer',by_key['employer']['refs']=={'employer':'inditech'} and by_key['tracking_app']['refs']['client']=='priyakanth',{'employer':'Inditech','client':'Priyakanthji Group'},'Relation-role bindings must survive decomposition; built-for does not imply works-at.')
    check('Updated date is not event validity',all(r['source_updated']=='2026-08-21' and r['valid_from'] is None and r['valid_until'] is None for r in v2_data['records']),{'source_updated':'2026-08-21','event_dates':None},'Source order and a shared last-updated date must not create a timeline or supersession.')
    check('All supplied detail statements remain evidenced',set(s['id'] for s in v2_data['sources'])==set(s for r in v2_data['records'] for s in r['sources']),{'detail_bullets':38,'typed_records':62},'Both designs retain original text; the redesign improves structured access rather than inventing new source information.')
    return checks


def synthetic_scale(v1_data,v2_data):
    """Measured query/coverage probe, not a neural retrieval benchmark.

    Append unrelated synthetic recent-work memories to the same owner. Real
    supplied sources and gold policy keys do not change. Both DBs must complete.
    """
    db1=kuzu.Database(str(OUT/'v1_graph.db'));c1=kuzu.Connection(db1)
    db2=kuzu.Database(str(OUT/'v2_graph.db'));c2=kuzu.Connection(db2)
    results=[];inserted=0
    expected={r['id'] for r in v2_data['records'] if r['key']=='debug_map'}
    source_manifest={a['id']:next(r['id'] for r in v2_data['records'] if r['key']==a['record_key']) for a in v1_claims(v2_data)[0]}
    expected_clauses={a['id'] for a in v1_claims(v2_data)[0] if a['record_key']=='debug_map'}
    for total in (0,100,1000,10000):
        for conn,version in ((c1,1),(c2,2)):
            conn.execute('BEGIN TRANSACTION')
            for i in range(inserted,total):
                cid=f'noise_{i:05}'
                if version==1:
                    value_id='value_'+hashlib_token(i)
                    conn.execute("CREATE (:Entity {id:$id,name:$name,kind:'Synthetic value'})",dict(id=value_id,name=f'Synthetic unrelated work episode {i}'))
                    conn.execute("CREATE (:Claim {id:$id,predicate:'reported_work_episode',context:'ctx_synthetic_work',owner:'north',valid_from:NULL,valid_until:NULL})",{'id':cid})
                    conn.execute("MATCH (r:Claim {id:$id}),(u:Entity {id:'north'}),(v:Entity {id:$vid}) CREATE (r)-[:SUBJECT]->(u) CREATE (r)-[:OBJECT]->(v)",dict(id=cid,vid=value_id))
                else:
                    conn.execute("CREATE (:Record {id:$id,record_key:$id,kind:'Activity',title:$title,payload:'{}',context:'ctx_synthetic_work',domain:'Recent Work',owner:'north',modality:'synthetic benchmark noise'})",dict(id=cid,title=f'Synthetic unrelated work episode {i}'))
            conn.execute('COMMIT')
        inserted=total
        sql1="MATCH (c:Claim)-[:OBJECT]->(v:Entity) WHERE c.owner='north' RETURN c.id AS id,v.id AS value_id ORDER BY value_id LIMIT 50"
        sql2="MATCH (r:Record) WHERE r.owner='north' AND r.kind='Policy' AND r.context='ctx_Preferences_debugging' RETURN r.id AS id ORDER BY id LIMIT 50"
        times=[];coverage=[];complete=[]
        for conn,sql in ((c1,sql1),(c2,sql2)):
            rows(conn,sql);durations=[]
            for _ in range(7):
                start=time.perf_counter();hits=rows(conn,sql);durations.append((time.perf_counter()-start)*1000)
            times.append(round(statistics.median(durations),3))
            selected={source_manifest.get(h['id'],h['id']) for h in hits}
            coverage.append(len(expected&selected)/len(expected))
            complete.append(expected_clauses.issubset({h['id'] for h in hits}) if conn is c1 else expected.issubset({h['id'] for h in hits}))
        results.append(dict(synthetic_unrelated_work_records=total,v1_claim_records=len(v1_data['claims'])+total,v2_typed_records=len(v2_data['records'])+total,
                            v1_median_query_ms=times[0],v2_median_query_ms=times[1],v1_debug_clause_seen=bool(coverage[0]),v2_debug_policy_seen=bool(coverage[1]),v1_complete_rule_in_budget=complete[0],v2_complete_rule_in_budget=complete[1],both_databases_completed=True))
    c1.close();db1.close();c2.close();db2.close()
    return dict(results=results,protocol='7 warm local queries per stage, median; same owner; budget 50; synthetic unrelated work records',
                limitation='Compares generic bounded neighbors ordered by hashed value IDs with typed context routing, not full hybrid retrieval or optimized v1. Clause presence is not full rule recovery; fetching the original source can repair fragment loss. Synthetic records have no real-world truth or evidence. These copies contain benchmark noise after the base export.',
                storage_failure_observed=False)


def hashlib_token(i):
    import hashlib
    return hashlib.sha256(str(i).encode()).hexdigest()[:12]


if __name__=='__main__':
    model=build_model();v1_data=v1(model);v2_data=v2(model)
    checks=probes(v1_data,v2_data)
    # Benchmarks get copies so the visualized base databases remain exact.
    import shutil
    benchmark_dir=OUT/'benchmark_routed';benchmark_dir.mkdir()
    for name in ('v1_graph.db','v2_graph.db'):shutil.copy2(OUT/name,benchmark_dir/name)
    real_out=OUT
    globals()['OUT']=benchmark_dir
    scale=synthetic_scale(v1_data,v2_data)
    globals()['OUT']=real_out
    bundle=dict(v1=v1_data,v2=v2_data,checks=checks,scale=scale)
    (OUT/'graph.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(v1_nodes=v1_data['meta']['nodes'],v1_edges=v1_data['meta']['edges'],v2_nodes=v2_data['meta']['nodes'],v2_edges=v2_data['meta']['edges'],checks=len(checks),scale=scale),indent=2))
