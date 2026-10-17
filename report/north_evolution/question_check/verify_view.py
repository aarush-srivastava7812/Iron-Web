"""Verify the question demo displays recorded outcomes and original evidence."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).resolve().parent
server=json.loads((OUT.parent/'server.json').read_text())['url'];url=server.replace('/index.html','/question_check/index.html')
checks=[];errors=[]
def check(name,ok):assert ok,name;checks.append({'name':name,'passed':True})
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True);page=browser.new_page(viewport={'width':1600,'height':1100})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url);page.wait_for_function('window.demoState !== undefined')
    check('All forty questions available',page.locator('#question option').count()==40)
    check('Six initial comparison rows displayed',page.locator('#scores tbody tr').count()==6)
    check('Three additional-question comparison rows displayed',page.locator('#holdout tbody tr').count()==3)
    page.screenshot(path=str(OUT/'comparison.png'))
    for index in range(40):
        page.locator('#question').select_option(str(index))
        names=page.locator('#system option').evaluate_all('(options) => options.map(o=>o.value)')
        for name in names:
            page.locator('#system').select_option(name)
            state=page.evaluate('window.demoState')
            expected=page.evaluate(f'window.demo.all[{index}].runs[{json.dumps(name)}].expanded.complete')
            check('Recorded outcome '+str(index)+' '+name,state['complete']==expected)
    page.locator('#question').select_option('16');page.locator('#system').select_option('prototype_kg')
    check('Original internship query shows missing companion','missing' in page.locator('#outcome').text_content().lower())
    page.locator('#system').select_option('improved_kg')
    check('Improved internship query shows complete evidence','All required' in page.locator('#outcome').text_content())
    page.locator('#returned details').first.locator('summary').click()
    check('Original wording is available',bool(page.locator('#returned .original').first.text_content()))
    page.locator('.comparison').screenshot(path=str(OUT/'internship_question.png'))
    page.locator('#question').select_option('26')
    check('Unsupported telephone query is not displayed as a correct answer','does not supply' in page.locator('#outcome').text_content())
    check('Reference answer is clearly labelled','not generated' in page.locator('.reference').text_content())
    page.set_viewport_size({'width':390,'height':844})
    dims=page.evaluate('({viewport:innerWidth,content:document.documentElement.scrollWidth})')
    check('Mobile page has no horizontal overflow',dims['content']<=dims['viewport'])
    page.screenshot(path=str(OUT/'mobile.png'))
    check('No browser runtime errors',not errors)
    browser.close()
(OUT/'viewer_verified.json').write_text(json.dumps({'url':url,'checks_passed':len(checks),'errors':errors},indent=2))
print(json.dumps({'url':url,'checks_passed':len(checks),'errors':errors},indent=2))
