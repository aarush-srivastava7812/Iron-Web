const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const report = path.resolve('report/hackathon_travel_20261017');
  await fs.mkdir(report, {recursive:true});
  const origin = process.env.VOYARA_EDITOR_TEST_URL || 'http://127.0.0.1:8092';
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  const page = await context.newPage(), errors = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  page.setDefaultTimeout(20000);
  try {
    const login = await context.request.post(origin+'/api/auth/developer', {headers:{Origin:origin,'X-Voyara-Developer':'1'}});
    assert.equal(login.status(),200,await login.text());
    const trips = await (await context.request.get(origin+'/api/assistant/conversations')).json();
    const trip = trips.find(t => t.title==='Goa hackathon browser fixture');
    assert.ok(trip);
    const endpoint = origin+'/api/assistant/conversations/'+trip.id+'/plan';
    await page.goto(origin+'/#trip/'+trip.id);
    await page.locator('.travel-plan').waitFor();
    assert.equal(await page.locator('.agent-work-grid article').count(),7);
    checks.push('Seven actual specialist traces render from retained live NVIDIA plan');
    const original = await (await context.request.get(endpoint)).json();
    const editResponse = page.waitForResponse(r => r.url().endsWith('/plan/edits') && r.request().method()==='POST');
    await page.locator('[data-plan-action=remove]').first().click();
    const edited = await (await editResponse).json();
    assert.equal(edited.version, original.version+1);
    assert.ok(edited.plan.budget.total_inr < original.plan.budget.total_inr);
    await page.locator('.plan-delta').first().filter({hasText:'previous version'}).waitFor();
    await page.reload();
    await page.locator('.travel-plan .tag').filter({hasText:'VERSION '+edited.version}).waitFor();
    checks.push('Remove activity/meal reprices and persists across reload');
    await page.locator('#planHistory').selectOption(String(original.version));
    await page.locator('#planComparison').filter({hasText:'compared with version '+original.version}).waitFor();
    const restoreResponse = page.waitForResponse(r => r.url().endsWith('/plan/edits') && r.request().method()==='POST');
    await page.locator('[data-plan-action=restore]').click();
    const restored = await (await restoreResponse).json();
    assert.equal(restored.plan.budget.total_inr,original.plan.budget.total_inr);
    checks.push('Compare and restore reproduce the original estimate');
    const stayOptions = page.locator('#planStay option');
    assert.ok(await stayOptions.count() >= 2);
    await page.locator('#planStay').selectOption('1');
    const stayResponse = page.waitForResponse(r => r.url().endsWith('/plan/edits') && r.request().method()==='POST');
    await page.locator('[data-plan-action=stay]').click();
    assert.equal((await stayResponse).status(),200);
    checks.push('Stay alternatives save and reprice through the server');
    const download = page.waitForEvent('download');
    await page.locator('[data-plan-action=export]').click();
    const exported = await download;
    assert.ok(exported.suggestedFilename().endsWith('.txt'));
    await exported.saveAs(path.join(report,'exported_itinerary.txt'));
    checks.push('Text export downloads successfully');
    for (const width of [1440,768,390,320]) {
      await page.setViewportSize({width,height:1000});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'overflow at '+width);
      if ([1440,390].includes(width)) await page.screenshot({path:path.join(report,'editor-'+width+'.png'),fullPage:true});
    }
    checks.push('No horizontal overflow at 1440, 768, 390 or 320 pixels');
    await page.locator('.agent-work > summary').click();
    assert.ok(await page.locator('.agent-work').getAttribute('open') !== null);
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(report,'browser_checks.json'),JSON.stringify({passed:true,scope:'Isolated local database; retained live agent snapshot; real HTTP edit endpoints',checks,errors},null,2));
    console.log(checks.join('\n'));
  } catch(e) {
    await page.screenshot({path:path.join(report,'browser-failure.png'),fullPage:true}).catch(()=>{});
    await fs.writeFile(path.join(report,'browser_checks.json'),JSON.stringify({passed:false,checks,errors,error:e.message},null,2));
    throw e;
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
