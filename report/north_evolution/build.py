"""Extend a copy of the previous KG; never replace or delete older data."""
import json
import shutil
from pathlib import Path
import kuzu
from model import model,OUT,PREVIOUS
from fuzzy import score,relationship,transition


def rows(conn,query,args=None):
    result=conn.execute(query,args or {});cols=result.get_column_names();output=[]
    while result.has_next():output.append(dict(zip(cols,result.get_next())))
    return output


def store(m):
    path=OUT/'evolution.db'
    if path.exists():raise RuntimeError('Refusing to overwrite evolution.db')
    shutil.copy2(PREVIOUS/'v2_graph.db',path)
    db=kuzu.Database(str(path));conn=kuzu.Connection(db)
    for schema in [
        'CREATE NODE TABLE Facet(id STRING,record_id STRING,subject STRING,slot STRING,value STRING,value_kind STRING,scope STRING,cardinality STRING,batch INT64,age_base DOUBLE,half_life DOUBLE,historical BOOLEAN,quality DOUBLE,support DOUBLE,conflict DOUBLE,protected BOOLEAN,status STRING,score DOUBLE,fuzzy_trace STRING,PRIMARY KEY(id))',
        'CREATE REL TABLE HAS_FACET(FROM Record TO Facet)',
        'CREATE REL TABLE FACET_EVIDENCE(FROM Facet TO Source)',
        'CREATE REL TABLE CONFIRMS(FROM Facet TO Facet,reason STRING,origin STRING,independence STRING)',
        'CREATE REL TABLE CONTRADICTS(FROM Facet TO Facet,reason STRING,resolved BOOLEAN)',
        'CREATE REL TABLE SUPERSEDES(FROM Facet TO Facet,reason STRING,accepted BOOLEAN)',
        'CREATE REL TABLE POSSIBLE_RELATION(FROM Record TO Record,reason STRING,status STRING)',
        'CREATE REL TABLE SAME_AS(FROM Entity TO Entity,source_id STRING,reason STRING,status STRING)',
    ]:conn.execute(schema)
    domains={x['name'] for x in rows(conn,'MATCH (d:Domain) RETURN d.name AS name')}
    contexts={x['id'] for x in rows(conn,'MATCH (c:Context) RETURN c.id AS id')}
    conn.execute('BEGIN TRANSACTION')
    for e in m['new_entities']:
        conn.execute('CREATE (:Entity {id:$id,name:$name,kind:$kind,aliases:$aliases,namespace:$namespace})',{**e,'aliases':'[]'})
    for s in m['new_sources']:
        conn.execute('CREATE (:Source {id:$id,text:$text,section:$section,updated:NULL,origin:$origin,evidence_group:$evidence_group,span_start:$span_start,span_end:$span_end})',
                     {k:s[k] for k in ('id','text','section','origin','evidence_group','span_start','span_end')})
    clarification=dict(id='C_ORG',text=m['identity']['evidence'],section='User clarification',updated=None,origin='explicit user confirmation for random test data',evidence_group='test-clarification',batch=3)
    conn.execute("CREATE (:Source {id:$id,text:$text,section:$section,updated:NULL,origin:$origin,evidence_group:$evidence_group,span_start:NULL,span_end:NULL})",{k:clarification[k] for k in ('id','text','section','origin','evidence_group')})
    for r in m['new_records']:
        if r['domain'] not in domains:
            conn.execute("CREATE (:Domain {id:$id,name:$id,owner:'north'})",{'id':r['domain']})
            conn.execute("MATCH (n:Entity {id:'north'}),(d:Domain {id:$id}) CREATE (n)-[:HAS_DOMAIN]->(d)",{'id':r['domain']});domains.add(r['domain'])
        if r['context'] not in contexts:
            conn.execute("CREATE (:Context {id:$id,name:$name,domain:$domain,owner:'north'})",dict(id=r['context'],name=r['context'],domain=r['domain']))
            conn.execute('MATCH (d:Domain {id:$domain}),(c:Context {id:$id}) CREATE (d)-[:HAS_CONTEXT]->(c)',dict(domain=r['domain'],id=r['context']));contexts.add(r['context'])
        args={k:r[k] for k in ('id','kind','title','context','domain','modality','numeric_value','unit','framework','extraction')}
        args.update(record_key=r['key'],payload=json.dumps(r['payload'],ensure_ascii=False))
        conn.execute("CREATE (:Record {id:$id,record_key:$record_key,kind:$kind,title:$title,payload:$payload,context:$context,domain:$domain,owner:'north',modality:$modality,source_updated:NULL,valid_from:NULL,valid_until:NULL,numeric_value:$numeric_value,unit:$unit,metric_name:NULL,framework:$framework,extraction:$extraction})",args)
        conn.execute('MATCH (c:Context {id:$cid}),(r:Record {id:$rid}) CREATE (c)-[:CONTAINS]->(r)',dict(cid=r['context'],rid=r['id']))
        conn.execute('MATCH (r:Record {id:$rid}),(e:Entity {id:$eid}) CREATE (r)-[:SUBJECT]->(e)',dict(rid=r['id'],eid=r['subject']))
        for role,eid in r['refs'].items():
            conn.execute('MATCH (r:Record {id:$rid}),(e:Entity {id:$eid}) CREATE (r)-[:REFERENCES {role:$role}]->(e)',dict(rid=r['id'],eid=eid,role=role))
        for sid in r['sources']:
            text=next(s['text'] for s in m['new_sources'] if s['id']==sid)
            conn.execute('MATCH (r:Record {id:$rid}),(s:Source {id:$sid}) CREATE (r)-[:SUPPORTED_BY {quote:$quote}]->(s)',dict(rid=r['id'],sid=sid,quote=text))
    for f in m['facets']:
        params={k:f[k] for k in ('id','record_id','subject','slot','value_kind','scope','cardinality','batch','age_base','half_life','historical','quality','support','conflict','protected','status','score')}
        params.update(value=json.dumps(f['value'],ensure_ascii=False),fuzzy_trace=json.dumps(f['fuzzy']))
        conn.execute('CREATE (:Facet {id:$id,record_id:$record_id,subject:$subject,slot:$slot,value:$value,value_kind:$value_kind,scope:$scope,cardinality:$cardinality,batch:$batch,age_base:$age_base,half_life:$half_life,historical:$historical,quality:$quality,support:$support,conflict:$conflict,protected:$protected,status:$status,score:$score,fuzzy_trace:$fuzzy_trace})',params)
        conn.execute('MATCH (r:Record {id:$rid}),(f:Facet {id:$fid}) CREATE (r)-[:HAS_FACET]->(f)',dict(rid=f['record_id'],fid=f['id']))
        for sid in f['sources']:
            conn.execute('MATCH (f:Facet {id:$fid}),(s:Source {id:$sid}) CREATE (f)-[:FACET_EVIDENCE]->(s)',dict(fid=f['id'],sid=sid))
    for e in m['relations']:
        conn.execute('MATCH (a:Facet {id:$source}),(b:Facet {id:$target}) CREATE (a)-[:CONFIRMS {reason:$reason,origin:$origin,independence:$independence}]->(b)',{k:e[k] for k in ('source','target','reason','origin','independence')})
    conn.execute("MATCH (a:Entity {id:'inditech_systems'}),(b:Entity {id:'inditech'}) CREATE (a)-[:SAME_AS {source_id:'C_ORG',reason:'Explicit user-confirmed alias, not an automatic name match',status:'accepted'}]->(b)")
    new_keys={r['key']:r['id'] for r in m['new_records']};old_keys={r['key']:r['id'] for r in m['old']['records']}
    for e in m['hypotheses']:
        conn.execute('MATCH (a:Record {id:$a}),(b:Record {id:$b}) CREATE (a)-[:POSSIBLE_RELATION {reason:$reason,status:$status}]->(b)',
                     dict(a=new_keys[e['source']],b=old_keys[e['target']],reason=e['reason'],status=e['status']))
    conn.execute('COMMIT');conn.close();db.close()
    # Reopen and read the facts, links, and fuzzy values that the viewer will use.
    db=kuzu.Database(str(path));conn=kuzu.Connection(db)
    stored=rows(conn,'MATCH (f:Facet) RETURN f.id AS id,f.score AS score,f.fuzzy_trace AS trace ORDER BY f.id')
    assert len(stored)==len(m['facets'])
    fac={f['id']:f for f in m['facets']}
    for row in stored:
        assert row['score']==fac[row['id']]['score'];fac[row['id']]['fuzzy']=json.loads(row['trace'])
    confirmations=rows(conn,"MATCH (a:Facet)-[r:CONFIRMS]->(b:Facet) RETURN a.id AS source,b.id AS target,r.reason AS reason")
    assert len(confirmations)==9
    old_source_text={s['id']:s['text'] for s in m['old']['sources']}
    stored_sources={s['id']:s['text'] for s in rows(conn,'MATCH (s:Source) RETURN s.id AS id,s.text AS text')}
    assert all(stored_sources[sid]==text for sid,text in old_source_text.items())
    assert all(stored_sources[s['id']]==s['text'] for s in m['new_sources'])
    counts={label:rows(conn,f'MATCH (n:{label}) RETURN count(n) AS n')[0]['n'] for label in ('Entity','Domain','Context','Record','Source','Facet')}
    edge_counts={label:rows(conn,f'MATCH ()-[r:{label}]->() RETURN count(r) AS n')[0]['n'] for label in ('CONFIRMS','CONTRADICTS','SUPERSEDES','SAME_AS','POSSIBLE_RELATION')}
    conn.close();db.close()
    m['clarification_source']=clarification;m['meta'].update(persistence_verified=True,counts=counts,relationship_counts=edge_counts,database=str(path))


