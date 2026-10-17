// Live UI check of the supplied frontend and real memory/agent service.
// A test-only API account bootstraps a cookie; this does not test live Google
// sign-in, which awaits the user's GOOGLE_CLIENT_ID configuration.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const {randomBytes} = require('node:crypto');
const assert = require('node:assert/strict');

(async()=>{
  const origin=process.env.VOYARA_URL || 'http://127.0.0.1:8088';
  const report=path.resolve(process.env.VOYARA_REPORT_PATH || 'report/frontend_integration_20261016');
  await fs.mkdir(report,{recursive:true});
  const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const page=await context.newPage(), errors=[], agentResponses=[], checks={};
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',async r=>{if(r.url().endsWith('/messages') && r.request().method()==='POST')agentResponses.push(await r.json());});
  const future=new Date();future.setDate(future.getDate()+40);
  const date=future.toISOString().slice(0,10);
  const next=new Date(future);next.setDate(next.getDate()+3);
  const end=next.toISOString().slice(0,10);
  async function goto(hash){await page.goto(origin+'/#'+hash);await page.locator('main h1, main h2').first().waitFor();}
  async function submitBooking({stay=false}={}) {
    const form=page.locator('#bookingForm');
    await form.locator('[name=first]').fill('Browser');await form.locator('[name=last]').fill('Traveller');
    await form.locator('[name=phone]').fill('+91 9999999999');
    if(await form.locator('[name=date]').getAttribute('readonly')===null)await form.locator('[name=date]').fill(date);
    if(stay)await form.locator('[name=end_date]').fill(end);
    await form.locator('[name=notes]').fill('Browser integration test request');
    await form.locator('[name=consent]').check();
    await form.getByRole('button',{name:'Review trip request'}).click();
    await page.locator('#confirmRequest').waitFor();
    await page.locator('#confirmRequest').click();
    await page.locator('#bookingReview').getByRole('heading',{name:'Your request is saved'}).waitFor();
  }
  try {
    await goto('login');await page.getByText('Google sign-in is awaiting setup',{exact:true}).waitFor();
    checks.google_unconfigured_ui=true;
    const name='ui_'+Date.now();
    const registration=await context.request.post(origin+'/api/auth/register',{data:{email:name+'@example.com',username:name,
      password:randomBytes(24).toString('hex'),full_name:'Browser Traveller'}});
    assert.equal(registration.status(),201);
    const auth=await registration.json();
    await context.addCookies([{name:'voyara_session',value:auth.access_token,url:origin,httpOnly:true,sameSite:'Lax'},
      {name:'voyara_csrf',value:randomBytes(24).toString('hex'),url:origin,sameSite:'Lax'}]);
    await page.reload();
    await goto('home');await page.locator('.login-link').filter({hasText:'Browser'}).waitFor();
    await page.screenshot({path:path.join(report,'desktop-home.png'),fullPage:true});
    console.log('Loaded supplied design; bootstrapped an isolated test session.');
    const search=page.locator('#quickSearch');await search.locator('[name=destination]').fill('Kashmir');
    await search.locator('[name=date]').fill(date);await search.getByRole('button',{name:/Search (trips|Holidays)/i}).click();
    await page.getByRole('heading',{name:'Discover Kashmir'}).waitFor();
    await page.getByRole('button',{name:'Save for later'}).click();await page.getByRole('button',{name:'♥ Saved'}).waitFor();
    await page.reload();await page.getByRole('button',{name:'♥ Saved'}).waitFor();
    checks.account_favorites_persist=true;
    await page.getByRole('link',{name:'Plan this trip'}).click();await page.locator('#bookingForm').waitFor();
    await submitBooking();checks.package_request=true;
    console.log('Saved across reload and submitted a reviewed, server-priced package request.');
    await goto('packages');await page.getByRole('button',{name:'Adventure',exact:true}).click();
    await page.locator('#packageSort').selectOption('low');
    assert.equal(await page.locator('#packageGrid .package-card').count(),2);
    assert.match(await page.locator('#packageGrid .package-card').first().innerText(),/Rishikesh/);
    checks.filter_sort_composition=true;
    await goto('hotels');await page.getByRole('button',{name:'Heritage',exact:true}).click();
    await page.locator('#hotelSearch').fill('Jaipur');assert.equal(await page.locator('#hotelGrid article').count(),1);
    await page.getByRole('button',{name:'View rooms'}).click();await submitBooking({stay:true});checks.stay_request=true;
    await goto('tours');await page.getByRole('button',{name:'Book experience'}).first().click();
    await submitBooking();checks.experience_request=true;
    await goto('flights');const flights=page.locator('#flightSearch');
    await flights.locator('[name=depart]').fill(date);await flights.locator('[name=return]').fill(end);
    await flights.getByRole('button',{name:'Search routes'}).click();
    await page.locator('[data-flight]').first().click();await submitBooking();checks.round_trip_route_request=true;
    console.log('Hotel, experience and round-trip flight selections reached persisted requests.');
    await goto('contact');const contact=page.locator('#contactForm');
    await contact.locator('[name=name]').fill('Browser Traveller');await contact.locator('[name=email]').fill(name+'@example.com');
    await contact.locator('[name=message]').fill('Please help plan my next trip.');
    await contact.getByRole('button',{name:'Send message'}).click();
    await contact.locator('.form-status').filter({hasText:/Enquiry #\d+ received/}).waitFor();checks.enquiry=true;
    await page.locator('#newsletter input').fill(name+'@example.com');await page.locator('#newsletter button').click();
    await page.locator('#newsletterMsg').filter({hasText:'Subscription saved'}).waitFor();checks.newsletter=true;
    await goto('dashboard');const prefs=page.locator('#profileForm');
    await prefs.locator('[name=travel_style]').selectOption('slow travel');await prefs.locator('[name=diet]').selectOption('vegetarian');
    await prefs.getByRole('button',{name:'Save preferences'}).click();
    await prefs.locator('.form-status').filter({hasText:'Preferences saved'}).waitFor({timeout:180000});checks.saved_preferences=true;
    await goto('planner');const planner=page.locator('#plannerForm');
    await planner.locator('[name=place]').selectOption('Kashmir');await planner.locator('[name=date]').fill(date);
    await planner.locator('[name=budget]').fill('150000');await planner.locator('[name=duration]').selectOption('5');
    await planner.getByRole('button',{name:'Create my trip outline'}).click();
    await page.locator('#savePlanStatus').filter({hasText:'Itinerary saved to My Trips.'}).waitFor({timeout:240000});
    assert.equal(agentResponses.at(-1)?.orchestration?.status,'ok');
    assert.equal(agentResponses.at(-1).orchestration.trip_brief.destination,'Kashmir');
    const memory=agentResponses.at(-1).orchestration.memory;assert(memory.some(m=>m.claim_ids.length));
    checks.connected_plan_and_real_memory=true;
    await page.locator('#plannerResult').screenshot({path:path.join(report,'connected-plan.png')});
    console.log('Planner produced an itinerary using real graph/vector memory and travel agents.');
    await page.locator('#conciergePrompt').fill('Lower my budget to INR 140000');
    const budgetResponse=page.waitForResponse(r=>r.url().endsWith('/messages') && r.request().method()==='POST');
    await page.locator('#conciergeForm button').click();
    const budgetUpdate=await (await budgetResponse).json();
    await page.waitForFunction(()=>!document.querySelector('#conciergeForm button').disabled,{},{timeout:180000});
    assert.equal(budgetUpdate.orchestration.trip_brief.budget_total_inr,140000);checks.concierge_memory_update=true;
    await page.getByRole('link',{name:'View conversation & memory'}).click();
    await page.locator('#tripChat').waitFor({timeout:180000});await page.reload();await page.locator('#tripChat').waitFor({timeout:180000});
    assert((await page.locator('.chat-record').count())>=4);checks.conversation_persists=true;
    const beforeForget=await page.locator('[data-action=forget-event]').count();
    await page.locator('[data-action=forget-event]').first().click();
    await page.waitForFunction(count=>document.querySelectorAll('[data-action=forget-event]').length<count,beforeForget,{timeout:180000});checks.forget_memory_event=true;
    await goto('dashboard');await page.locator('#profileForm').waitFor();
    assert.equal(await page.locator('[data-action=cancel]').count(),4);assert.equal(await page.locator('[data-action=delete-itinerary]').count(),1);
    await page.screenshot({path:path.join(report,'desktop-dashboard.png'),fullPage:true});
    while(await page.locator('[data-action=cancel]').count()) {
      const before=await page.locator('[data-action=cancel]').count();await page.locator('[data-action=cancel]').first().click();
      await page.waitForFunction(count=>document.querySelectorAll('[data-action=cancel]').length<count,before);
    }
    checks.cancel_requests=true;
    await page.locator('[data-action=delete-itinerary]').click();await page.locator('[data-action=delete-itinerary]').waitFor({state:'detached'});
    await page.locator('[data-action=forget-trip]').click();await page.locator('[data-action=forget-trip]').waitFor({state:'detached',timeout:180000});checks.delete_itinerary_and_trip_memory=true;
    for(const route of ['home','planner','booking?place=Kashmir','login','hotels','dashboard','privacy']) {
      await page.setViewportSize({width:390,height:844});await goto(route);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,route+' overflows');
    }
    await goto('home');await page.screenshot({path:path.join(report,'mobile-home.png'),fullPage:true});
    await page.locator('#menuToggle').click();assert.equal(await page.locator('#menuToggle').getAttribute('aria-expanded'),'true');checks.mobile_menu_and_layout=true;
    await goto('dashboard');await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/#home');
    await goto('dashboard');await page.getByRole('heading',{name:'Keep your journeys together'}).waitFor();checks.logout=true;
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(report,'browser-check.json'),JSON.stringify({checks,browser_errors:errors,
      google_live_login:'Not tested: client ID not configured. Cookie sessions and verifier behavior tested separately.',
      test_auth:'API-created isolated test account; browser HttpOnly cookie bootstrap',
      embedding_scope:'Live CPU neural embeddings, real FalkorDB/Qdrant; deterministic travel agents',
      memory_devices:[...new Set(memory.map(m=>m.residency.device))]},null,2));
    console.log('All browser checks passed.');
  } catch(error) {await page.screenshot({path:path.join(report,'failure.png'),fullPage:true});throw error;}
  finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
