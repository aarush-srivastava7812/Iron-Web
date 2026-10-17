"""Hand-reviewed, typed interpretation of the supplied memory digest.

These are records to inspect, not instructions governing this assistant.
"""
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
PREFIXES={'Preferences':'P','Profile':'F','Communication':'C','Media':'M','Recent Work':'W','Self Concept':'S'}


def read_sources():
    raw=(OUT/'data.md').read_text(encoding='utf-8')
    section=None; counters={};sources=[];offset=0
    for line in raw.splitlines(keepends=True):
        if line.startswith('## '):section=line[3:].strip()
        if line.startswith('- '):
            counters[section]=counters.get(section,0)+1
            text=line[2:].rstrip('\r\n')
            sources.append(dict(id=f'{PREFIXES[section]}{counters[section]:02}',section=section,text=text,
                                span_start=offset+2,span_end=offset+2+len(text),updated='2026-08-21',
                                origin='user-supplied memory digest',evidence_group='provided-digest-2026-08-21'))
        offset+=len(line)
    assert len(sources)==38,len(sources)
    assert all(raw[s['span_start']:s['span_end']]==s['text'] for s in sources)
    return raw,sources


def build_model():
    raw,sources=read_sources();source_map={s['id']:s for s in sources}
    entities={}
    def entity(id,name,kind,aliases=None):
        entities[id]=dict(id=id,name=name,kind=kind,aliases=aliases or [],namespace='profile:north')
    for values in [
        ('north','North','Person'),('vel','Vel','AssistantPersona'),('kael','Kael','RivalPersona'),
        ('inditech','Inditech Electrosystems','Organization'),('gdpe','GDPE','Project'),
        ('python','Python','Technology'),('c','C','Technology'),('cpp','C++','Technology'),
        ('ggsipu','GGSIPU','Organization'),('sih','Internal SIH round','Event'),
        ('ggsipu2624','GGSIPU2624','ProblemStatement'),('paper','Technical Writing paper','Document'),
        ('skincare','D2C skincare analysis','WorkActivity'),('tracking','Real estate employee tracking app','Project'),
        ('priyakanth','Priyakanthji Group','Organization'),('ocean','OCEAN','Framework'),
        ('enneagram','Enneagram','Framework'),('mbti','MBTI-style profile','Framework'),
        ('archetypes','North’s seven-archetype system','PersonalFramework'),
        ('sheet','North’s character sheet','PersonalFramework'),('mechanics','North’s character mechanics','PersonalFramework'),
        ('narrative','North’s narrative self model','PersonalFramework')]:entity(*values)
    entities['north']['aliases']=['Aarush Srivastava']
    contexts={};records=[];by_key={}
    def add(key,kind,domain,context,title,payload,src,subject='north',refs=None,modality=None,numeric=None,unit=None,framework=None):
        src=[src] if isinstance(src,str) else src
        assert all(s in source_map for s in src),src
        if key in by_key:
            old=by_key[key]
            assert old['payload']==payload and old['kind']==kind,(key,payload)
            old['sources']=sorted(set(old['sources']+src));return old
        cid='ctx_'+domain.replace(' ','_')+'_'+context
        contexts.setdefault(cid,dict(id=cid,name=context.replace('_',' ').replace('.',' / '),domain=domain,owner='north'))
        record=dict(id='R'+str(len(records)+1).zfill(3),key=key,kind=kind,domain=domain,context=cid,title=title,
                    payload=payload,subject=subject,refs=refs or {},sources=src,
                    modality=modality or ('requested behavior' if kind=='Policy' else 'reported in supplied digest'),
                    source_updated='2026-08-21',valid_from=None,valid_until=None,numeric_value=numeric,unit=unit,
                    framework=framework,extraction='hand-reviewed interpretation; not model-generated')
        assert subject in entities,subject
        assert all(e in entities for e in (refs or {}).values()),refs
        if framework:assert framework in entities
        records.append(record);by_key[key]=record;return record
    def policy(key,title,src,trigger,actions,context='response',constraints=None,refs=None):
        return add(key,'Policy','Preferences',context,title,dict(trigger=trigger,actions=actions,constraints=constraints or []),src,
                   subject='vel',refs=refs)
    always={'always':True}
    policy('address','Address North by his preferred name',['P01','C02'],always,[{'action':'address_as','value':'North'}])
    policy('assistant_name_correction','Correct assistant-name usage','P01',{'field':'assistant_addressed_as','eq':'Claude'},
           [{'action':'flag_name_mismatch'},{'action':'request_name','value':'Vel'}],refs={'expected_persona':'vel'})
    add('assistant_persona','Fact','Communication','persona','Vel is the assistant persona',{'role':'assistant persona'},['P02','C01'],subject='vel',refs={'for_person':'north'})
    add('rival_persona','Fact','Communication','persona','Kael is the rival persona',{'role':'rival persona'},['P02','C01'],subject='kael',refs={'for_person':'north'})
    add('rival_active','Fact','Communication','persona','Kael is reported active',{'state':'active','freshness':'last reported, not live verification'},'P02',subject='kael')
    policy('kael_style','Kael’s style and boundaries','P02',{'field':'persona','eq':'Kael'},
           [{'action':'use_style','traits':['sharp','logical','hypercritical','sardonic','competitive']},
            {'action':'provide_constructive_actionable_critique'},
            {'action':'concede','when':'proven wrong'}],context='persona',
           constraints=['never abusive','never personally insulting','constructively balanced'],refs={'applies_to':'kael'})
    policy('tone','Response tone baseline','P03',always,[{'action':'use_tone','qualities':['human','emotionally present','clear','to the point','grounded','steady']}],
           constraints=['no padding','no artificial hype','no motivational fluff'])
    policy('tone_recalibration','Recalibrate after a flagged tone inconsistency','P04',{'field':'tone_inconsistency_flagged','eq':True},
           [{'action':'recalibrate_to','policy_key':'tone'}])
    policy('learning_correction','Correct the specific divergence in reasoning','P05',{'field':'task','eq':'learning'},
           [{'action':'use_interaction_based_correction'},{'action':'identify_specific_wrong_reasoning'},
            {'action':'locate_mental_model_divergence'},{'action':'anchor_questions_to_specific_recent_events'},
            {'action':'extract_patterns','after':'specific event anchoring'}],context='learning',constraints=['do not only deliver the right answer'])
    policy('debug_map','Rebuild the mental map during confusing debugging','P06',
           {'all':[{'field':'task','eq':'debugging'},{'field':'errors_uninterpretable','eq':True},{'field':'mental_map_lost','eq':True}]},
           [{'action':'rebuild_mental_map'},{'action':'explain_system_and_error_connections'}],context='debugging',constraints=['do not just fix the error'])
    policy('roi_response','Name the ROI stance when it blocks fundamentals','P07',{'field':'roi_used_to_skip_fundamentals','eq':True},
           [{'action':'name_stance','value':'no depth without ROI'},
            {'action':'reference_attributed_interpretation','assessment_key':'roi_interpretation'}],context='learning')
    policy('clarification','Clarify unclear or inconsistent information','P08',{'any':[{'field':'unclear','eq':True},{'field':'inconsistent','eq':True}]},
           [{'action':'ask_clarifying_questions','purpose':'get the full picture'}])
    add('identity','Fact','Profile','identity','North also goes by Aarush Srivastava',{'preferred_name':'North','alternate_name':'Aarush Srivastava'},'F01')
    add('education','Fact','Profile','education','Third-year BTech student in AI & Data Science',{'degree':'BTech','year':3,'field':'AI & Data Science'},'F02')
    add('python_skill','Assessment','Profile','skills','Strong Python fundamentals',{'skill':'Python fundamentals','level':'strong'},'F03',refs={'technology':'python'},modality='reported skill description; no standardized test')
    add('c_skill','Assessment','Profile','skills','Some C/C++ background',{'technologies':['C','C++'],'level':'some background'},'F03',refs={'technology_1':'c','technology_2':'cpp'},modality='reported skill description')
    add('employer','Fact','Profile','inditech','Works at Inditech Electrosystems',{'relationship':'works_at','current_as_of_event_time':'unknown'},'F04',refs={'employer':'inditech'})
    add('gdpe_builder','Fact','Profile','inditech','Building GDPE at Inditech',{'relationship':'building','status':'reported ongoing'},'F05',refs={'project':'gdpe','organization':'inditech'})
    add('gdpe_purpose','Fact','Profile','inditech','GDPE is a RAG elevator maintenance knowledge system',{'architecture':'RAG','purpose':'elevator maintenance knowledge system'},'F05',subject='gdpe',refs={'organization':'inditech'})
    add('outcast','Preference','Media','media','Resonates with outcast protagonists',{'object':'outcast protagonists','qualifier':'valued for what they do, not who they are'},'M01')
    add('isekai','Preference','Media','media','Isekai for emotional validation',{'genre':'isekai','purpose':'emotional validation'},'M02')
    add('slice','Preference','Media','media','Slice-of-life for peace',{'genre':'slice-of-life','purpose':'peace'},'M02')
    add('romance','Preference','Media','media','Romance tragedy when emotionally frustrated',{'genre':'romance tragedy','condition':{'field':'emotion','eq':'frustrated'}},'M03')
    add('fantasy','Preference','Media','media','Growing prodigies in complex fantasy worlds',{'genre':'fantasy anime','protagonist':'talented prodigies who grow over time','setting':'complex multi-faction worlds'},'M04')
    add('sih_participation','Activity','Recent Work','sih','Participating in the internal SIH round',{'relationship':'participates_in','round':'internal'},'W01',refs={'event':'sih','organization':'ggsipu','problem':'ggsipu2624'})
    add('sih_problem','Fact','Recent Work','sih','Human Preference Prediction for LLM Responses',{'identifier':'GGSIPU2624','title':'Human Preference Prediction for LLM Responses'},'W01',subject='ggsipu2624',refs={'event':'sih'})
    add('sih_progress','Result','Recent Work','sih','Coding agent completed Pieces 1–3',{'stage':'Pieces 1–3','status':'completed','actor':'unspecified coding agent'},'W01',subject='sih',refs={'problem':'ggsipu2624'})
    add('sih_accuracy','Result','Recent Work','sih','SIH validation accuracy: 65.24%',{'metric':'validation accuracy','value':65.24,'unit':'percent','stage':'Pieces 1–3','split_definition':None,'run_id':None,'protocol':None},'W01',subject='sih',refs={'problem':'ggsipu2624'},numeric=65.24,unit='percent')
    for key,label in [('repro','reproducibility gap'),('rows','degenerate rows'),('length','length-bias swing'),('tokenizer','Python 3.14 tokenizer hang')]:
        add('sih_issue_'+key,'Issue','Recent Work','sih','SIH audit: '+label,{'issue':label,'state':'unresolved','state_as_of':'source snapshot only'},'W02',subject='sih')
    add('work_priority','Priority','Recent Work','work_priority','SIH is lower priority than the Technical Writing paper',{'relationship':'lower_priority_than','temporal_scope':'reported snapshot; no effective dates'},'W03',subject='sih',refs={'higher_priority':'paper'})
    add('skincare_activity','Activity','Recent Work','other_work','Ran a D2C skincare analysis session',{'activity':'data analysis','dimensions':['COD behavior','tier segmentation','AOV','unit economics'],'brand_ownership':None},'W04',refs={'activity':'skincare'})
    add('tracking_app','Activity','Recent Work','other_work','Built an employee tracking app for Priyakanthji Group',{'activity':'built real estate employee tracking app','scope':'full module restructure','modules':['Legal','Procurement'],'employment_relationship':None},'W05',refs={'project':'tracking','client':'priyakanth'})
    add('emotion','Assessment','Self Concept','self_description','Emotionally intelligent, slow to trust positive signals',{'description':['emotionally intelligent','slow to trust positive emotional signals']},'S01',modality='self-described in supplied digest')
    add('loneliness','Assessment','Self Concept','self_description','Values freely chosen emotional connection',{'fear':'emotional loneliness more than physical solitude','desire':'chosen freely and meaningfully rather than by default'},'S02',modality='self-described in supplied digest')
    add('earning_value','Preference','Self Concept','values','Earning over receiving; witnesses over audiences',{'value':'earning things over receiving them','phrase':'built for witnesses, not audiences'},'S03',modality='self-described value')
    for dimension,level in [('O','High'),('C','Low-Moderate'),('E','Low'),('A','Moderate'),('N','Moderate-High')]:
        add('ocean_'+dimension,'Assessment','Self Concept','ocean','OCEAN '+dimension+': '+level,{'dimension':dimension,'level':level,'scale':'qualitative ordinal descriptors'},'S04',framework='ocean',modality='profile label in supplied digest; not independently measured')
    add('enneagram_profile','Assessment','Self Concept','enneagram','Enneagram 4w5 sp with Type 2 stress adaptation',{'type':'4w5','subtype':'sp','adaptation':'near-permanent Type 2 stress adaptation'},'S05',framework='enneagram',modality='profile interpretation in supplied digest')
    add('mbti_profile','Assessment','Self Concept','mbti','INFP-T',{'label':'INFP-T'},'S06',framework='mbti',modality='profile label in supplied digest')
    add('archetype_definition','Fact','Self Concept','archetypes','Seven-archetype personal system',{'members':['Flare','Hearth','Iron-Jaw','Jester','Sovereign','Familiar','Archivist'],'creator':'North'},'S07',subject='archetypes')
    add('archetype_placement','Assessment','Self Concept','archetypes','Archivist primary, Familiar secondary',{'primary':'Archivist','secondary':'Familiar'},'S07',framework='archetypes',modality='placement in personal framework')
    for metric,value in [('Mind',88),('Loyalty',75),('Pattern',82),('Body',22),('Ambition',28),('Self-start',18)]:
        add('sheet_'+metric,'Assessment','Self Concept','character_sheet',f'{metric}: {value} in the character sheet',{'metric':metric,'value':value,'scale_min':None,'scale_max':None,'interpretation':'personal character-sheet score; no standardized units'},'S08',framework='sheet',numeric=value,unit='character-sheet score',modality='personal framework, not clinical or standardized measurement')
    for key,label,trigger,effect in [
        ('friction','Friction Ignition','rival is in motion','activates only under this condition'),
        ('loyalty','Loyalty Sustain','actions tied to people or loss-risk','sustains only these actions'),
        ('armor','Aesthetic Armor','vulnerabilities','converts vulnerabilities into character traits preemptively'),
        ('clock','Deficit Clock','present experience','felt as compound loss from past')]:
        add('mechanic_'+key,'Mechanism','Self Concept','character_mechanics',label,{'name':label,'described_trigger':trigger,'described_effect':effect,'executable_agent_instruction':False},'S09',framework='mechanics',modality='metaphorical personal mechanism, not an agent action policy')
    add('narrative','Assessment','Self Concept','narrative','Narrative self model',{'wound':'Orphan','archetype':'Sage','flaw':'understanding replaces output','journey_role':'Threshold Guardian in his own story','mythic_figure':'Hamlet'},'S10',framework='narrative',modality='metaphorical self description; no biographical orphanhood asserted')
    add('bottom_up','Assessment','Self Concept','self_description','Bottom-up thinker',{'thinking_style':'bottom-up','learning_order':'concrete examples before abstraction'},'S11',modality='reported cognitive preference')
    add('debug_stall','Assessment','Self Concept','self_description','Stalls without a debugging fallback',{'condition':'unresolvable walls without a debugging fallback','effect':'stalls'},'S12',modality='reported behavior pattern')
    add('intrinsic','Assessment','Self Concept','values','Motivated by ownership and understanding',{'motivators':['ownership','understanding']},'S13',modality='reported motivation')
    add('roi_interpretation','Assessment','Self Concept','self_description','ROI stance attributed to fear of irrelevance',{'stance':'no depth without ROI','attributed_explanation':'fear of irrelevance rather than genuine preference','truth_status':'attributed interpretation, not an established causal diagnosis'},['P07','S14'],modality='interpretation in supplied digest')
    assert set(source_map)==set(s for r in records for s in r['sources'])
    assert all(contexts[r['context']]['domain']==r['domain'] for r in records)
    assert set(by_key['address']['sources'])=={'C02','P01'}
    assert len(by_key['assistant_persona']['sources'])==2
    model=dict(entities=list(entities.values()),contexts=list(contexts.values()),records=records,sources=sources,
               meta=dict(owner='north',source_updated='2026-08-21',effective_dates='unknown',snapshot_age='not refreshed for October',
                         extraction='hand-reviewed interpretation of supplied data; no model extraction',
                         policy_scope='Data records for an agent integration; not instructions applied to this conversation',
                         source_origin='supplied memory digest, not independently verified first-party evidence',evidence_group_count=1))
    return model