def counterfactuals(m):
    """Positive conflict controls in a separate database; not supplied test data."""
    path=OUT/'counterfactuals.db'
    if path.exists():raise RuntimeError('Refusing to overwrite counterfactuals.db')
    db=kuzu.Database(str(path));conn=kuzu.Connection(db)
    for schema in [
        'CREATE NODE TABLE TestClaim(id STRING,case_id STRING,text STRING,slot STRING,value STRING,scope STRING,protected BOOLEAN,score DOUBLE,status STRING,prior_acceptance DOUBLE,origin STRING,PRIMARY KEY(id))',
        'CREATE REL TABLE CONTRADICTS(FROM TestClaim TO TestClaim,reason STRING,resolved BOOLEAN)',
        'CREATE REL TABLE SUPERSEDES(FROM TestClaim TO TestClaim,reason STRING,accepted BOOLEAN)',
    ]:conn.execute(schema)
    fixtures=[]
    base_address=next(f for f in m['facets'] if f['slot']=='response.preferred_address')
    base_year=next(f for f in m['facets'] if f['slot']=='education.year')
    for name,base,value,text,explicit_correction,explicit_change,same_time,accepted,quality in [
        ('protected_name_change',base_address,'Aarush','Synthetic test: From now on call me Aarush instead of North.',False,True,False,True,.85),
        ('protected_year_correction',base_year,4,'Synthetic test: Correction to the earlier profile: that study year was 4, not 3.',True,False,True,True,.85),
        ('unaccepted_conflicting_year',base_year,4,'Synthetic untrusted test: The same earlier profile should say year 4.',False,False,True,False,.35),
    ]:
        old={**base,'id':name+'_old','protected':True,'score':1.}
        new={**base,'id':name+'_new','value':value,'protected':False,'score':score(quality=quality)['score'],'quality':quality,'age_base':0}
        relation,reason=relationship(old,new,explicit_change=explicit_change,explicit_correction=explicit_correction,same_time=same_time)
        a,b=transition(old,new,relation,accepted=accepted)
        if not accepted:
            a['conflict']=quality;b['conflict']=.85
        for item in (a,b):
            item['fuzzy']=score(quality=item['quality'],age_days=item['age_base'],half_life=item['half_life'],
                support=item['support'],conflict=item['conflict'],protected=item['protected'],status=item['status'])
            item['score']=item['fuzzy']['score']
        for item,label in ((a,'Previous claim retained'),(b,text)):
            conn.execute("CREATE (:TestClaim {id:$id,case_id:$case_id,text:$text,slot:$slot,value:$value,scope:$scope,protected:$protected,score:$score,status:$status,prior_acceptance:$prior,origin:'SYNTHETIC positive control; not user-supplied data'})",
                         dict(id=item['id'],case_id=name,text=label,slot=item['slot'],value=json.dumps(item['value']),scope=item['scope'],protected=item['protected'],score=item['score'],status=item['status'],prior=item.get('historical_score')))
        if relation in {'CONTRADICTS','CONTRADICTS_AND_SUPERSEDES'}:
            conn.execute('MATCH (a:TestClaim {id:$new}),(b:TestClaim {id:$old}) CREATE (a)-[:CONTRADICTS {reason:$reason,resolved:$resolved}]->(b)',dict(new=b['id'],old=a['id'],reason=reason,resolved=accepted))
        if accepted and relation in {'SUPERSEDES','CONTRADICTS_AND_SUPERSEDES'}:
            conn.execute('MATCH (a:TestClaim {id:$new}),(b:TestClaim {id:$old}) CREATE (a)-[:SUPERSEDES {reason:$reason,accepted:true}]->(b)',dict(new=b['id'],old=a['id'],reason=reason))
        fixtures.append(dict(case=name,text=text,relation=relation,reason=reason,accepted=accepted,old=a,new=b,
                             history_note='Prior acceptance is retained as audit history, not proof that a retracted claim was historically true.'))
    conn.close();db.close()
    db=kuzu.Database(str(path));conn=kuzu.Connection(db)
    stored=rows(conn,'MATCH (n:TestClaim) RETURN n.id AS id,n.score AS score,n.status AS status')
    assert len(stored)==6
    edges=rows(conn,"MATCH (a:TestClaim)-[r:CONTRADICTS]->(b:TestClaim) RETURN a.id AS source,b.id AS target,'CONTRADICTS' AS type,r.resolved AS resolved")
    edges+=rows(conn,"MATCH (a:TestClaim)-[r:SUPERSEDES]->(b:TestClaim) RETURN a.id AS source,b.id AS target,'SUPERSEDES' AS type,r.accepted AS accepted")
    conn.close();db.close()
    return dict(fixtures=fixtures,edges=edges,source_label='Separate synthetic controls, not actual incoming data',database=str(path),persistence_verified=True)


