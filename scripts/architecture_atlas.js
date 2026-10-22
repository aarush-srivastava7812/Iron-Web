(() => {
  'use strict';
  const data = JSON.parse(document.querySelector('#atlas-data').textContent);
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const safe = (s) => String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = (n) => Number(n).toLocaleString('en-US');
  let selected = 'orchestrator';
  let filter = 'all';
  let activeTool = 'search';
  const positions = (a) => ({x: 12 + a.x * 0.76, y: 8 + a.y * 0.84});

  $('#agent-nodes').style.display = 'contents';
  for (const a of data.agents) {
    const {x, y} = positions(a);
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    for (const [key, value] of Object.entries({x1:500, y1:480, x2:x*10, y2:y*10, class:'agent-edge '+a.connection, 'data-agent-edge':a.id})) line.setAttribute(key,value);
    $('#agent-lines').append(line);
    const button = document.createElement('button');
    button.className = 'agent-node ' + a.connection;
    button.dataset.agent = a.id;
    button.style.left = x + '%'; button.style.top = y + '%';
    button.setAttribute('aria-pressed','false');
    button.innerHTML = '<b>'+safe(a.name)+'</b><small>'+safe(a.topic)+'</small><span class="agent-mark">'+(a.connection==='direct'?'TinyFish direct':'Shared evidence')+'</span>';
    button.addEventListener('click',()=>selectAgent(a.id,true));
    button.addEventListener('keydown',(event)=>{
      if (!['ArrowRight','ArrowLeft','ArrowDown','ArrowUp'].includes(event.key)) return;
      event.preventDefault();
      const buttons = $$('.agent-node').filter(b=>!b.hidden);
      const step = ['ArrowRight','ArrowDown'].includes(event.key)?1:-1;
      const next = buttons[(buttons.indexOf(button)+step+buttons.length)%buttons.length];
      next.focus(); next.click();
    });
    $('#agent-nodes').append(button);
  }
  function selectAgent(id, updateHash=false) {
    const agent = data.agents.find(a=>a.id===id) || data.agents[0];
    selected = agent.id;
    $$('.agent-node').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.agent===selected)));
    $$('[data-agent-edge]').forEach(line=>line.classList.toggle('active',line.dataset.agentEdge===selected));
    $('#agent-name').textContent=agent.name;
    $('#agent-code').textContent=agent.code;
    $('#agent-role').textContent=agent.role;
    $('#agent-actual').textContent=agent.actual;
    $('#agent-recommendation').textContent=agent.recommendation;
    $('#agent-value').textContent='Recommended value: '+agent.value;
    $('#agent-status').className='status '+agent.connection;
    $('#agent-status').textContent=agent.connection==='direct'?'Direct research adapter':'Via shared evidence / coordination';
    describeToolConnection();
    if(updateHash) history.replaceState(null,'','#agents/'+selected);
  }
  function setFilter(value) {
    filter=value;
    $$('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===value)));
    for(const a of data.agents) {
      const hidden=value!=='all' && a.connection!==value;
      $('[data-agent="'+a.id+'"]').hidden=hidden;
      $('[data-agent-edge="'+a.id+'"]').style.display=hidden?'none':'';
    }
    if($('[data-agent="'+selected+'"]').hidden)selectAgent(data.agents.find(a=>value==='all'||a.connection===value).id,true);
  }
  $$('[data-filter]').forEach(b=>b.addEventListener('click',()=>setFilter(b.dataset.filter)));

  function describeToolConnection() {
    const agent=data.agents.find(a=>a.id===selected);
    const tool=data.tools[activeTool];
    $('#agent-tool-label').textContent=tool.name+' connection';
    let detail;
    if(agent.connection==='shared') detail='No direct '+tool.name+' call from this role. It coordinates research or consumes shared eligible evidence.';
    else if(activeTool==='agent') detail='Available through an explicitly supplied TinyFishClient; not the default runtime client. URL + read-only goal → async run → poll → validated structured result.';
    else if(tool.roles.includes(agent.id)) detail=activeTool==='search'?'This role sends a public destination and topic to Search and receives source URLs.':'This role can send selected URLs to Fetch when the configured extraction reader is available. Fetched text is checked locally.';
    else detail='Explorer normally returns Search discovery leads without the venue Fetch step. The separate destination-memory refresh service can still fetch relevant public pages.';
    $('#agent-tool-detail').textContent=detail;
  }
  function setTool(id) {
    if(!data.tools[id])return;
    activeTool=id;
    const tool=data.tools[id];
    $$('[data-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tool===id)));
    $$('[data-tool-card]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.toolCard===id)));
    for(const agent of data.agents) {
      const edge=$('[data-agent-edge="'+agent.id+'"]');
      edge.classList.toggle('optional',id==='agent'&&agent.connection==='direct');
      edge.classList.toggle('inactive',id==='fetch'&&agent.connection==='direct'&&!tool.roles.includes(agent.id));
    }
    $('#hub-tool-status').textContent=tool.status;
    $('#map-tool-caption').textContent=id==='agent'?'Amber dashed paths: optional Agent client for four research roles; not enabled by the default client. Shared-evidence links remain blue.':id==='fetch'?'Fetch: selected URLs → public page text → local extraction/checks. Three venue roles use this conditional step; destination-memory refresh also uses Fetch.':'Search: four research roles → public destination/topic query → source URLs. Blue dashed links coordinate or consume shared evidence.';
    $('#tool-name').textContent='TinyFish '+tool.name;
    $('#tool-status').textContent=tool.status;
    $('#tool-status').className='pill '+(id==='agent'?'amber':'green');
    for(const key of ['endpoint','request','response','implementation','next']) $('#tool-'+key).textContent=tool[key];
    describeToolConnection();
  }
  $('#tool-cards').innerHTML=Object.entries(data.tools).map(([id,tool])=>'<button class="tool-card" data-tool-card="'+id+'" aria-pressed="false"><span class="pill '+(id==='agent'?'amber':'green')+'">'+safe(tool.status)+'</span><b>'+safe(tool.name)+'</b><p>'+safe(tool.request)+'</p><small>Returns: '+safe(tool.response)+'</small></button>').join('');
  $$('[data-tool]').forEach(b=>b.addEventListener('click',()=>setTool(b.dataset.tool)));
  $$('[data-tool-card]').forEach(b=>b.addEventListener('click',()=>setTool(b.dataset.toolCard)));
  setTool(activeTool);

  const providers=data.published.rows;
  const tiny=providers.find(r=>r.provider==='TinyFish');
  function chart(selector, rows, field, format) {
    const max=Math.max(...rows.map(r=>r[field]));
    $(selector).innerHTML=rows.map(r=>'<div class="chart-row '+(r.provider==='TinyFish'?'highlight':'')+'"><span>'+safe(r.provider)+'</span><div class="track" aria-hidden="true"><div class="bar" style="width:'+(100*r[field]/max).toFixed(3)+'%"></div></div><b>'+safe(format(r[field]))+'</b></div>').join('');
  }
  chart('#token-chart',providers,'tokens',number);
  chart('#latency-chart',providers,'task_s',v=>v+' s');
  chart('#vendor-chart',data.published.vendor_search_latency.rows,'ms',v=>number(v)+' ms');
  $('#comparison-rows').innerHTML=providers.map(r=>'<tr class="'+(r.provider==='TinyFish'?'highlight':'')+'"><th scope="row">'+safe(r.provider)+'<div class="note">'+safe(r.configuration)+'</div></th><td>'+r.completion.toFixed(1)+'% ± '+r.completion_sd.toFixed(1)+'</td><td>'+r.task_s+' s</td><td>'+r.avg_search_s.toFixed(3)+' s</td><td>'+number(r.tokens)+'</td></tr>').join('');
  $('#comparator').innerHTML=providers.filter(r=>r!==tiny).map(r=>'<option>'+safe(r.provider)+'</option>').join('');
  function insight() {
    const other=providers.find(r=>r.provider===$('#comparator').value);
    const tokens=100*(1-tiny.tokens/other.tokens);
    const latency=100*(tiny.task_s/other.task_s-1);
    const completion=tiny.completion-other.completion;
    $('#comparison-insight').innerHTML='<strong>'+Math.abs(tokens).toFixed(1)+'% '+(tokens>=0?'fewer':'more')+' LLM tokens</strong> than '+safe(other.provider)+' on this board. TinyFish’s median task time is <b>'+Math.abs(latency).toFixed(1)+'% '+(latency>0?'longer':'shorter')+'</b>; completion differs by <b>'+(completion>=0?'+':'')+completion.toFixed(1)+' percentage points</b>. Derived from the published table; no travel-system speedup is implied.';
  }
  $('#comparator').addEventListener('change',insight); insight();
  $('#download-data').addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(data.published,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='published-tinyfish-comparison-20261022.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });

  const guard=data.lifecycle;
  const cards=[
    [guard.repeated_requests.reduction_percent+'%','Fewer repeated HTTP requests','Controlled · mock transport','20 → 2 requests; 10 identical lookups'],
    [guard.stale_exclusion.passed+'/'+guard.stale_exclusion.cases,'Stale cases excluded','Controlled · seeded challenge','Freshness guard, not factual accuracy'],
    [guard.unsupported_quote_rejection.passed+'/'+guard.unsupported_quote_rejection.cases,'Unsupported quotes rejected','Controlled · exact quote gate','Changed-plan flags: '+guard.changed_plan_detection.passed+'/'+guard.changed_plan_detection.cases],
    [data.site.passed+'/'+data.site.checks.length,'Voyara + dashboard checks','Actual localhost browser test',data.site.browser_errors.length+' browser runtime errors'],
  ];
  $('#local-probes').innerHTML=cards.map(([value,label,kind,note])=>'<article class="probe"><span class="pill">'+safe(kind)+'</span><strong>'+safe(value)+'</strong><h3>'+safe(label)+'</h3><small>'+safe(note)+'</small></article>').join('');
  const t=data.site.timings;
  const stages=[
    [Math.round(t.chat_median_ms)+' ms','Draft-chat response','Median, 5 local turns'],
    [t.trip_create_ms.toFixed(1)+' ms','Seeded itinerary API','3-day dated plan + estimate'],
    [(data.live.elapsed_ms/1000).toFixed(2)+' s','TinyFish Search + Fetch','1 query · '+data.live.sources+' sources · '+data.live.fetched_pages+' pages'],
    [Math.round(t.dashboard_snapshot_median_ms)+' ms','Live dashboard feed','Median, 3 authenticated samples'],
  ];
  $('#stage-timings').innerHTML=stages.map(([value,label,note])=>'<div class="stage"><strong>'+safe(value)+'</strong><span>'+safe(label)+'</span><small>'+safe(note)+'</small></div>').join('');
  $('#memory-rows').innerHTML=data.memory.datasets.map(d=>'<tr><th scope="row">'+safe({locomo:'LoCoMo',dmr:'DMR / MSC',longmemeval:'LongMemEval'}[d.benchmark])+'<div class="note">'+d.questions+' queries · '+d.documents+' sessions</div></th><td>'+(100*d.lexical.recall_at_5).toFixed(1)+'%</td><td><div class="bar-memory"><div class="track" aria-hidden="true"><div class="bar" style="width:'+(100*d.native.recall_at_5).toFixed(2)+'%"></div></div><b>'+(100*d.native.recall_at_5).toFixed(1)+'%</b></div></td><td>'+Math.round(d.native.median_ms)+' ms</td></tr>').join('');

  function selectMemoryStep(id,updateHash=false) {
    const step=data.memory_steps.find(s=>s.id===id)||data.memory_steps[0];
    $$('[data-memory-step]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.memoryStep===step.id)));
    $('#memory-step-title').textContent=step.title;
    $('#memory-step-function').textContent=step.function;
    $('#memory-step-detail').textContent=step.detail;
    $('#memory-step-output').textContent='Handoff: '+step.output;
    $('#memory-step-source').href=step.file;
    if(updateHash)history.replaceState(null,'','#memory/'+step.id);
  }
  $('#memory-steps').innerHTML=data.memory_steps.map(step=>'<button data-memory-step="'+step.id+'" aria-pressed="false">'+safe(step.label)+'</button>').join('');
  $$('[data-memory-step]').forEach(b=>b.addEventListener('click',()=>selectMemoryStep(b.dataset.memoryStep,true)));
  const scenarios={
    fresh:['Reuse the eligible version','Latest owner-scoped SQL version → freshness/conflict gate → optional vector ranking → external_evidence[].','Recall does not enqueue a new refresh for this eligible topic. Research specialists may still run their own separate discovery tasks.','evidence_reused'],
    stale:['Withhold expired evidence; queue refresh','Expired SQL version → stale_topics → background Search/Fetch job → new checked version after completion.','Recall returns immediately with usable evidence and refresh status. Stale history is preserved, but it is not current external context.','stale_excluded · refresh_requested'],
    changed:['Preserve history; flag the affected plan','Changed high-impact quotation → new SQL version with previous_id → invalidate_trips() → evidence_review_required.','The saved plan needs review. This flag does not silently edit activities, change confirmed preferences or create a reservation.','evidence_versioned · plan_flagged'],
    outage:['Keep SQL evidence available','Graph unavailable → exact eligible SQL evidence still returned; optional vector ranking is skipped.','New graph writes can remain pending. sync_graph retries on a later recall; the committed source history is retained.','graph_status: pending; retry on recall'],
  };
  function selectMemoryScenario(id,updateHash=false) {
    const key=scenarios[id]?id:'fresh';
    const [title,flow,note,event]=scenarios[key];
    $$('[data-memory-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.memoryScenario===key)));
    $('#memory-scenario').innerHTML='<b>'+safe(title)+'</b><p>'+safe(flow)+'</p><p>'+safe(note)+'</p><code>'+safe(event)+'</code>';
    if(updateHash)history.replaceState(null,'','#memory/'+key);
  }
  $$('[data-memory-scenario]').forEach(b=>b.addEventListener('click',()=>selectMemoryScenario(b.dataset.memoryScenario,true)));
  selectMemoryStep('research');selectMemoryScenario('fresh');

  function route(focus=false) {
    const [requested,agent]=location.hash.slice(1).split('/');
    const id=['overview','agents','memory','tools','comparison','measurements','sources'].includes(requested)?requested:'overview';
    $$('.view').forEach(section=>section.hidden=section.id!==id);
    $$('nav [data-view]').forEach(b=>{if(b.dataset.view===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    if(id==='agents' && agent && data.agents.some(a=>a.id===agent)) {
      const a=data.agents.find(a=>a.id===agent);
      if(filter!=='all'&&a.connection!==filter)setFilter('all');
      selectAgent(agent);
    }
    if(id==='tools'&&data.tools[agent])setTool(agent);
    if(id==='memory'&&data.memory_steps.some(s=>s.id===agent))selectMemoryStep(agent);
    if(id==='memory'&&scenarios[agent])selectMemoryScenario(agent);
    document.title='Voyara · '+({overview:'Architecture overview',agents:'Agent map',memory:'TinyFish memory integration',tools:'Search, Fetch and Agent wiring',comparison:'Provider comparisons',measurements:'Our benchmarks',sources:'Sources'}[id]);
    if(focus){const heading=$('#title-'+id);heading.tabIndex=-1;heading.focus({preventScroll:true});window.scrollTo(0,0);}
  }
  $$('nav [data-view]').forEach(b=>b.addEventListener('click',()=>{location.hash=b.dataset.view;route(true);}));
  window.addEventListener('hashchange',()=>route());
  selectAgent(selected); route();
})();
