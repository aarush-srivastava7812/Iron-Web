"""Field-aware interpretation of the later random test dataset."""
import json
import re
from pathlib import Path
from datetime import date
from fuzzy import score,relationship

OUT=Path(__file__).resolve().parent
PREVIOUS=OUT.parent/'north_graph'
CLIENT_DATE=date(2026,10,13)
OLD_AGE=(CLIENT_DATE-date(2026,8,21)).days


def read_new_sources():
    raw=(OUT/'new_data.md').read_text(encoding='utf-8');sources=[]
    for index,match in enumerate(re.finditer(r'^### ([^\n]+)\n(?:\n)?([^#]*?)(?=^### |\Z)',raw,re.M),1):
        content=match.group(2).strip()
        if not content:continue
        start=match.start(2)+len(match.group(2))-len(match.group(2).lstrip())
        sources.append(dict(id=f'B2_{index}',section=match.group(1),text=content,updated=None,batch=2,
                            origin='later user-supplied random test summary',evidence_group='random-test-batch-2',
                            span_start=start,span_end=start+len(content)))
    assert len(sources)==6
    assert all(raw[s['span_start']:s['span_end']]==s['text'] for s in sources)
    return raw,sources


def incoming():
    _,sources=read_new_sources();smap={s['section']:s['id'] for s in sources}
    entities=[
        ('platform','Industrial Knowledge Intelligence Platform','Project'),('tm2','TM2','Project'),('prefiq','PrefIQ','Project'),
        ('inditech_systems','Inditech Systems','OrganizationMention'),('pune','Pune','Place'),('india','India','Place'),
        ('fastapi','FastAPI','Technology'),('sqlite','SQLite','Technology'),('postgres','PostgreSQL','Technology'),
        ('sqlalchemy','SQLAlchemy','Technology'),('alembic','Alembic','Technology'),('qdrant','Qdrant','Technology'),
        ('pokemon','Pokémon','Franchise'),('pokemon_game','Local multiplayer Pokémon project','Project'),
        ('angela_course','100 Days of Code','Course'),('bitfumes_course','Bitfumes FastAPI course','Course'),
        ('internship','Completed IT-IoT internship','Episode'),('deberta','DeBERTa-v3','Model'),('mistral','Mistral','Model'),
    ]
    records=[]
    def add(key,title,section,kind,domain,context,payload,fields,subject='north',refs=None,modality='reported in later random test summary'):
        records.append(dict(id='N'+str(len(records)+1).zfill(3),key=key,title=title,kind=kind,domain=domain,
            context='ctx_'+domain.replace(' ','_')+'_'+context,subject=subject,refs=refs or {},payload=payload,
            sources=[smap[section]],source_updated=None,valid_from=None,valid_until=None,framework=None,
            numeric_value=None,unit=None,modality=modality,extraction='hand-reviewed typed interpretation; not model extraction',fields=fields,batch=2))
    def field(slot,value,scope,cardinality='single',historical=False,half_life=365,kind='literal'):
        return dict(slot=slot,value=value,scope=scope,cardinality=cardinality,historical=historical,half_life=half_life,value_kind=kind)
    add('later_identity','Name: Aarush Srivastava','Overview','Fact','Profile','identity',{'name':'Aarush Srivastava'},
        [field('identity.name','Aarush Srivastava','identity',half_life=3650)])
    add('later_study','AI & Data Science student in India','Overview','Fact','Profile','education',{'discipline':'AI & Data Science','study_country':'India'},
        [field('education.discipline','AI & Data Science','education'),field('education.country','india','education',kind='entity')],refs={'study_location':'india'})
    add('work_focus','Practical systems and technical focus','Overview','Preference','Profile','work_focus',
        {'focus':['practical software systems','backend engineering','machine learning','retrieval systems','product design']},
        [field('work.focus',x,'professional interests',cardinality='many') for x in ['practical software systems','backend engineering','machine learning','retrieval systems','product design']])
    add('overview_style','Direct analytical communication with minimal fluff','Overview','Policy','Preferences','response',
        {'trigger':{'always':True},'style':['direct','analytical'],'padding':'minimal'},
        [field('response.clarity','high','response',half_life=730),field('response.padding','minimal','response',half_life=730),
         field('response.style','analytical','response',cardinality='many',half_life=730)],subject='vel')
    add('solution_quality','Technically sound, realistic production-oriented solutions','Overview','Preference','Preferences','technical_solutions',
        {'qualities':['technically sound','production-oriented','realistic'],'avoid':'overhype'},
        [field('solution.quality',x,'technical solutions',cardinality='many',half_life=730) for x in ['technically sound','production-oriented','realistic']])
    add('later_tone','Concise, straightforward, practical responses','Communication Style','Policy','Preferences','response',
        {'trigger':{'always':True},'qualities':['concise','straightforward','forward-thinking','analytical','practical'],'padding':'minimal','enthusiasm':'not exaggerated'},
        [field('response.conciseness','high','response',half_life=730),field('response.clarity','high','response',half_life=730),
         field('response.padding','minimal','response',half_life=730),field('response.hype','none','response',half_life=730)]
        +[field('response.style',x,'response',cardinality='many',half_life=730) for x in ['forward-thinking','analytical','practical']],subject='vel')
    add('compact_documents','Compact document formatting','Communication Style','Policy','Preferences','documents',
        {'trigger':{'field':'task','eq':'document_generation'},'action':'compact formatting without excessive whitespace'},
        [field('document.formatting','compact without excessive whitespace','document generation',half_life=730)],subject='vel')
    add('synthetic_term','Use synthetic in selected appropriate documents','Communication Style','Policy','Preferences','documents',
        {'trigger':{'all':[{'field':'task','eq':'document_generation'},{'field':'selected_document_subset','eq':True},{'field':'terminology_replacement_appropriate','eq':True}]},
         'action':{'prefer':'synthetic','instead_of':['AI','LLM']},'scope_limit':'some documents, when appropriate'},
        [field('document.terminology','synthetic instead of AI/LLM','selected appropriate documents',half_life=730)],subject='vel')
    add('primary_platform','Primary long-term Industrial Knowledge Intelligence Platform','Technical Projects','Fact','Technical Projects','industrial_platform',
        {'relationship':'primary long-term project','domain_independent':True},
        [field('project.primary_long_term','platform','long-term project focus',kind='entity',half_life=180)],refs={'project':'platform'})
    add('platform_design','Parsing and retrieval, not a traditional chatbot','Technical Projects','Fact','Technical Projects','industrial_platform',
        {'basis':['document parsing','retrieval'],'interaction':'not a traditional chatbot','scope':'domain-independent industrial knowledge'},
        [field('project.design',{'basis':['document parsing','retrieval'],'interaction':'not a traditional chatbot'},'project:platform')],subject='platform')
    add('platform_goal','Production-ready system like an experienced technical engineer','Technical Projects','Goal','Technical Projects','industrial_platform',
        {'target':'production-ready','desired_behavior':'experienced technical engineer','achieved':None},
        [field('project.goal','production-ready experienced technical engineer behavior','project:platform')],subject='platform',modality='goal, not an assertion that production readiness is achieved')
    components=['generic document ingestion','normalization','classification','embeddings','vector search','retrieval','agent integrations']
    add('platform_architecture','Reported platform architecture','Technical Projects','Fact','Technical Projects','industrial_platform',{'components':components},
        [field('project.component',x,'project:platform',cardinality='many') for x in components],subject='platform')
    improvements=['parsing quality','hybrid retrieval','chunking strategies','clustering robustness','reranking confidence evaluation','pipeline reliability']
    add('platform_work','Work on parsing and retrieval reliability','Technical Projects','Activity','Technical Projects','industrial_platform',{'areas':improvements,'measured_gains':None},
        [field('project.improvement_work',improvements,'project:platform',historical=True,half_life=None)],subject='platform')
    add('tm2','TM2: AI-controlled focus system','Technical Projects','Fact','Technical Projects','related_projects',{'description':'AI-controlled focus system'},
        [field('project.description','AI-controlled focus system','project:tm2')],subject='tm2',refs={'builder':'north'})
    add('prefiq','PrefIQ: human preference prediction from paired responses','Technical Projects','Fact','Technical Projects','related_projects',{'task':'human preference prediction','input':'paired response comparisons'},
        [field('project.description',{'task':'human preference prediction','input':'paired response comparisons'},'project:prefiq')],subject='prefiq',refs={'builder':'north'})
    stack=['fastapi','sqlite','postgres','sqlalchemy','alembic','python']
    add('backend_stack','Primary Python backend stack','Development Environment','Fact','Development Environment','backend',{'stack':stack},
        [field('development.primary_stack',x,'development stack',cardinality='many',kind='entity',half_life=180) for x in stack],refs={f'technology_{i}':x for i,x in enumerate(stack)})
    hardware={'cpu':'AMD Ryzen 5 7845HS','gpu':'NVIDIA RTX 4050','vram':{'value':6,'unit':'GB'},'ram':{'value':40,'unit':'GB'},'storage':{'value':1,'unit':'TB'}}
    add('hardware','Reported laptop configuration','Development Environment','Fact','Development Environment','hardware',{'specification':hardware,'model_name_validation':'not performed'},
        [field('hardware.'+k,v,'laptop',half_life=180,kind='quantity' if isinstance(v,dict) else 'literal') for k,v in hardware.items()])
    exposure=['DeBERTa-v3','Mistral fine-tuning concepts','Qdrant','OCR pipelines','embedding models','document processing libraries']
    add('model_tool_exposure','Reported model and document-tool exposure','Development Environment','Activity','Development Environment','tools',{'exposure':exposure,'expertise_level':None},
        [field('experience.tool',x,'tool exposure',cardinality='many',historical=True,half_life=None) for x in exposure])
    add('study_again','Studying AI & Data Science','Learning and Coursework','Fact','Profile','education',{'discipline':'AI & Data Science'},
        [field('education.discipline','AI & Data Science','education')])
    add('angela_progress','100 Days of Code: through Day 32','Learning and Coursework','Result','Learning and Coursework','courses',
        {'course':'100 Days of Code','completed_through_day':32,'whole_course_completed':False},
        [field('course.completed_through_day',32,'course:angela_course',historical=True,half_life=None,kind='ordinal')],refs={'course':'angela_course'})
    add('fastapi_course','Completed Bitfumes FastAPI course','Learning and Coursework','Result','Learning and Coursework','courses',{'status':'completed'},
        [field('course.completion','completed','course:bitfumes_course',historical=True,half_life=None)],refs={'course':'bitfumes_course'})
    add('internship','Completed IT-IoT internship with Inditech Systems in Pune','Learning and Coursework','Activity','Learning and Coursework','internship',
        {'type':'IT-IoT','status':'completed','organization_mention':'Inditech Systems','city':'Pune','event_dates':None},
        [field('internship.organization','inditech_systems','episode:internship',historical=True,half_life=None,kind='entity'),
         field('internship.status','completed','episode:internship',historical=True,half_life=None),
         field('internship.location','pune','episode:internship',historical=True,half_life=None,kind='entity')],refs={'episode':'internship','organization_mention':'inditech_systems','location':'pune'})
    add('internship_exposure','Industrial systems and IoT elevator exposure','Learning and Coursework','Activity','Learning and Coursework','internship',
        {'exposure':['connected industrial systems','IoT-based elevator technology']},
        [field('internship.exposure',['connected industrial systems','IoT-based elevator technology'],'episode:internship',historical=True,half_life=None)],refs={'episode':'internship'})
    add('academic_application','Applying classroom concepts to real software','Learning and Coursework','Assessment','Learning and Coursework','application',
        {'pattern':'academic and project work overlap','emphasis':'apply classroom concepts to real software'},
        [field('learning.application','classroom concepts applied to real software','learning approach')])
    add('pokemon_interest','Enjoys Pokémon','Gaming Interests','Preference','Gaming Interests','pokemon',{'franchise':'Pokémon'},
        [field('interest.franchise','pokemon','gaming interests',cardinality='many',kind='entity',half_life=730)],refs={'franchise':'pokemon'})
    add('pokemon_design','Team building, battle mechanics, competitive design','Gaming Interests','Activity','Gaming Interests','pokemon',
        {'areas':['team building','battle mechanics','competitive design'],'avoids_reliance_on':'gimmicks such as Mega Evolution'},
        [field('gaming.design_approach','competitive core mechanics without relying on Mega Evolution','Pokemon design',half_life=730)])
    add('pokemon_project','Designing a local multiplayer Pokémon project','Gaming Interests','Activity','Gaming Interests','pokemon_project',{'status':'designing','mode':'local multiplayer'},
        [field('project.builds','pokemon_game','project activity',cardinality='many',kind='entity',half_life=180)],refs={'project':'pokemon_game'})
    features=['teams from latest Pokédex','abilities','natures','moves','turn-based battles']
    add('pokemon_features','Pokémon project feature goals','Gaming Interests','Goal','Gaming Interests','pokemon_project',{'features':features,'pokedex_version':None},
        [field('project.feature_goal',x,'project:pokemon_game',cardinality='many') for x in features],subject='pokemon_game')
    add('pokemon_improvements','Improve UI and battles, retain core Pokémon experience','Gaming Interests','Activity','Gaming Interests','pokemon_project',
        {'work':['UI','battle system'],'constraint':'faithful to core Pokémon experience','measured_results':None},
        [field('project.improvement_work',['UI','battle system'],'project:pokemon_game',historical=True,half_life=None),
         field('project.design_constraint','faithful to core Pokémon experience','project:pokemon_game')],subject='pokemon_game')
    return entities,records,sources


