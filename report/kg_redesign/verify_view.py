"""Verify the proposed viewer and query traces with a headless renderer."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(__file__).resolve().parent
url=json.loads((OUT/'server.json').read_text())['url']
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1580,'height':1120})
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(url,wait_until='networkidle')
    assert page.locator('svg .node').count()==6
    assert 'PostgreSQL was replaced by SQLite' in page.locator('#answer').inner_text()
    page.screenshot(path=str(OUT/'overview.png'),full_page=True)
    page.locator('[data-question="database"]').click()
    assert 'SQLite' in page.locator('#answer').inner_text()
    assert 'Latest reported database in the described use: PostgreSQL' not in page.locator('#answer').inner_text()
    page.locator('[data-question="context"]').click()
    assert all(word in page.locator('#answer').inner_text() for word in ['Maya','Python','SQLite','not evidence of Maya'])
    assert page.locator('#answer .premise').count()==3
    page.screenshot(path=str(OUT/'inference.png'),full_page=True)
    page.locator('[data-question="skill"]').click()
    assert 'Unknown' in page.locator('#answer').inner_text()
    page.locator('[data-question="when"]').click()
    assert 'Exact date unknown' in page.locator('#answer').inner_text()
    page.locator('[data-question="database"]').click()
    page.locator('#step').fill('2')
    assert 'PostgreSQL' in page.locator('#answer').inner_text()
    assert 'SQLite' not in page.locator('#answer').inner_text()
    assert page.locator('svg .node').count()==4
    page.locator('#step').fill('3')
    page.locator('svg .edge[data-claim="C3"] text').first.click()
    assert 'historical' in page.locator('#detail').inner_text()
    page.locator('[data-view="claim"]').click()
    page.locator('#claimPicker button').filter(has_text='C4').click()
    assert 'Unknown; nullable' in page.locator('#detail').inner_text()
    assert 'S3' in page.locator('#detail').inner_text()
    page.screenshot(path=str(OUT/'claim.png'),full_page=True)
    page.locator('[data-view="storage"]').click()
    assert page.locator('#storage table tr').count()==6
    assert '22 typed edges' in page.locator('#storage').inner_text()
    page.locator('[data-view="overview"]').click()
    page.locator('[data-question="change"]').click()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    assert not errors,errors
    browser.close()
(OUT/'viewer_verified.json').write_text(json.dumps(dict(
    stage_changes=True,current_and_historical=True,claims_and_sources=True,composed_premises=True,
    unsupported_inferences_blocked=True,unknown_dates=True,storage_records=True,mobile_no_overflow=True,
    browser_errors=errors),indent=2))
print('Viewer verified: timeline, scoped replacement, evidence, inference boundaries, storage records, and mobile layout.')
