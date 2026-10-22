/* Replays a fictional chat fixture based on the reported wording. */
const path=require('node:path');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../dashboard/frontend/package.json'))('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');

(async()=>{
  const origin='http://127.0.0.1:8000';
  const report=path.resolve('report/conversational_travel_20261022');
  await fs.mkdir(report,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1050}});
  const page=await context.newPage(), turns=[], errors=[];
  page.setDefaultTimeout(30000);
  page.on('pageerror',error=>errors.push(error.message));
  async function send(message,{model=true}={}){
    await page.locator('#journeyMessage').fill(message);
    const pending=page.waitForResponse(r=>r.url().endsWith('/chat')&&r.request().method()==='POST');
    const started=Date.now();
    await page.getByRole('button',{name:'Send to Voyara AI',exact:true}).click();
    const response=await pending;
    assert.equal(response.status(),200);
    const result=await response.json();
    await page.locator('.journey-chat-loading').waitFor({state:'hidden'});
    assert.equal(result.status,'ok',result.reply);
    assert.equal(result.conversation?.mode,model?'nvidia':'local',JSON.stringify(result.conversation));
    assert.equal(result.conversation.model_calls,model?1:0);
    assert.ok(!result.reply.includes('Travelers:')&&!result.reply.includes('Preferences:'));
    turns.push({message,reply:result.reply,seconds:(Date.now()-started)/1000,conversation:result.conversation});
    return result;
  }
  try{
    const login=await context.request.post(origin+'/api/auth/developer',{headers:{Origin:origin,'X-Voyara-Developer':'1'}});
    assert.equal(login.status(),200,await login.text());
    const csrf=(await context.cookies()).find(cookie=>cookie.name==='voyara_csrf').value;
    const created=await context.request.post(origin+'/api/assistant/conversations',{headers:{Origin:origin,'X-CSRF-Token':csrf},data:{}});
    assert.equal(created.status(),201,await created.text());
    const id=(await created.json()).id;
    await page.goto(origin+'/#travel-book/'+id);
    await page.locator('.journey-book').waitFor();
    await page.locator('.journey-launcher').click();
    const first=await send('I want to go ot the place where I can feel relax, for a solo trip with 50k');
    assert.equal(first.workspace.draft.pace,'relaxed');
    assert.equal(first.workspace.draft.budget,50000);
    assert.equal(first.workspace.draft.traveller_count,1);
    assert.equal(first.cards.length,3);
    assert.ok(!first.reply.includes('Where would you like to go?'));
    assert.equal(await page.locator('.journey-understanding').evaluate(el=>el.open),false);
    const second=await send('suggest some places');
    assert.deepEqual(second.cards.map(c=>c.name),first.cards.map(c=>c.name));
    assert.ok(!second.cards.some(c=>c.name==='Jaipur'));
    assert.equal(second.workspace.revision,first.workspace.revision);
    const why=await send('why '+second.cards[0].name);
    assert.equal(why.workspace.revision,first.workspace.revision);
    await page.screenshot({path:path.join(report,'conversation-desktop.png')});
    const chosen=await send('the second one',{model:false});
    assert.equal(chosen.workspace.draft.destination,second.cards[1].name);
    assert.equal(chosen.workspace.draft.budget,50000);
    assert.ok(chosen.reply.includes(second.cards[1].name));
    assert.equal(chosen.awaiting,'origin');
    assert.ok(chosen.reply.includes('starting from'));
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.locator('.journey-chat').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
    await page.screenshot({path:path.join(report,'conversation-mobile.png')});
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(report,'acceptance.json'),JSON.stringify({passed:true,trip_id:id,turns,errors},null,2));
    console.log(JSON.stringify({passed:true,trip_id:id,turns},null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