def verify(m):
    f=m['facets'];links=m['relations'];keys={r['key']:r['id'] for r in m['old']['records']};newkeys={r['key']:r['id'] for r in m['new_records']}
    checks=[]
    def check(name,ok,evidence):assert ok,name;checks.append(dict(name=name,passed=True,evidence=evidence))
    degree=[x for x in f if x['record_id']==keys['education']]
    confirmed={e['target'] for e in links}
    check('Partial confirmation does not refresh the degree or year',all((x['id'] in confirmed)==(x['slot']=='education.discipline') for x in degree),[{k:x[k] for k in ('slot','value','score','last_confirmation_batch','age_base')} for x in degree])
    address=next(x for x in f if x['slot']=='response.preferred_address')
    check('Full name does not replace preferred address',address['value']=='North' and address['id'] not in confirmed,dict(address=address['value'],name='Aarush Srivastava',conflict=False))
    check('No unjustified actual contradictions or supersessions',m['meta']['relationship_counts']['CONTRADICTS']==0 and m['meta']['relationship_counts']['SUPERSEDES']==0,m['meta']['relationship_counts'])
    employment=next(x for x in f if x['slot']=='employment.organization')
    internship=next(x for x in f if x['slot']=='internship.organization')
    rel,reason=relationship(employment,internship,aliases={'inditech_systems':'inditech'})
    check('Alias confirmation does not supersede employment',rel=='ADDITIVE',dict(relation=rel,reason=reason,alias_accepted=True))
    stack=[x for x in f if x['slot']=='development.primary_stack']
    a=next(x for x in stack if x['value']=='sqlite');b=next(x for x in stack if x['value']=='postgres')
    rel,reason=relationship(a,b)
    check('SQLite and PostgreSQL coexist in a multi-valued stack',rel=='ADDITIVE',dict(relation=rel,reason=reason))
    compact=next(r for r in m['new_records'] if r['key']=='synthetic_term')
    check('Synthetic terminology stays conditional',len(compact['payload']['trigger']['all'])==3,compact['payload'])
    check('Undated sources remain undated',all(s['updated'] is None for s in m['new_sources']) and all(r['valid_from'] is None for r in m['new_records']),dict(receipt_order=2,event_dates=None))
    values=[score(age_days=d,half_life=180)['score'] for d in (0,53,90,180,365)]
    check('Ordinary scores decay with age',all(a>=b for a,b in zip(values,values[1:])),dict(days=[0,53,90,180,365],scores=values))
    pins=[score(age_days=d,half_life=180,protected=True,conflict=1)['score'] for d in (0,53,365,10000)]
    check('Protection blocks ordinary decay and unaccepted conflict',all(v==1 for v in pins),dict(days=[0,53,365,10000],scores=pins))
    check('Same-author support is not independent proof',all(x['support']<=.35 for x in f) and all(x['score']<1 for x in f),dict(support_input=.35,default_protected_records=0,probabilities_calibrated=False))
    historical=[x for x in f if x['historical']]
    check('Completed results do not become false from aging',all(score(age_days=36500,half_life=x['half_life'])['score']==score(age_days=0,half_life=x['half_life'])['score'] for x in historical),dict(historical_facets=len(historical),tested_age_days=36500,aging_policy='no temporal credibility decay for completed facts'))
    cs=m['counterfactuals']['fixtures']
    check('Accepted changes transfer protected score one',all(c['new']['score']==1 and c['old']['score']==0 for c in cs if c['accepted']),[dict(case=c['case'],old_score=c['old']['score'],new_score=c['new']['score'],relation=c['relation']) for c in cs])
    check('Unaccepted contradiction remains disputed',cs[2]['old']['score']==1 and cs[2]['old']['status']=='disputed' and cs[2]['new']['score']<1,dict(case=cs[2]['case'],old_score=cs[2]['old']['score'],new_score=cs[2]['new']['score'],status=cs[2]['old']['status']))
    check('Old records and sources are retained',m['meta']['counts']['Record']==91 and m['meta']['counts']['Source']==45,dict(previous_records=62,previous_sources=38,new_records=29,new_sources=6,clarifications=1))
    m['checks']=checks


if __name__=='__main__':
    m=model();store(m);m['counterfactuals']=counterfactuals(m);verify(m)
    (OUT/'graph.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(counts=m['meta']['counts'],relations=m['meta']['relationship_counts'],checks=len(m['checks']),synthetic_edges=m['counterfactuals']['edges']),indent=2))
