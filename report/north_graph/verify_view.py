"""Headless visual and interaction checks of the local comparison artifact."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).resolve().parent
url=json.loads((OUT/'server.json').read_text())['url']
data=json.loads((OUT/'graph.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1160})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url,wait_until='networkidle')
    assert page.locator('svg .node').count()==7
    assert 'Map rebuilding stays inactive' in page.locator('#case').inner_text()
    page.screenshot(path=str(OUT/'revised.png'),full_page=True)
    page.locator('#v1').click()
    assert str(data['v1']['meta']['nodes'])+' stored nodes' in page.locator('#stats').inner_text()
    assert page.locator('svg .node').count()>300
    page.screenshot(path=str(OUT/'first.png'),full_page=True)
    page.locator('[data-case="score"]').click()
    assert 'all six score candidates' in page.locator('#case').inner_text()
    assert 'character-sheet score' in page.locator('#detail').inner_text()
    page.locator('#v2').click()
    page.locator('#policy').click()
    assert 'Map rebuilding applies' in page.locator('#case').inner_text()
    assert 'trigger' in page.locator('#detail').inner_text()
    assert 'P06' in page.locator('#detail').inner_text()
    page.screenshot(path=str(OUT/'policy.png'),full_page=True)
    page.locator('[data-case="debug_simple"]').click()
    assert 'Map rebuilding stays inactive' in page.locator('#case').inner_text()
    page.locator('[data-domain="Self Concept"]').click()
    page.locator('#context').select_option('ctx_Self_Concept_character_sheet')
    assert page.locator('svg .node').count()==8
    page.get_by_role('button',name='Mind: 88 in the character sheet',exact=True).click()
    assert 'Record, roles, framework, and evidence' in page.locator('#viewTitle').inner_text()
    assert page.locator('svg .node').count()==5
    assert '88 character-sheet score' in page.locator('#detail').inner_text()
    assert 'S08' in page.locator('#detail').inner_text()
    page.screenshot(path=str(OUT/'framework.png'),full_page=True)
    page.locator('[data-domain="Profile"]').click()
    page.locator('#context').select_option('ctx_Profile_inditech')
    page.get_by_role('button',name='Works at Inditech Electrosystems',exact=True).click()
    assert 'F04' in page.locator('#detail').inner_text()
    assert 'REFERENCES: employer' in page.locator('svg').text_content()
    page.screenshot(path=str(OUT/'professional.png'),full_page=True)
    page.locator('[data-case="employer"]').click()
    assert 'Priyakanthji' in page.locator('#detail').inner_text()
    page.locator('[data-case="mechanism"]').click()
    assert 'not a command' in page.locator('#case').inner_text()
    page.locator('[data-case="date"]').click()
    assert 'current state unverified' in page.locator('#case').inner_text()
    page.locator('[data-case="duplicate"]').click()
    assert 'P01' in page.locator('#detail').inner_text() and 'C02' in page.locator('#detail').inner_text()
    page.get_by_role('button',name='Where the first model loses meaning',exact=True).click()
    assert page.locator('#checks .check').count()==10
    page.get_by_role('button',name='Scale checks',exact=True).click()
    assert '10000' in page.locator('#scale').inner_text()
    assert 'No storage failure was observed' in page.locator('#scale').inner_text()
    page.screenshot(path=str(OUT/'scale.png'),full_page=True)
    page.locator('#home').click()
    page.locator('[data-case="debug_simple"]').click()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    assert not errors,errors
    browser.close()
(OUT/'viewer_verified.json').write_text(json.dumps(dict(first_and_revised_graphs=True,policy_conditions=True,framework_binding=True,
    client_employer_distinction=True,attribution_and_dates=True,all_checks_and_scale=True,mobile_no_overflow=True,browser_errors=errors),indent=2))
print('Comparison viewer verified: graph modes, conditional policies, scores, roles, provenance, dates, scale, and mobile layout.')
