"""Bounded repeat-render/disposal measurements; actual assets, mocked bridge."""
import json,time,statistics
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]/'evidence'
fixtures=json.loads((OUT/'fixtures.json').read_text(encoding='utf-8'));samples=[];checks=[];errors=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='chrome',headless=True);page=browser.new_page(viewport=dict(width=1440,height=810))
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto((BASE/'resources/ui/workspace/index.html').as_uri())
 page.evaluate('''s=>{window.auditState=s;window.pywebview={api:{diagnostic:async()=>true,snapshot:async()=>null,dispatch:async()=>({ok:true})}};window.dispatchEvent(new Event('pywebviewready'));promptsmithView.applySnapshot(s)}''',fixtures['empty'])
 def load(name):
  s=fixtures[name]
  return page.evaluate('''s=>{closePopup(true);const start=performance.now();window.auditState=s;promptsmithView.applySnapshot(s);document.body.offsetHeight;return performance.now()-start}''',s)
 for name in ['interview','skills','plan','final','empty']:load(name)
 page.wait_for_timeout(350)
 base=page.locator('*').count()
 for cycle in range(20):
  for name in ['interview','skills','plan','final','empty']:samples.append(dict(kind=name,ms=load(name)))
  page.wait_for_timeout(18)
 page.wait_for_timeout(350)
 checks.append(dict(name='20 full timeline cycles return to stable DOM count',passed=page.locator('*').count()==base,actual=page.locator('*').count(),expected=base))
 checks.append(dict(name='Empty timeline releases rendered traces',passed=page.evaluate('traces.size===0'),actual=page.evaluate('traces.size'),expected=0))
 for trigger in ['model-button','depth-button','category-button','file-button']:
  for i in range(5):
   page.locator('#'+trigger).click();page.wait_for_timeout(40);page.evaluate('closePopup(true)')
  checks.append(dict(name=trigger+' five closes remove floating DOM',passed=page.locator('.popup').count()==0,actual=page.locator('.popup').count(),expected=0))
 for i in range(5):
  page.locator('#history-search').click();page.wait_for_timeout(30);page.locator('.history-dialog .popup-close').click()
 checks.append(dict(name='History modal five closes remove overlay',passed=page.locator('.history-overlay').count()==0,actual=page.locator('.history-overlay').count(),expected=0))
 checks.append(dict(name='No JS exceptions during cycles',passed=not errors,actual=errors,expected=[]))
 browser.close()
values=sorted(s['ms'] for s in samples)
result=dict(environment='Chrome154 headless/1440x810/current assets/synthetic bridge; layout wall time not display FPS or long-term heap proof',checks=checks,samples=samples,metrics=dict(samples=len(values),median_ms=statistics.median(values),p95_ms=values[int(len(values)*.95)-1],max_ms=max(values)))
(OUT/'browser-lifecycle.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Browser lifecycle',len(checks),'passed',sum(c['passed'] for c in checks),result['metrics'])
