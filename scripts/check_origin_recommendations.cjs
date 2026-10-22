/* Fictional local demo: origins, fares, per-card reasons and more destinations. */
const path=require('node:path');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../dashboard/frontend/package.json'))('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');

(async()=>{
  const origin='http://127.0.0.1:8000', report=path.resolve('report/origin_recommendations_20261022');
  await fs.mkdir(report,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1050}});
  const page=await context.newPage(), checks=[], errors=[];
  page.setDefaultTimeout(30000);
  page.on('pageerror',error=>errors.push(error.message));
  async function waitTurn(action){
    const pending=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST');
    await action();
    const response=await pending;
    assert.equal(response.status(),200,await response.text());
    const result=await response.json();
    assert.equal(result.status,'ok',result.reply);
    await page.locator('.journey-chat-loading').waitFor({state:'hidden'});
    return result;
  }
  async function send(text){
    await page.locator('#journeyMessage').fill(text);
    return waitTurn(()=>page.getByRole('button',{name:'Send to Voyara AI',exact:true}).click());
  }
  try{
    assert.equal((await context.request.post(origin+'/api/auth/developer',{headers:{Origin:origin,'X-Voyara-Developer':'1'}})).status(),200);
    await page.goto(origin+'/#home');
    await page.locator('.journey-launcher').click();
    await page.locator('.journey-chat-loading').waitFor({state:'hidden'});
    const created=page.waitForResponse(r=>r.url().endsWith('/assistant/conversations')&&r.request().method()==='POST');
    await page.locator('[data-chat=new]').click();
    const id=(await (await created).json()).id;
    await page.locator('.journey-chat-loading').waitFor({state:'hidden'});
    const first=await send('I want a relaxing solo trip with 50k');
    assert.equal(first.awaiting,'origin');
    assert.ok(first.reply.toLowerCase().includes('city'));
    assert.equal(await page.locator('.journey-destination-fit').count(),3);
    assert.ok(first.cards.every(c=>c.match_reasons.length&&c.transport.status==='needs_origin'));
    assert.ok((await page.locator('.journey-chat-cards').innerText()).includes('excludes travel fares'));
    checks.push('Asks for the starting city; every initial card explains its preference fit and excludes unknown fares');
    const located=await send('Mumbai');
    assert.equal(located.workspace.draft.origin,'Mumbai');
    assert.ok(!located.workspace.draft.destination);
    const goaMumbai=located.workspace.options.destinations.find(d=>d.name==='Goa').transport;
    assert.ok(goaMumbai.round_trip_inr>0);
    assert.ok(located.cards.every(c=>c.transport.origin==='Mumbai'));
    const initial=new Set(located.cards.map(c=>c.name));
    const more=await waitTurn(()=>page.getByRole('button',{name:'See more destinations',exact:true}).click());
    assert.ok(more.cards.every(c=>!initial.has(c.name)));
    const seen=new Set([...initial,...more.cards.map(c=>c.name)]);
    const moreAgain=await waitTurn(()=>page.getByRole('button',{name:'See more destinations',exact:true}).click());
    assert.ok(moreAgain.cards.every(c=>!seen.has(c.name)));
    assert.equal(moreAgain.workspace.draft.budget,50000);
    checks.push('See more loads distinct batches without changing the traveler count, budget or chosen destination');
    await page.locator('.journey-chat-cards').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(report,'reasons-and-more-desktop.png')});
    const name=moreAgain.cards[0].name;
    const chosen=await waitTurn(()=>page.locator('.journey-chat-cards .journey-choice').filter({has:page.getByText(name,{exact:true})}).getByRole('button').click());
    assert.equal(chosen.workspace.draft.destination,name);
    assert.equal(chosen.workspace.draft.origin,'Mumbai');
    await send("Actually, I'm starting from New Delhi");
    const current=await (await context.request.get(origin+'/api/assistant/conversations/'+id+'/workspace')).json();
    const goaDelhi=current.options.destinations.find(d=>d.name==='Goa').transport;
    assert.equal(goaDelhi.origin,'New Delhi');
    assert.notEqual(goaDelhi.round_trip_inr,goaMumbai.round_trip_inr);
    checks.push('Changing the starting city changes actual sample round-trip fares and preserves the selected destination');
    await page.reload();
    await page.locator('.journey-launcher').click();
    await page.locator('.journey-chat-loading').waitFor({state:'hidden'});
    assert.ok((await page.locator('.journey-chat-cards').innerText()).includes('Why this fits you'));
    await page.setViewportSize({width:390,height:844});
    await page.locator('.journey-chat-cards').scrollIntoViewIfNeeded();
    assert.ok(await page.locator('.journey-chat').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
    await page.screenshot({path:path.join(report,'reasons-and-more-mobile.png')});
    checks.push('Explanations, origin-specific fare notices and the more-options control persist after reload and fit mobile');
    assert.deepEqual(errors,[]);
    const result={passed:true,trip_id:id,checks,fares:{Mumbai:goaMumbai,NewDelhi:goaDelhi},errors};
    await fs.writeFile(path.join(report,'acceptance.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result,null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
