// Exhaustive rendered-control audit plus bounded local concurrency checks.
// All mutations belong to an API-created test account; no personal trip is used.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {randomBytes, randomUUID} = require('node:crypto');

(async () => {
  const origin = process.env.VOYARA_URL || 'http://127.0.0.1:8088';
  assert.ok(['127.0.0.1','localhost'].includes(new URL(origin).hostname), 'Local stress checks only');
  const report = path.resolve(process.env.VOYARA_CONTROL_REPORT || 'report/control_stress_20261017');
  await fs.mkdir(report, {recursive:true});
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const checks=[], inventory=[], errors=[], serverErrors=[], metrics=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',async r=>{if(r.url().startsWith(origin+'/api/') && r.status()>=500){const body=await r.text().catch(()=>'');serverErrors.push({url:r.url(),status:r.status(),injected:body.includes('(test)')});}});
  const stamp = 'controls_'+Date.now(), csrf=randomBytes(24).toString('hex');
  const email=stamp+'@example.com';
  let headers, catalog;
  const date=new Date(Date.now()+45*86400000).toISOString().slice(0,10);
  const end=new Date(Date.now()+48*86400000).toISOString().slice(0,10);
  async function save(){await fs.writeFile(path.join(report,'controls.json'),JSON.stringify({checks,inventory,errors,serverErrors,metrics,limits:{google:'Client ID absent; live Google authentication not exercised',providers:'Sample inventory; no provider reservation or payment',load:'Local concurrency 5; no production capacity claim'}},null,2));}
  async function check(name, fn){
    const start=Date.now();
    try {const detail=await fn();checks.push({name,status:'passed',ms:Date.now()-start,...(detail?{detail}:{})});}
    catch(e){checks.push({name,status:'failed',error:e.message,ms:Date.now()-start});await page.screenshot({path:path.join(report,'failure-'+checks.length+'.png'),fullPage:true}).catch(()=>{});}
    await save(); console.log(checks.at(-1).status.toUpperCase()+': '+name);
  }
  async function goto(route){const target=origin+'/#'+route;if(page.url()===target)await page.reload();else await page.goto(target);await page.waitForFunction(()=>!/(Your next journey is loading|Loading your journeys)/.test(document.querySelector('main').textContent));await page.locator('main h1,main h2,main h3').first().waitFor();}
  async function api(route,method='GET',data){
    const response=await context.request.fetch(origin+'/api'+route,{method,headers,data});
    assert.ok(response.ok(), `${method} ${route}: ${response.status()} ${await response.text()}`);
    return response.status()===204?null:response.json();
  }
  async function capture(route){
    const controls=await page.locator('a,button,input,select,textarea,summary').evaluateAll(els=>els.map((el,i)=>({
      index:i,tag:el.tagName.toLowerCase(),label:el.getAttribute('aria-label')||el.textContent.trim().replace(/\s+/g,' ').slice(0,100)||el.name||el.id,
      href:el.getAttribute('href'),onclick:el.getAttribute('onclick'),id:el.id||null,name:el.name||null,
      form:el.closest('form')?.id||null,type:el.type||null,visible:!!el.getClientRects().length,disabled:el.disabled||false
    })));
    inventory.push({route,controls});
  }
  async function awaitForm(form){await form.locator('button[type=submit]').waitFor({state:'visible'});await page.waitForFunction(id=>!document.getElementById(id)?.dataset.busy,await form.getAttribute('id'));}
  async function fillBooking(){const f=page.locator('#bookingForm');await f.locator('[name=first]').fill('Control');await f.locator('[name=last]').fill('Tester');await f.locator('[name=phone]').fill('+91 9999999999');await f.locator('[name=date]').fill(date);await f.locator('[name=consent]').check();return f;}
  async function mutateFavorite(kind,id){
    const before=await api('/favorites');const exists=before.some(f=>f.item_type===kind&&f.item_id===id);
    const button=page.locator(`[onclick="toggleSave('${kind}',${id})"]`).first();
    await button.click();
    await page.waitForFunction(({kind,id,want})=>[...document.querySelectorAll(`[onclick="toggleSave('${kind}',${id})"]`)].some(b=>b.getAttribute('aria-pressed')===String(want)),{kind,id,want:!exists});
    assert.equal((await api('/favorites')).some(f=>f.item_type===kind&&f.item_id===id),!exists);
  }
  try {
    const reg=await context.request.post(origin+'/api/auth/register',{data:{email,username:stamp,password:randomBytes(24).toString('hex'),full_name:'Control Tester'}});
    assert.equal(reg.status(),201);const auth=await reg.json();headers={Authorization:'Bearer '+auth.access_token};
    await context.addCookies([{name:'voyara_session',value:auth.access_token,url:origin,httpOnly:true,sameSite:'Lax'},{name:'voyara_csrf',value:csrf,url:origin,sameSite:'Lax'}]);
    catalog=await api('/website/catalog');
    const base=['home','destinations','packages','tours','hotels','planner','flights','about','contact','privacy','login','dashboard'];
    for(const route of base)await check('Inventory and link audit: '+route,async()=>{
      await goto(route);await capture(route);
      const links=await page.locator('a').evaluateAll(els=>els.map(e=>e.getAttribute('href')));
      assert.ok(links.every(h=>h && h!=='#' && !h.startsWith('javascript:')),'Empty or placeholder link');
      const dead=await page.locator('button:not([disabled])').evaluateAll(els=>els.filter(el=>!el.closest('form')&&!el.onclick&&!el.dataset.action&&!el.dataset.prompt&&!el.dataset.searchTab&&el.id!=='menuToggle').map(el=>el.outerHTML));
      assert.deepEqual(dead,[],'Buttons without a known action');
    });
    await check('Every visible header/footer/home/agent link navigates',async()=>{
      await goto('home');
      const links=await page.locator('a').evaluateAll(els=>els.map((el,index)=>({index,href:el.getAttribute('href'),visible:!!el.getClientRects().length})).filter(x=>x.visible));
      for(const link of links){await goto('home');await page.locator('a').nth(link.index).click();await page.waitForURL(origin+'/'+link.href);await page.locator('main h1,main h2,main h3').first().waitFor();assert.doesNotMatch(await page.locator('main').innerText(),/This page could not be found|Destination not found/);}
      return {clicked:links.length};
    });
    await check('All five home search-category buttons',async()=>{
      for(const [tab,route] of [['holiday','home'],['flights','flights'],['hotels','hotels'],['tours','tours'],['packages','packages']]){await goto('home');await page.locator(`[data-search-tab=${tab}]`).click();assert.equal(new URL(page.url()).hash,'#'+route);}
    });
    await check('Home search invalid input, keyboard submit and trip fields',async()=>{
      await goto('home');const f=page.locator('#quickSearch');await f.locator('[name=destination]').fill('No such place');await f.locator('button[type=submit]').click();await f.locator('.form-status').filter({hasText:'Choose a destination'}).waitFor();
      await f.locator('[name=destination]').fill('Goa');await f.locator('[name=date]').fill(date);await f.locator('[name=from]').selectOption('Mumbai');await f.locator('[name=travellers]').selectOption('2 Adults, 1 Child');await f.locator('[name=destination]').press('Enter');await page.waitForURL('**/#destination/Goa');
      await page.getByRole('link',{name:'Plan this trip'}).click();assert.equal(await page.locator('#bookingForm [name=date]').inputValue(),date);assert.equal(await page.locator('#bookingForm [name=travellers]').inputValue(),'3');
      await page.evaluate(()=>sessionStorage.removeItem('voyaraSearch'));
    });
    for(const d of catalog.destinations)await check('Destination/package controls: '+d.name,async()=>{
      await goto('destinations');await page.getByRole('link',{name:'Explore '+d.name,exact:true}).click();await page.getByRole('heading',{name:'Discover '+d.name,exact:true}).waitFor();await capture('destination/'+d.name);
      await mutateFavorite('package',d.id);await mutateFavorite('package',d.id);
      await page.getByRole('link',{name:'Plan this trip'}).click();await page.locator('#bookingForm').waitFor();assert.match(await page.locator('.sticky-card h3').innerText(),new RegExp(d.name));
      await goto('packages');await page.locator('#packageGrid .package-card').filter({has:page.locator(`a[href="#package/${encodeURIComponent(d.name)}"]`)}).getByRole('link',{name:'View trip'}).click();await capture('package/'+d.name);
      const mainLinks=await page.locator('main a').evaluateAll(els=>els.map(el=>el.getAttribute('href')));assert.ok(mainLinks.includes('#planner'));await page.locator('main a[href^="#booking"]').first().click();await page.locator('#bookingForm').waitFor();
    });
    await check('All package filter and sort combinations',async()=>{
      await goto('packages');const labels=await page.locator('.toolbar .chip').allTextContents();
      for(const label of labels){await page.getByRole('button',{name:label,exact:true}).click();for(const sort of ['featured','low','high']){await page.locator('#packageSort').selectOption(sort);const expected=catalog.destinations.filter(d=>label==='All'||d.tag===label);if(sort!=='featured')expected.sort((a,b)=>sort==='low'?a.price-b.price:b.price-a.price);const names=await page.locator('#packageGrid .package-card h3').allTextContents();assert.deepEqual(names,expected.map(d=>d.name+' escape'));}}
      return {combinations:labels.length*3};
    });
    await check('Every destination region/experience filter combination',async()=>{
      await goto('destinations');const f=page.locator('#destinationSearch');const regions=await f.locator('[name=region] option').evaluateAll(els=>els.map(e=>e.value));const types=await f.locator('[name=experience] option').evaluateAll(els=>els.map(e=>e.value));
      for(const region of regions)for(const type of types){await f.locator('[name=region]').selectOption(region);await f.locator('[name=experience]').selectOption(type);await f.locator('button').click();await awaitForm(f);const expected=catalog.destinations.filter(d=>(region==='All'||d.region===region)&&(type==='All'||d.tag===type));assert.equal(await page.locator('.escape-tile').count(),expected.length);}
      return {combinations:regions.length*types.length};
    });
    await check('Every hotel type, text-search and reset',async()=>{
      await goto('hotels');const types=await page.locator('.toolbar .chip').allTextContents();
      for(const type of types){await page.getByRole('button',{name:type,exact:true}).click();for(const text of ['', 'Jaipur','no-such-hotel']){await page.locator('#hotelSearch').fill(text);assert.equal(await page.locator('#hotelGrid .hotel-card').count(),catalog.hotels.filter(h=>(type==='All stays'||h.type.toLowerCase().includes(type.toLowerCase()))&&(h.name+' '+h.place+' '+h.type).toLowerCase().includes(text.toLowerCase())).length);}}
    });
    for(const h of catalog.hotels)await check('Hotel save and room button: '+h.name,async()=>{
      await goto('hotels');await mutateFavorite('stay',h.id);await mutateFavorite('stay',h.id);await page.locator(`[onclick="bookHotel(${h.id})"]`).click();await page.locator('#bookingForm [name=end_date]').waitFor();assert.match(await page.locator('.sticky-card h3').innerText(),new RegExp(h.name));await capture('booking?type=stay&id='+h.id);
    });
    await check('Every experience category',async()=>{await goto('tours');for(const type of await page.locator('.toolbar .chip').allTextContents()){await page.getByRole('button',{name:type,exact:true}).click();assert.equal(await page.locator('#experienceGrid .experience-card').count(),catalog.experiences.filter(e=>type==='All'||e.type===type).length);}});
    for(const e of catalog.experiences)await check('Experience booking button: '+e.name,async()=>{await goto('tours');await page.locator(`[onclick="bookExperience(${e.id})"]`).click();await page.locator('#bookingForm').waitFor();assert.match(await page.locator('.sticky-card h3').innerText(),new RegExp(e.name));});
    await check('All eight planner interest toggles',async()=>{await goto('planner');const toggles=page.locator('#plannerForm [type=checkbox]');assert.equal(await toggles.count(),8);for(const toggle of await toggles.all()){await toggle.check();assert.equal(await toggle.isChecked(),true);await toggle.uncheck();assert.equal(await toggle.isChecked(),false);}});
    await check('All FAQ mouse and keyboard expand/collapse',async()=>{await goto('contact');for(const summary of await page.locator('.faq summary').all()){await summary.click();assert.equal(await summary.evaluate(el=>el.parentElement.open),true);await summary.press('Enter');assert.equal(await summary.evaluate(el=>el.parentElement.open),false);}});
    await check('Required/invalid forms block accidental requests',async()=>{
      for(const [route,id] of [['home','quickSearch'],['planner','plannerForm'],['flights','flightSearch'],['contact','contactForm'],['booking?place=Kashmir','bookingForm']]){await goto(route);const f=page.locator('#'+id);assert.equal(await f.evaluate(el=>el.checkValidity()),false);await f.locator('[type=submit]').click();assert.equal(await f.evaluate(el=>el.dataset.busy||null),null);}
      await page.locator('#newsletter input').fill('invalid-email');assert.equal(await page.locator('#newsletter').evaluate(el=>el.checkValidity()),false);
    });
    await check('Booking review, edit, quote failure, retry, rapid confirm',async()=>{
      await goto('booking?place=Kashmir');let f=await fillBooking();await capture('booking-form');
      await page.route('**/api/website/quote',route=>route.fulfill({status:503,json:{detail:'Temporary quote outage (test)'}}),{times:1});
      await f.locator('[type=submit]').click();await f.locator('.form-status').filter({hasText:'Temporary quote outage'}).waitFor();assert.equal(await f.locator('[type=submit]').isEnabled(),true);
      await f.locator('[type=submit]').click();await page.locator('#editRequest').waitFor();await capture('booking-review');await page.locator('#editRequest').click();assert.equal(await f.locator('[name=first]').isEnabled(),true);assert.equal(await page.locator('#confirmRequest').count(),0);
      await f.locator('[name=travellers]').selectOption('3');await f.locator('[type=submit]').click();await page.locator('#confirmRequest').waitFor();
      await page.route('**/api/website/bookings',route=>route.fulfill({status:503,json:{detail:'Temporary save outage (test)'}}),{times:1});await page.locator('#confirmRequest').click();await page.locator('#confirmationStatus').filter({hasText:'Temporary save outage'}).waitFor();assert.equal(await page.locator('#confirmRequest').isEnabled(),true);
      const before=(await api('/bookings')).length;await page.locator('#confirmRequest').evaluate(el=>{el.click();el.click();});await page.getByRole('heading',{name:'Your request is saved'}).waitFor();assert.equal((await api('/bookings')).length,before+1);await capture('booking-saved');
    });
    await check('Flight invalid airports/dates, empty state, route select and refresh',async()=>{
      await goto('flights');const f=page.locator('#flightSearch');await f.locator('[name=depart]').fill(date);const airports=await f.locator('[name=from] option').evaluateAll(els=>els.map(e=>e.value));await f.locator('[name=to]').selectOption(airports[0]);await f.locator('[name=from]').selectOption(airports[0]);await f.locator('[type=submit]').click();await f.locator('.form-status').filter({hasText:'Choose different airports'}).waitFor();
      await f.locator('[name=from]').selectOption({label:'New Delhi'});await f.locator('[name=to]').selectOption({label:'Kashmir'});await f.locator('[type=submit]').click();await page.locator('[data-flight]').first().waitFor();await capture('flight-results');await page.locator('[data-flight]').first().click();await page.locator('#bookingForm [name=date][readonly]').waitFor();await page.reload();await page.getByRole('heading',{name:'Choose your journey'}).waitFor();await page.getByRole('link',{name:'Search flights',exact:true}).click();await page.locator('#flightSearch').waitFor();
    });
    await check('Saved cards can be removed from My Trips',async()=>{await api('/favorites','POST',{item_type:'package',item_id:catalog.destinations[0].id});await api('/favorites','POST',{item_type:'stay',item_id:catalog.hotels[0].id});await goto('dashboard');while(await page.locator('main .heart').count()){const count=await page.locator('main .heart').count();await page.locator('main .heart').first().click();await page.waitForFunction(n=>document.querySelectorAll('main .heart').length<n,count);await page.locator('#profileForm').waitFor();}assert.equal((await api('/favorites')).length,0);});
    await check('Error page retry and boot retry',async()=>{
      await page.route('**/api/bookings',route=>route.fulfill({status:503,json:{detail:'Temporary dashboard outage (test)'}}),{times:1});await goto('dashboard');await page.getByRole('button',{name:'Try again',exact:true}).click();await page.locator('#profileForm').waitFor();
      await page.route('**/api/website/catalog',route=>route.fulfill({status:503,json:{detail:'Temporary catalog outage (test)'}}),{times:1});await page.reload();await page.locator('#retryBoot').waitFor();await page.locator('#retryBoot').click();await page.locator('#profileForm').waitFor();
    });
    await check('Back/forward navigation restores functional forms',async()=>{await goto('home');await page.locator('[data-search-tab=hotels]').click();await page.locator('#hotelSearch').waitFor();await page.goBack();await page.locator('#quickSearch').waitFor();await page.goForward();await page.locator('#hotelSearch').fill('no-matching-hotel');await page.getByRole('heading',{name:'No matching stays'}).waitFor();});
    await check('Mobile menu: every header link, close, account and footer',async()=>{await page.setViewportSize({width:390,height:844});await goto('home');const hrefs=await page.locator('#mainNav a').evaluateAll(els=>els.map(el=>el.getAttribute('href')));for(const href of hrefs){await page.locator('#menuToggle').click();assert.equal(await page.locator('#menuToggle').getAttribute('aria-expanded'),'true');await page.locator(`#mainNav a[href="${href}"]`).click();assert.equal(await page.locator('#menuToggle').getAttribute('aria-expanded'),'false');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}await page.locator('#menuToggle').click();await page.locator('#menuToggle').click();assert.equal(await page.locator('#menuToggle').getAttribute('aria-expanded'),'false');await page.locator('.login-link').click();await page.locator('#profileForm').waitFor();await page.setViewportSize({width:1440,height:1000});});
    await check('Rapid favorites click is a single mutation',async()=>{await goto('home');const id=catalog.destinations[0].id;await api('/favorites/package/'+id,'DELETE');await page.reload();const requests=[];const listener=r=>{if(r.url().endsWith('/api/favorites')&&r.method()==='POST')requests.push(r);};page.on('request',listener);const b=page.locator(`[onclick="toggleSave('package',${id})"]`);await b.evaluate(el=>{for(let i=0;i<5;i++)el.click();});await page.waitForFunction(()=>document.querySelector('.heart')?.getAttribute('aria-pressed')==='true');await api('/favorites');page.off('request',listener);assert.equal(requests.length,1,'Rapid save clicks should coalesce');});
    await check('Favorite failure displays feedback and permits retry',async()=>{await goto('hotels');const id=catalog.hotels[0].id;await api('/favorites/stay/'+id,'DELETE');await goto('hotels');await page.route('**/api/favorites',route=>route.request().method()==='POST'?route.fulfill({status:503,json:{detail:'Temporary favorites outage (test)'}}):route.continue(),{times:1});await page.locator(`[onclick="toggleSave('stay',${id})"]`).click();await page.locator('#toast').filter({hasText:'Temporary favorites outage'}).waitFor();await mutateFavorite('stay',id);});
    await check('Bounded API load: 60 reads, concurrency five',async()=>{
      let next=0;const endpoints=['/website/catalog','/favorites','/bookings','/profile','/itineraries','/assistant/conversations'];
      await Promise.all(Array.from({length:5},async()=>{while(next<60){const index=next++,start=Date.now();await api(endpoints[index%endpoints.length]);metrics.push({kind:'read',ms:Date.now()-start});}}));
      const durations=metrics.map(m=>m.ms).sort((a,b)=>a-b);return {requests:durations.length,concurrency:5,p95_ms:durations[Math.ceil(durations.length*.95)-1],max_ms:durations.at(-1)};
    });
    await check('Concurrent booking retries preserve one request',async()=>{
      const d=catalog.destinations[0],finish=new Date(new Date(date+'T12:00:00Z').getTime()+d.nights*86400000).toISOString().slice(0,10),items=[{item_type:'package',item_id:d.id,quantity:1,start_date:date,end_date:finish}];const quote=await api('/website/quote','POST',{items});const data={items,request_key:randomUUID(),expected_total_inr:quote.total_inr,traveler:{first:'Load',last:'Tester',email,phone:'+91 9999999999',notes:'Isolated concurrency check',consent:true}};const results=await Promise.all(Array.from({length:5},()=>api('/website/bookings','POST',data)));assert.equal(new Set(results.map(r=>r.id)).size,1);await api('/bookings/'+results[0].id+'/cancel','POST');
    });
    await check('Concurrent duplicate subscriptions are idempotent',async()=>{await Promise.all(Array.from({length:5},()=>api('/website/newsletter','POST',{email})));});
    await check('Concurrent favorite saves preserve one item',async()=>{const id=catalog.hotels[0].id;await api('/favorites/stay/'+id,'DELETE');await Promise.all(Array.from({length:5},()=>api('/favorites','POST',{item_type:'stay',item_id:id})));assert.equal((await api('/favorites')).filter(f=>f.item_type==='stay'&&f.item_id===id).length,1);});
    await check('Malformed and unknown routes have working escape links',async()=>{for(const route of ['destination/NoSuchPlace','package/NoSuchPlace','no-such-page','booking?type=stay&id=999999']){await goto(route);assert.doesNotMatch(await page.locator('main').innerText(),/undefined|\[object Object\]/);await page.locator('.brand').first().click();await page.locator('#quickSearch').waitFor();}});
    await check('Logout and signed-out guards for favorites/planner/bookings',async()=>{
      await goto('dashboard');for(const b of await page.locator('[data-action=cancel]').all()){if(await b.isVisible()){await b.click();await page.locator('#profileForm').waitFor();}}
      await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/#home');await page.locator('.heart').first().click();await page.waitForURL('**/#login');await page.getByText('Google sign-in is awaiting setup',{exact:true}).waitFor();
      await goto('dashboard');await page.getByRole('heading',{name:'Keep your journeys together'}).waitFor();assert.equal(await page.locator('#profileForm').count(),0);
    });
    // Delete only this test account's active booking requests and shortlist.
    await check('Test-data cleanup',async()=>{for(const b of await api('/bookings'))if(b.status==='requested')await api('/bookings/'+b.id+'/cancel','POST');for(const f of await api('/favorites'))await api('/favorites/'+f.item_type+'/'+f.item_id,'DELETE');});
    const unexpected500=serverErrors.filter(e=>!e.injected);
    await check('No uncaught browser exceptions',async()=>assert.deepEqual(errors,[]));
    await check('No unexpected server failures',async()=>assert.deepEqual(unexpected500,[]));
    await save();const failed=checks.filter(c=>c.status==='failed');console.log(JSON.stringify({passed:checks.length-failed.length,failed:failed.map(c=>c.name),inventory_pages:inventory.length,rendered_controls:inventory.reduce((n,r)=>n+r.controls.length,0),unexpected500},null,2));
    if(failed.length)process.exitCode=1;
  } finally {await save();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