def old_fields(r):
    def f(slot,value,scope,card='single',half=365,historical=False,kind='literal'):
        return dict(slot=slot,value=value,scope=scope,cardinality=card,half_life=half,historical=historical,value_kind=kind)
    if r['key']=='education':return [f('education.degree','BTech','education'),f('education.year',3,'education',half=180,kind='ordinal'),f('education.discipline','AI & Data Science','education')]
    if r['key']=='identity':return [f('identity.name','Aarush Srivastava','identity',half=3650),f('identity.preferred_alias','North','identity',half=3650)]
    if r['key']=='address':return [f('response.preferred_address','North','response',half=730)]
    if r['key']=='employer':return [f('employment.organization','inditech','employment',card='many',half=180,kind='entity')]
    if r['key']=='gdpe_builder':return [f('project.builds','gdpe','project activity',card='many',half=180,kind='entity')]
    historical=r['kind'] in {'Result','Activity'}
    half=None if historical else (30 if r['kind']=='Priority' else 180 if r['kind']=='Issue' else 730)
    return [f('record.'+r['key'],r['payload'],r['context'],half=half,historical=historical,kind='structured')]


def make_facets(old,new):
    facets=[]
    for batch,records in ((1,old),(2,new)):
        for r in records:
            if batch==1 and r['key']=='tone':
                specs=[dict(slot=slot,value=value,scope='response',cardinality='single',half_life=730,historical=False,value_kind='literal') for slot,value in
                       [('response.clarity','high'),('response.conciseness','high'),('response.padding','minimal'),('response.hype','none')]]
                specs += [dict(slot='response.style',value=x,scope='response',cardinality='many',half_life=730,historical=False,value_kind='literal')
                          for x in ['human','emotionally present','grounded','steady']]
            else:specs=old_fields(r) if batch==1 else r['fields']
            for index,spec in enumerate(specs,1):
                facets.append(dict(id=f"F_{r['id']}_{index}",record_id=r['id'],subject=r['subject'],batch=batch,
                    sources=r['sources'],quality=.85,support=0.,conflict=0.,protected=False,status='active',base_score=.99,
                    age_base=OLD_AGE if batch==1 else 0,last_confirmation_batch=batch,**spec))
    matches=[]
    for new_f in [f for f in facets if f['batch']==2]:
        for old_f in [f for f in facets if f['batch']==1]:
            rel,reason=relationship(old_f,new_f)
            if rel=='CONFIRMS':
                matches.append(dict(source=new_f['id'],target=old_f['id'],type='CONFIRMS',reason=reason,origin='hand-normalized typed slot comparison',independence='same test-data author; not independent external verification'))
                old_f['support']=.35;old_f['age_base']=0;old_f['last_confirmation_batch']=2
    for f in facets:f['fuzzy']=score(quality=f['quality'],age_days=0 if f['historical'] else f['age_base'],half_life=f['half_life'],support=f['support'],conflict=f['conflict'],protected=f['protected'],status=f['status']);f['score']=f['fuzzy']['score']
    return facets,matches


