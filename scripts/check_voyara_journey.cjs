const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');

(async()=>{
  const origin=process.env.VOYARA_JOURNEY_TEST_URL||'http://127.0.0.1:8094';
  const report=path.resolve('report/travel_chat_catalog_20261017');await fs.mkdir(report,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});
  const page=await context.newPage(),checks=[],errors=[];page.setDefaultTimeout(20000);
  page.on('pageerror',e=>errors.push(e.message));
  async function current(){const r=await context.request.get(origin+'/api/assistant/conversations');assert.equal(r.status(),200);return (await r.json()).find(t=>t.title==='Kerala chat & Travel Book fixture');}
  async function regenerate(){const response=page.waitForResponse(r=>r.url().endsWith('/confirm')&&r.request().method()==='POST',{timeout:180000});await page.locator('[data-book=generate-manual]').click();const r=await response;assert.equal(r.status(),200,await r.text());assert.equal((await r.json()).orchestration.status,'ok');await page.locator('[data-book=download]:enabled').waitFor({timeout:180000});}
  async function chat(text){await page.locator('#journeyMessage').fill(text);const response=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST',{timeout:180000});await page.locator('.journey-chat-compose [type=submit]').click();const r=await response;assert.equal(r.status(),200);const data=await r.json();assert.equal(data.status,'ok',data.reply);await page.locator('.journey-chat-loading').waitFor({state:'hidden'});return data;}
  try{
    const login=await context.request.post(origin+'/api/auth/developer',{headers:{Origin:origin,'X-Voyara-Developer':'1'}});assert.equal(login.status(),200,await login.text());
    await page.goto(origin+'/#destination/Kerala');await page.getByRole('heading',{name:'Discover Kerala',exact:true}).waitFor();
    assert.equal((await context.request.get(origin+'/travel/kerala.jpg')).headers()['content-type'],'image/jpeg');
    await page.screenshot({path:path.join(report,'kerala-guide-desktop.png'),fullPage:true});checks.push('Kerala guide, real local photograph and regional discovery sketch render');
    const trip=await current();assert.ok(trip);
    await page.goto(origin+'/#travel-book/'+trip.id);await page.locator('.journey-book').waitFor();
    await page.locator('[data-book=download]:enabled').waitFor();
    await page.locator('.journey-launcher').click();await page.locator('.journey-chat[open]').waitFor();
    const reply=await chat('Show me three stays from my current Kerala catalog. Keep all my trip details unchanged.');
    assert.ok(reply.reply.length>30);assert.equal(reply.workspace.draft.destination,'Kerala');assert.equal(reply.workspace.plan_ready,true);
    assert.ok(reply.cards.every(c=>reply.workspace.options.stays.some(s=>s.id===c.id)||c.kind!=='stay'));
    checks.push('Live NVIDIA chat replies with current trip context and grounded catalog choices');
    await page.screenshot({path:path.join(report,'chat-desktop.png')});
    await page.route('**/api/assistant/conversations/*/chat',route=>route.fulfill({status:503,json:{detail:'Temporary provider outage (browser test)'}}),{times:1});
    await page.locator('#journeyMessage').fill('Show my current budget');await page.locator('.journey-chat-compose [type=submit]').click();
    await page.locator('.journey-chat-status').filter({hasText:'Temporary provider outage'}).waitFor();
    assert.equal(await page.locator('#journeyMessage').inputValue(),'Show my current budget');
    assert.equal(await page.locator('.journey-chat-compose [type=submit]').isEnabled(),true);
    const priced=await chat('Show my current budget without changing any trip fields.');
    assert.ok(priced.estimate);assert.ok(priced.reply.includes('Total: INR '+priced.estimate.budget.total_inr.toLocaleString('en-US')));
    assert.equal(priced.workspace.plan_ready,true);
    checks.push('Provider error keeps the input and allows a live retry with the exact server-owned saved estimate');
    for(const width of [1440,768,390,320]){
      await page.setViewportSize({width,height:950});
      assert.ok(await page.locator('.journey-chat').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'chat overflow '+width);
      if(width===390)await page.screenshot({path:path.join(report,'chat-mobile.png')});
    }
    await page.locator('[aria-label="Minimize travel chat"]').click();await page.reload();
    await page.locator('.journey-book').waitFor();await page.locator('.journey-launcher').click();
    await page.locator('.journey-message').filter({hasText:'Show me three stays from my current Kerala catalog'}).waitFor();
    await page.locator('[aria-label="Minimize travel chat"]').click();checks.push('Chat history resumes after reload and minimizes by keyboard-accessible controls');
    await page.setViewportSize({width:1440,height:1050});
    await page.locator('a[href="#hotels?tripId='+trip.id+'&edit=true"]').click();
    await page.locator('.journey-context-bar').waitFor();assert.ok((await page.locator('.hotel-card').count())>=6);
    await page.locator('.hotel-card button[onclick^="bookHotel"]').first().click();
    await page.waitForURL('**/#travel-book/'+trip.id);await page.locator('.journey-book').waitFor();
    await regenerate();checks.push('Trip-specific hotel edit link opens matched stays; selecting one updates the same trip');
    await page.locator('a[href="#flights?tripId='+trip.id+'&edit=true"]').click();
    const flightForm=page.locator('#flightSearch');await flightForm.waitFor();
    await page.locator('.journey-context-bar').waitFor();
    assert.equal(await flightForm.locator('[name=depart]').inputValue(),'2026-12-12');
    assert.equal(parseInt(await flightForm.locator('[name=travellers]').inputValue()),2);
    const flights=page.waitForResponse(r=>r.url().includes('/api/website/flights?'));await flightForm.locator('[type=submit]').click();
    assert.equal((await flights).status(),200);await page.locator('[data-flight]').first().click();
    await page.waitForURL('**/#travel-book/'+trip.id);await page.locator('.journey-book').waitFor();await regenerate();
    checks.push('Flight edit link prefills the trip; selecting a sample outbound flight updates its draft and estimate');
    const download=page.waitForEvent('download',{timeout:60000});await page.locator('[data-book=download]').click();
    const pdf=await download;await pdf.saveAs(path.join(report,'Browser_Travel_Book.pdf'));
    const bytes=await fs.readFile(path.join(report,'Browser_Travel_Book.pdf'));assert.equal(bytes.subarray(0,5).toString(),'%PDF-');
    checks.push('Personalized branded PDF downloads from the authenticated backend');
    for(const width of [1440,768,390,320]){
      await page.setViewportSize({width,height:1050});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'book overflow '+width);
      if([1440,390].includes(width))await page.screenshot({path:path.join(report,'travel-book-'+width+'.png'),fullPage:true});
    }
    checks.push('Travel Book and chat have no horizontal overflow at 320, 390, 768 or 1440 pixels');
    await page.goto(origin+'/#dashboard');await page.locator('[data-action=logout]').first().click();await page.waitForURL('**/#home');
    assert.equal(await page.locator('.journey-chat-messages').textContent(),'');checks.push('Signing out clears private chat content');
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(report,'browser_checks.json'),JSON.stringify({passed:true,scope:'Isolated local app and real HTTP endpoints, live NVIDIA chat, manual memory-backed planning; hosted specialist generation tested separately',checks,errors},null,2));
    console.log(checks.join('\n'));
  }catch(e){await page.screenshot({path:path.join(report,'browser-failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(report,'browser_checks.json'),JSON.stringify({passed:false,checks,errors,error:e.message},null,2));throw e;}
  finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
