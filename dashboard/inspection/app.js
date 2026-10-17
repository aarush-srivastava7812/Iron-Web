const $ = id => document.getElementById(id);
let base = window.DASHBOARD_API_URL || localStorage.getItem('memory-dashboard-backend') || '';
let stream = null, paused = false, generation = 0;
let graphOffset = null, claimsOffset = null, vectorCursor = null;
let graphPaged=false, claimsPaged=false, vectorsPaged=false;
$('backend').value = base;
const render = (id, value) => { $(id).textContent = JSON.stringify(value, null, 2); };
const fail = message => { $('status').textContent = 'Feed unavailable â€” displayed data may be stale.'; $('error').textContent = message; };
function normalize(value) {
  if (!value.trim()) return '';
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || !['', '/'].includes(url.pathname)) throw new Error('Enter an HTTP(S) backend origin without credentials, path, or query.');
  return url.origin;
}
async function api(path) {
  const response = await fetch(base + '/api/dashboard/' + path, {cache:'no-store', signal:AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'Memory feed unavailable');
  return data;
}
function renderMetrics(data) {
  $('summary').replaceChildren();
  for (const [label, value] of [['Registered agents', data.agents.registered], ['Agents observed', data.agents.observed], ['Reading memory now', data.agents.reading_memory], ['Vector memories', data.storage.memories], ['Graph nodes', Object.values(data.storage.nodes).reduce((a,b)=>a+b,0)], ['Graph edges', Object.values(data.storage.edges).reduce((a,b)=>a+b,0)]]) {
    const block=document.createElement('div'), number=document.createElement('strong'), text=document.createElement('span');
    number.textContent=String(value); text.textContent=label; block.append(number,text); $('summary').append(block);
  }
}
function accept(data) {
  if (data.status !== 'online') { fail(data.message || 'Memory is not ready'); return; }
  $('error').textContent='';
  $('status').textContent = paused ? 'Snapshot loaded â€” live updates paused.' : 'Connected â€” memory snapshot refreshed every 2 seconds.';
  $('updated').textContent='Updated '+new Date(data.timestamp*1000).toLocaleTimeString();
  $('scope').textContent='Scope: '+data.scope+(data.trip_id ? ' / '+data.trip_id : '')+'. Counts cover the monitored travelerâ€™s store.';
  renderMetrics(data);
  render('agents',data.agents); render('tiers',data.tiers); render('credentials',data.credentials);
  render('events',{...data.observations, contexts:undefined, receipts:data.receipts});
  render('overview',{databases:data.databases,storage:data.storage,models:data.models,cache:data.cache,notes:data.notes});
  $('accounting').textContent=data.tiers.accounting+'. Captured contexts are actual agent reads.';
  if (!graphPaged) { render('graph',data.graph); $('more-graph').disabled=data.graph.next_offset===null; }
  if (!claimsPaged) { render('shared-memory',data.shared_memory); $('more-claims').disabled=data.shared_memory.next_offset===null; }
  if (!vectorsPaged && !$('vector-values').checked) { render('vectors',data.vectors); $('more-vectors').disabled=data.vectors.next_cursor===null; }
  window.latestSnapshot=data;
}
function connect() {
  stream?.close(); stream=null; generation++;
  graphOffset=claimsOffset=vectorCursor=null; graphPaged=claimsPaged=vectorsPaged=false;
  $('api-docs').href=base+'/docs';
  if(paused) return;
  $('status').textContent='Connecting to the memory feedâ€¦';
  const current=generation;
  stream=new EventSource(base+'/api/dashboard/stream');
  stream.addEventListener('snapshot',event=>{if(current===generation) { try{accept(JSON.parse(event.data));}catch{fail('Invalid memory snapshot received.');} }});
  stream.addEventListener('feed_error',event=>{if(current===generation) fail(JSON.parse(event.data).message);});
  stream.onerror=()=>{if(current===generation) fail('Connection lost. The live stream will reconnect automatically.');};
}
$('connection').addEventListener('submit',event=>{event.preventDefault();try{base=normalize($('backend').value);localStorage.setItem('memory-dashboard-backend',base);connect();}catch(error){fail(error.message);}});
$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'Resume live updates':'Pause live updates';if(paused){stream?.close();generation++;$('status').textContent='Live updates paused. Displayed values are a snapshot.';}else connect();};
$('refresh').onclick=async()=>{try{graphOffset=claimsOffset=vectorCursor=null; graphPaged=claimsPaged=vectorsPaged=false;accept(await api('snapshot'));}catch(error){fail(error.message);}};
async function loadPage(kind, next=false) {
  const button=$(kind==='vectors'?'more-vectors':kind==='graph'?'more-graph':'more-claims');button.disabled=true;
  try {
    let query='';
    if(kind==='vectors') {const after=next?(vectorCursor || window.latestSnapshot?.vectors.next_cursor):null;query='?include_values='+$('vector-values').checked+(after?'&after='+encodeURIComponent(after):'');}
    else {const previous=kind==='graph'?graphOffset:claimsOffset;query='?offset='+(next?(previous || (kind==='graph'?window.latestSnapshot?.graph.next_offset:window.latestSnapshot?.shared_memory.next_offset) || 0):0);}
    const data=await api(kind+query);render(kind,data);
    if(kind==='vectors'){vectorsPaged=true;vectorCursor=data.next_cursor;button.disabled=data.next_cursor===null;}
    else {if(kind==='graph'){graphPaged=true;graphOffset=data.next_offset;}else{claimsPaged=true;claimsOffset=data.next_offset;}button.disabled=data.next_offset===null;}
  }catch(error){fail(error.message);button.disabled=false;}
}
$('more-graph').onclick=()=>loadPage('graph',true);
$('more-claims').onclick=()=>loadPage('shared-memory',true);
$('more-vectors').onclick=()=>loadPage('vectors',true);
$('vector-values').onchange=()=>loadPage('vectors');
try {base=normalize(base);connect();}catch(error){fail(error.message);}
