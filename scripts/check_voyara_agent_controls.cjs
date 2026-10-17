const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {randomBytes}=require('node:crypto');
(async()=>{
  const origin='http://127.0.0.1:8088',report=path.resolve('report/control_stress_20261017/agents');
  await fs.mkdir(report,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  page.setDefaultTimeout(15000);const checks=[],errors=[];let token;
  page.on('pageerror',e=>errors.push(e.message));
  async function save(){await fs.writeFile(path.join(report,'checks.json'),JSON.stringify({checks,errors,scope:'Isolated test account, real memory/agent backend'},null,2));}
  async function check(name,fn){try{const detail=await fn();checks.push({name,status:'passed',detail});}catch(e){checks.push({name,status:'failed',error:e.message});await page.screenshot({path:path.join(report,'failure-'+checks.length+'.png'),fullPage:true}).catch(()=>{});}await save();console.log(checks.at(-1).status.toUpperCase()+': '+name);}
  async function api(route,method='GET',data){const r=await context.request.fetch(origin+'/api'+route,{method,data,headers:{Authorization:'Bearer '+token},timeout:180000});assert.ok(r.ok(),route+' '+r.status());return r.status()===204?null:r.json();}
  async function goto(route){if(page.url()===origin+'/#'+route)await page.reload();else await page.goto(origin+'/#'+route);await page.locator('main h1,main h2').first().waitFor();}
  async function message(click){const response=page.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST',{timeout:180000});await click();const r=await response;assert.equal(r.status(),200);const data=await r.json();assert.equal(data.connection_status,'agents_connected');assert.ok(data.reply.content.length);await page.waitForFunction(()=>!document.querySelector('#conciergeForm button')?.disabled);return data;}
  try{
    const name='agents_'+Date.now(),reg=await context.request.post(origin+'/api/auth/register',{data:{email:name+'@example.com',username:name,password:randomBytes(24).toString('hex'),full_name:'Agent Control Tester'}});assert.equal(reg.status(),201);token=(await reg.json()).access_token;
    await context.addCookies([{name:'voyara_session',value:token,url:origin,httpOnly:true,sameSite:'Lax'},{name:'voyara_csrf',value:randomBytes(24).toString('hex'),url:origin,sameSite:'Lax'}]);
    for(const route of ['packages','tours','hotels','destination/Darjeeling','package/Kashmir','planner','flights','about','contact','booking?place=Kashmir','dashboard'])await check('All concierge suggestions and Send: '+route,async()=>{
      await goto(route);const suggestions=page.locator('.concierge-suggestions button');assert.equal(await suggestions.count(),3);
      for(let i=0;i<3;i++)await message(()=>suggestions.nth(i).click());
      await page.locator('#conciergePrompt').fill('What can you help me plan?');await message(()=>page.locator('#conciergeForm button').click());
      assert.equal(await page.locator('.concierge-message a[href="#planner"]').count(),1,'Show one follow-up link after repeated replies');
      return {real_agent_requests:4};
    });
    await check('Concierge failure keeps draft and permits retry',async()=>{
      await goto('planner');await page.route('**/api/assistant/conversations/*/messages',route=>route.fulfill({status:503,json:{detail:'Temporary chat outage (test)'}}),{times:1});await page.locator('#conciergePrompt').fill('Recommend destinations');await page.locator('#conciergeForm button').click();await page.locator('#conciergeReply').filter({hasText:'Temporary chat outage'}).waitFor();assert.equal(await page.locator('#conciergePrompt').inputValue(),'Recommend destinations');assert.equal(await page.locator('#conciergeForm button').isEnabled(),true);await message(()=>page.locator('#conciergeForm button').click());
    });
    await check('Start a new conversation preserves the previous one',async()=>{
      const before=await api('/assistant/conversations');await goto('planner');await page.getByRole('button',{name:'Start a new trip conversation'}).click();await page.locator('#conciergePrompt').fill('Recommend destinations');const result=await message(()=>page.locator('#conciergeForm button').click());assert.ok(before.every(c=>c.id!==result.message.conversation_id));assert.equal((await api('/assistant/conversations')).length,before.length+1);
    });
    await check('Planner repeated submissions create one itinerary',async()=>{
      await goto('planner');const f=page.locator('#plannerForm'),date=new Date(Date.now()+50*86400000).toISOString().slice(0,10);await f.locator('[name=date]').fill(date);await f.locator('[name=budget]').fill('90000');await f.locator('[name=duration]').selectOption('3');await f.locator('[name=interests][value=Food]').check();
      const before=(await api('/itineraries')).length;let messages=0;const listener=r=>{if(r.url().endsWith('/messages')&&r.method()==='POST')messages++;};page.on('request',listener);await f.evaluate(el=>{for(let i=0;i<5;i++)el.requestSubmit();});await page.locator('#savePlanStatus').filter({hasText:'Itinerary saved to My Trips.'}).waitFor({timeout:240000});page.off('request',listener);assert.equal(messages,1);assert.equal((await api('/itineraries')).length,before+1);
      await page.getByRole('link',{name:'View conversation & memory',exact:true}).click();await page.locator('#tripChat').waitFor({timeout:180000});
    });
    await check('Trip chat, saved memory panels and reload',async()=>{
      const f=page.locator('#tripChat');assert.equal(await f.evaluate(el=>el.checkValidity()),false);await f.locator('[name=content]').fill('Lower my budget to INR 80000');const response=page.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST',{timeout:180000});await f.locator('[type=submit]').click();const result=await (await response).json();assert.equal(result.orchestration.trip_brief.budget_total_inr,80000);await page.locator('.memory-detail').filter({hasText:'80,000'}).waitFor({timeout:180000});await page.reload();await page.locator('#tripChat').waitFor({timeout:180000});assert.ok(await page.locator('.chat-record').count()>=4);assert.ok(await page.locator('[data-action=forget-event]').count());
      for(const summary of await page.locator('main details summary').all()){await summary.click();assert.equal(await summary.evaluate(el=>el.parentElement.open),true);await summary.press('Enter');assert.equal(await summary.evaluate(el=>el.parentElement.open),false);}
      for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(report,'trip-'+width+'.png'),fullPage:true});}await page.setViewportSize({width:1440,height:1000});
    });
    await check('Trip chat failure and rapid retry',async()=>{
      const f=page.locator('#tripChat');await f.locator('[name=content]').fill('What is my budget?');await page.route('**/api/assistant/conversations/*/messages',route=>route.fulfill({status:503,json:{detail:'Temporary trip chat outage (test)'}}),{times:1});await f.locator('[type=submit]').click();await f.locator('.form-status').filter({hasText:'Temporary trip chat outage'}).waitFor();assert.equal(await f.locator('[name=content]').inputValue(),'What is my budget?');const before=await page.locator('.chat-record').count();const response=page.waitForResponse(r=>r.url().endsWith('/messages')&&r.request().method()==='POST',{timeout:180000});await f.evaluate(el=>{for(let i=0;i<5;i++)el.requestSubmit();});await response;await page.waitForFunction(n=>document.querySelectorAll('.chat-record').length===n+2,before,{timeout:180000});
    });
    await check('Login account links and sign out button',async()=>{await goto('login');await page.getByRole('link',{name:'My journeys',exact:false}).click();await page.locator('#profileForm').waitFor();await goto('login');await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/#home');});
    await check('Isolated trip cleanup',async()=>{for(const c of await api('/assistant/conversations'))await api('/assistant/conversations/'+c.id,'DELETE');for(const i of await api('/itineraries'))await api('/itineraries/'+i.id,'DELETE');});
    await check('No uncaught chat/browser errors',async()=>assert.deepEqual(errors,[]));
    await save();if(checks.some(c=>c.status==='failed'))process.exitCode=1;
  }finally{await save();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