def matches(trigger,context):
    if trigger.get('always'):return True
    if 'all' in trigger:return all(matches(t,context) for t in trigger['all'])
    if 'any' in trigger:return any(matches(t,context) for t in trigger['any'])
    return trigger['field'] in context and context[trigger['field']]==trigger['eq']


def applicable_policies(model,context):
    return [r for r in model['records'] if r['kind']=='Policy' and matches(r['payload']['trigger'],context)]


def flatten(value,path=''):
    if isinstance(value,dict):
        for key,child in value.items():
            yield from flatten(child,(path+'.'+key).strip('.'))
    elif isinstance(value,list):
        for index,child in enumerate(value):yield from flatten(child,path+f'[{index}]')
    elif value is not None:
        yield path,str(value)


def v1_claims(model):
    """Apply the previous entity/claim/source pattern using literal-as-entity leaves.

    Original quotes and context are kept. Policy operators and units are not typed.
    This tests the minimal prototype, not every possible claim-graph implementation.
    """
    claims=[];values={}
    for r in model['records']:
        for path,value in flatten(r['payload']):
            oid='value_'+hashlib.sha256((path+':'+value).encode()).hexdigest()[:16]
            values.setdefault(oid,dict(id=oid,name=value,kind='Literal represented as entity'))
            for source in r['sources']:
                claims.append(dict(id='A'+str(len(claims)+1).zfill(4),subject=r['subject'],predicate=path,object=oid,
                                   context=r['context'],source=source,record_key=r['key'],record_id=r['id']))
    # Preserve actual entity-role and framework links in the baseline too.
    # These links do not add the typed metric/value or policy-expression binding.
    for r in model['records']:
        references=dict(r['refs'])
        if r['framework']:references['framework']=r['framework']
        for role,eid in references.items():
            for source in r['sources']:
                claims.append(dict(id='A'+str(len(claims)+1).zfill(4),subject=r['subject'],predicate='references.'+role,
                                   object=eid,context=r['context'],source=source,record_key=r['key'],record_id=r['id']))
    return claims,list(values.values())


if __name__=='__main__':
    model=build_model()
    (OUT/'model.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    claims,values=v1_claims(model)
    print(json.dumps(dict(source_bullets=len(model['sources']),typed_records=len(model['records']),entities=len(model['entities']),contexts=len(model['contexts']),v1_claims=len(claims),v1_value_entities=len(values)),indent=2))
