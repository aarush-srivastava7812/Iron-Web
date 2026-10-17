// Focused checks for the user's two reference layouts. Existing connected smoke
// checks cover the booking, assistant and memory mutation contracts separately.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');

(async()=>{
  const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const origin=process.env.VOYARA_URL || 'http://127.0.0.1:8088';
  const report=path.resolve('report/reference_ui_20261017');
  await fs.mkdir(report,{recursive:true});
  const errors=[], checks={};
  page.on('pageerror',e=>errors.push(e.message));
  async function goto(route){await page.goto(origin+'/#'+route);await page.locator('main h1').waitFor();}
  async function waitForPhotos(){
    const failed=await page.evaluate(async()=>{
      const sources=[...document.querySelectorAll('.hero-scene,.escape-photo')].map(el=>getComputedStyle(el).backgroundImage.match(/url\(["']?(.*?)["']?\)/)?.[1]).filter(Boolean);
      const results=await Promise.all(sources.map(async src=>{
        const img=new Image();img.src=src;
        try{await img.decode();return null;}catch{return src;}
      }));
      await Promise.all([...document.querySelectorAll('main img')].map(async img=>{img.loading='eager';try{await img.decode();}catch{results.push(img.src);}}));
      return results.filter(Boolean);
    });
    assert.deepEqual(failed,[],'Reference photography should load');
  }
  try {
    await goto('home');
    assert.equal(await page.locator('.agent-tile').count(),7);
    assert.equal(await page.locator('.holiday-tile').count(),10);
    assert.equal(await page.locator('.home-hero .team-row').count(),7);
    assert.equal(await page.locator('.site-header .brand-mark svg').count(),1);
    assert.equal(await page.locator('.holiday-tile img').count(),10);
    await waitForPhotos();
    await page.screenshot({path:path.join(report,'home-desktop.png'),fullPage:true});
    checks.home_reference_structure=true;
    for(const tab of ['flights','hotels','tours','packages']){
      await goto('home');await page.locator('[data-search-tab='+tab+']').click();
      await page.waitForURL('**/#'+tab);await page.locator('main h1').waitFor();
    }
    checks.search_category_navigation=true;
    await goto('home');
    await page.locator('.agent-tile').filter({hasText:'Food Guide Agent'}).getByRole('link',{name:'Explore',exact:true}).click();
    await page.locator('#plannerForm').waitFor();
    assert.equal(await page.locator('#plannerForm input[value=Food]').isChecked(),true);
    checks.food_agent_opens_connected_planner=true;
    await goto('destinations');
    assert.equal(await page.locator('.escape-tile').count(),10);
    assert.equal(await page.locator('.destination-hero .team-row').count(),4);
    await waitForPhotos();
    await page.screenshot({path:path.join(report,'destinations-desktop.png'),fullPage:true});
    const form=page.locator('#destinationSearch');
    await form.getByLabel('Region',{exact:true}).selectOption('North India');
    await form.getByLabel('Experience',{exact:true}).selectOption('Adventure');
    await form.getByRole('button',{name:'Search',exact:true}).click();
    assert.equal(await page.locator('.escape-tile').count(),2);
    await form.getByLabel('Search destinations',{exact:true}).fill('Manali');
    await form.getByRole('button',{name:'Search',exact:true}).click();
    assert.equal(await page.locator('.escape-tile').count(),1);
    assert.match(await page.locator('.escape-tile').getAttribute('class'),/escape-yellow/);
    await page.getByRole('link',{name:'Explore Manali',exact:true}).click();
    await page.getByRole('heading',{name:'Discover Manali',exact:true}).waitFor();
    checks.destination_search_filters_and_detail=true;
    await goto('destinations');
    await page.locator('#destinationSearch [name=q]').fill('Nothing matches this destination');
    await page.locator('#destinationSearch button').click();
    await page.getByRole('heading',{name:'No matching destinations',exact:true}).waitFor();
    assert.match(await page.locator('#destinationCount').textContent(),/^0/);
    checks.destination_empty_state=true;
    for(const width of [320,390,768,1024]){
      await page.setViewportSize({width,height:900});
      for(const route of ['home','destinations']){
        await goto(route);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,route+' overflows at '+width);
        assert.equal(await page.locator('.login-link').isVisible(),true,'Sign-in must remain reachable');
        if(width===390){await waitForPhotos();await page.screenshot({path:path.join(report,route+'-mobile.png'),fullPage:true});}
      }
      if(width<981){
        await page.locator('#menuToggle').click();
        await page.locator('#mainNav').getByRole('link',{name:'Flights',exact:true}).click();
        await page.waitForURL('**/#flights');
      }
    }
    checks.mobile_tablet_layout_and_navigation=true;
    // Check the user's existing developer conversation read-only, when present.
    await goto('login');
    const dev=page.getByRole('button',{name:'Continue as Developer'});
    const developerConfig=await page.request.get(origin+'/api/auth/developer/config').then(r=>r.json());
    if(developerConfig.enabled){
      await dev.waitFor();
      await dev.click();await page.locator('#profileForm').waitFor();
      const trips=page.locator('a[href^="#trip/"]');
      if(await trips.count()){
        await trips.first().click();await page.locator('#tripChat').waitFor({timeout:120000});
        assert((await page.locator('.memory-detail').count())>0);
        assert.equal(await page.locator('.memory-technical').getAttribute('open'),null);
        checks.readable_existing_trip_memory=true;
        if(/(?:Stay Agent:\s*0 stay options|Tour Guide Agent:\s*0 experience ideas)/i.test(await page.locator('.chat-record').allTextContents().then(x=>x.join(' ')))){
          assert((await page.locator('.plan-caveat').count())>0);
          checks.partial_plan_notice=true;
        }
      }
    }
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(report,'reference-check.json'),JSON.stringify({checks,browser_errors:errors,viewports:[320,390,768,1024,1440]},null,2));
    console.log('Reference layouts, search, navigation, mobile/tablet sizes and readable memory checks passed.');
  }catch(error){await page.screenshot({path:path.join(report,'failure.png'),fullPage:true});throw error;}
  finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
