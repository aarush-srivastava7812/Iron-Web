const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage();
  const report = path.resolve('report/interior_ui_20261017');
  await fs.mkdir(report, {recursive: true});
  const errors = [], checks = [];
  page.on('pageerror', e => errors.push(e.message));
  const routes = ['packages','hotels','tours','destination/Darjeeling','package/Kashmir','planner','flights','about','contact','privacy','login','dashboard','booking?kind=package&id=1'];
  try {
    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      for (const route of routes) {
        await page.goto('http://127.0.0.1:8088/#' + route);
        await page.locator('main h1, main h2').first().waitFor();
        const result = await page.evaluate(() => ({width: innerWidth, content: document.documentElement.scrollWidth, hero: !!document.querySelector('.interior-hero-copy')}));
        assert.ok(result.content <= result.width + 1, `${route} at ${width}: overflow ${result.content}`);
        if (!route.startsWith('booking')) assert.ok(result.hero, `Missing shared hero on ${route}`);
        checks.push({route, width, overflow: false});
        if ([1440,390].includes(width) && ['destination/Darjeeling','hotels','planner','login','contact','flights','dashboard'].includes(route)) {
          await page.evaluate(async () => { await Promise.all([...document.querySelectorAll('main img')].map(img => img.decode().catch(() => {}))); });
          await page.screenshot({path: path.join(report, route.replace(/\//g,'-') + '-' + width + '.png'), fullPage: true});
        }
      }
    }
    assert.deepEqual(errors, []);
    await fs.writeFile(path.join(report,'checks.json'),JSON.stringify({passed: true, checks, errors},null,2));
    console.log(`Passed ${checks.length} route/viewport checks; no browser errors.`);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
