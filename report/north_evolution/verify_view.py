"""Check rendered prototype behavior and browser/Python fuzzy-score parity."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from fuzzy import score

OUT=Path(__file__).resolve().parent
url=json.loads((OUT/'server.json').read_text())['url']
checks=[];errors=[]
def check(name,ok,evidence=None):
    assert ok,(name,evidence)
    checks.append({'name':name,'passed':True,'evidence':evidence})

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1080})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url);page.wait_for_selector('#score[data-value]')
    actual=page.evaluate('''() => window.prototype.m.facets.map(f => ({id:f.id,stored:f.score,rendered:window.prototype.fuzzy(f).score}))''')
    delta=max(abs(x['stored']-x['rendered']) for x in actual)
    check('All 143 browser defaults match persisted scores',len(actual)==143 and delta<0.000002,{'count':len(actual),'maximum_delta':delta})
    content=page.locator('#graph').text_content()
    check('Education confirms discipline without refreshing year',all(x in content for x in ['year: 3','not re-confirmed','CONFIRMS discipline only']),content)
    page.screenshot(path=str(OUT/'education.png'),full_page=True)
    facets=page.evaluate('() => window.prototype.m.facets')
    year=next(f for f in facets if f['slot']=='education.year')
    discipline=next(f for f in facets if f['slot']=='education.discipline' and f['batch']==1)
    page.locator('#facet').select_option(discipline['id'])
    recent=float(page.locator('#score').get_attribute('data-value'))
    page.locator('#stage').select_option('1')
    before=float(page.locator('#score').get_attribute('data-value'))
    check('Older receipt stage has no later discipline support',before<recent and 'Later study statements' not in page.locator('#graph').text_content(),{'before':before,'after':recent})
    page.locator('#stage').select_option('3')
    page.locator('#facet').select_option(year['id'])
    original=float(page.locator('#score').get_attribute('data-value'))
    page.locator('#days').fill('3650');page.locator('#days').dispatch_event('input')
    aged=float(page.locator('#score').get_attribute('data-value'))
    check('Ordinary memory decays in the inspector',aged<original,{'original':original,'aged':aged})
    page.locator('#conflict').fill('1');page.locator('#conflict').dispatch_event('input')
    page.locator('#pin').check()
    check('Protected memory remains exactly one despite age/conflict',float(page.locator('#score').get_attribute('data-value'))==1)
    page.screenshot(path=str(OUT/'protected.png'),full_page=True)
    page.locator('#pin').uncheck()
    check('Removing preview protection restores ordinary scoring',float(page.locator('#score').get_attribute('data-value'))<1)
    page.locator('#facet').select_option(year['id'])
    page.locator('[data-view="organization"]').click()
    page.locator('#stage').select_option('1')
    check('Earlier organization lens excludes the later internship','Completed IT-IoT internship' not in page.locator('#graph').text_content())
    page.locator('#stage').select_option('2')
    check('Organization match is unresolved before user confirmation','Candidate only' in page.locator('#graph').text_content())
    page.screenshot(path=str(OUT/'alias_before.png'),full_page=True)
    page.locator('#stage').select_option('3')
    text=page.locator('#graph').text_content()
    check('Confirmed alias preserves separate internship and employment',all(x in text for x in ['SAME_AS','Completed IT-IoT internship','Reported employment']),text)
    page.screenshot(path=str(OUT/'alias.png'),full_page=True)
    page.locator('[data-view="projects"]').click()
    check('Project relationships remain unresolved','POSSIBLE_RELATION' in page.locator('#graph').text_content())
    page.screenshot(path=str(OUT/'projects.png'),full_page=True)
    page.locator('#stage').select_option('1')
    check('Earlier project lens excludes reports not yet received','PrefIQ' not in page.locator('#graph').text_content() and 'Industrial Knowledge Platform' not in page.locator('#graph').text_content())
    page.locator('#stage').select_option('3')
    page.locator('[data-view="controls"]').click()
    text=page.locator('#graph').text_content()
    check('Accepted address change preserves both nodes with supersession',all(x in text for x in ['SUPERSEDES','Earlier claim retained','Synthetic new claim','0.000','1.000']) and 'CONTRADICTS' not in text,text)
    check('Address-change inspector shows the protected synthetic new node',float(page.locator('#score').get_attribute('data-value'))==1 and 'SYNTHETIC' in page.locator('#detail').text_content())
    page.locator('#fixture').select_option('1')
    text=page.locator('#graph').text_content()
    check('Correction has both contradiction and supersession edges',all(x in text for x in ['CONTRADICTS','SUPERSEDES','retracted','0.000','1.000']),text)
    check('Correction inspector agrees with the protected replacement',float(page.locator('#score').get_attribute('data-value'))==1 and page.locator('#pin').is_checked())
    page.screenshot(path=str(OUT/'correction.png'),full_page=True)
    page.locator('#fixture').select_option('2')
    text=page.locator('#graph').text_content()
    check('Unaccepted contradiction remains disputed with no supersession','CONTRADICTS' in text and 'SUPERSEDES' not in text and text.count('disputed')>=2,text)
    check('Unaccepted candidate has no protection in the inspector',abs(float(page.locator('#score').get_attribute('data-value'))-.1782)<0.000002 and not page.locator('#pin').is_checked())
    page.screenshot(path=str(OUT/'unresolved.png'),full_page=True)
    page.locator('[data-view="records"]').click()
    check('All 91 records are available',page.locator('#data table tr').count()==92)
    page.locator('[data-view="checks"]').click()
    check('All 14 graph behavior checks appear',page.locator('#data .test').count()==14)
    # Compare a wider input sweep, not only defaults. Explicit state guards are included.
    spec=[dict(quality=q,age_days=a,half_life=h,support=s,conflict=c,protected=pin,status=state)
          for q,a,h,s,c,pin,state in [(0,0,180,0,0,False,'active'),(.35,53,180,0,.85,False,'disputed'),
             (.85,180,180,.35,0,False,'active'),(.5,365,730,.8,.5,False,'active'),
             (1,36500,None,1,0,False,'active'),(.1,36500,180,0,1,True,'disputed'),
             (.85,0,180,0,0,True,'superseded')]]
    script='''(spec) => spec.map(x => window.prototype.fuzzy({status:x.status,historical:x.half_life===null,
        age_base:x.age_days,batch:2,quality:x.quality,half_life:x.half_life,support:x.support,
        conflict:x.conflict,protected:x.protected}).score)'''
    rendered=page.evaluate(script,spec)
    expected=[score(**x)['score'] for x in spec]
    check('Fuzzy engine parity includes conflict and state guards',max(abs(a-b) for a,b in zip(rendered,expected))<0.000002,{'browser':rendered,'python':expected})
    page.locator('[data-view="education"]').click()
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
    dimensions=page.evaluate('() => ({viewport:innerWidth,content:document.documentElement.scrollWidth})')
    check('Mobile layout avoids horizontal page overflow',dimensions['content']<=dimensions['viewport'],dimensions)
    check('No browser runtime errors',not errors,errors)
    browser.close()
(OUT/'viewer_verified.json').write_text(json.dumps({'url':url,'checks':checks},indent=2),encoding='utf-8')
print(json.dumps({'url':url,'checks_passed':len(checks),'browser_errors':errors,'maximum_default_delta':delta},indent=2))