def model():
    previous=json.loads((PREVIOUS/'graph.json').read_text(encoding='utf-8'))['v2']
    entities,new,sources=incoming();facets,matches=make_facets(previous['records'],new)
    return dict(old=previous,new_records=new,new_sources=sources,new_entities=[dict(id=id,name=name,kind=kind,namespace='random-test:north',aliases=[]) for id,name,kind in entities],facets=facets,relations=matches,
                identity=dict(mention='inditech_systems',canonical='inditech',before='unresolved name similarity',after='accepted user-confirmed alias',
                              evidence='yes the are same, but I want to see how your logic for KG would handle it.',
                              project_scope_note='User clarified that these are random test data, unrelated to the current project. GDPE/platform identity remains unspecified.'),
                hypotheses=[dict(id='H1',source='primary_platform',target='gdpe_builder',type='POSSIBLE_RELATION',status='unresolved',reason='Industrial retrieval focus overlaps; no evidence establishes same project, broader platform, or replacement.'),
                            dict(id='H2',source='prefiq',target='sih_problem',type='POSSIBLE_RELATION',status='unresolved',reason='Preference-prediction tasks overlap; names and project identity are not established as equal.')],
                meta=dict(previous_records=len(previous['records']),new_records=len(new),source_date=None,receipt_order='batch 2 is newer by user instruction; event dates remain unknown',old_snapshot_age_days=OLD_AGE,
                          actual_contradictions=0,actual_supersessions=0,interpretation='hand-reviewed typed fields; no model extraction or calibrated truth probabilities',dataset='random test data, not facts about user or repository'))


if __name__=='__main__':
    m=model();print(json.dumps(dict(old_records=len(m['old']['records']),new_records=len(m['new_records']),facets=len(m['facets']),confirmation_edges=len(m['relations'])),indent=2))
