"""Additional audit evidence: clean small-window states, keyboard and stale jobs.

The UI assets are real; desktop actions are explicitly simulated. No model calls.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / 'evidence'
fixtures = json.loads((OUT / 'fixtures.json').read_text(encoding='utf-8'))
observations = []


def record(name, actual, expected=True, detail=None):
    observations.append(dict(name=name, actual=actual, expected=expected,
                             passed=actual == expected, detail=detail))


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport=dict(width=1440, height=810))
    page.goto((BASE / 'resources/ui/workspace/index.html').as_uri())
    page.evaluate('''s=>{
      window.auditState=s;window.auditVersion=1;window.calls=[];window.failAction=null;
      window.pywebview={api:{diagnostic:async()=>true,snapshot:async v=>v===auditVersion?null:{version:auditVersion,state:structuredClone(auditState)},dispatch:async(action,data)=>{
        calls.push({action,data});if(action===failAction)return {ok:false,error:'合成操作失败，请保留草稿重试'};
        if(action==='drafts')return {ok:true};
        if(action==='settings')auditState.page='settings';
        if(action==='settings_back')auditState.page='workspace';
        if(action==='new'){auditState=structuredClone(window.emptyState);auditState.session+='new';}
        auditVersion++;return {ok:true};
      }}};window.emptyState=structuredClone(s);window.dispatchEvent(new Event('pywebviewready'));
    }''', fixtures['empty'])
    page.wait_for_selector('.history-row')

    def load(kind, **changes):
        state = json.loads(json.dumps(fixtures[kind]))
        state.update(changes)
        page.evaluate('s=>{closePopup(true);auditState=s;auditVersion++;promptsmithView.applySnapshot(s)}', state)
        page.wait_for_timeout(120)

    def box(selector):
        return page.locator(selector).first.evaluate('e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}}')

    load('interview')
    page.evaluate("failAction='answer'")
    page.locator('.answer-input').first.fill('失败后保留👩🏽‍💻')
    page.locator('.answer-input').first.press('Enter')
    page.wait_for_timeout(240)
    record('Action-specific failure preserves answer draft', page.locator('.answer-input').first.input_value(), '失败后保留👩🏽‍💻')
    record('Action-specific failure offers next action', '请' in page.locator('#toast').inner_text(), detail=page.locator('#toast').inner_text())
    page.evaluate('failAction=null')

    load('empty')
    page.locator('#depth-button').click(); page.wait_for_timeout(450)
    page.locator('.menu-row').first.focus(); page.keyboard.press('ArrowDown')
    record('Depth menu ArrowDown advances', page.locator('.menu-row').nth(1).evaluate('e=>e===document.activeElement'))
    page.keyboard.press('Escape'); page.wait_for_timeout(250)
    record('Depth close focus returns trigger', page.locator('#depth-button').evaluate('e=>e===document.activeElement'))

    load('empty'); page.locator('#model-button').click(); page.wait_for_timeout(450)
    page.locator('.picker-search input').fill('GPT')
    n = page.evaluate('calls.filter(c=>c.action==="model").length')
    page.locator('.picker-search input').dispatch_event('keydown', dict(key='Enter', isComposing=True, keyCode=229))
    page.wait_for_timeout(180)
    record('Model search IME Enter must not select', page.evaluate('calls.filter(c=>c.action==="model").length') == n)

    for p in ['requirements', 'plan', 'summary']:
        load('plan'); page.locator('[data-panel='+p+']').click(); page.wait_for_timeout(450)
        record(p+' opening establishes panel focus', page.evaluate('!!document.activeElement.closest(".review-panel")'))
        record(p+' header advertises expansion', page.locator('[data-panel='+p+']').get_attribute('aria-expanded'), 'true')
    # Text is inserted with textContent; HTML-looking model output stays inert.
    load('final')
    page.evaluate("text=>{const s=structuredClone(auditState);s.cards.find(c=>c.kind==='result').text=text;auditState=s;promptsmithView.applySnapshot(s)}", '<img src=x onerror="window.auditXSS=1">\n# 合成标题\n<script>window.auditXSS=1</script>')
    record('Model prose cannot create executable HTML', page.evaluate('!window.auditXSS && !document.querySelector(".reading img")'))
    record('ATX heading becomes heading', page.locator('.reading h1').count() > 0)

    # Clean settings instance, no earlier draft/status. Native minimum-size contract.
    page.set_viewport_size(dict(width=720,height=440))
    load('empty', page='settings', font_size=18)
    page.evaluate('promptsmithHistory.setCollapsed(true)'); page.wait_for_timeout(450)
    sizes = {}
    for cat in ['模型','Skill 搜索','界面','会话与导出','诊断']:
        page.locator('.settings-tabs').get_by_text(cat,exact=True).click()
        sizes[cat] = {'scroll':box('.settings-scroll'),'footer':box('.settings-footer'),
                      'save':box('.settings-footer .actions button:last-child')}
        record('Clean 720x440/font18 '+cat+' readable form area', sizes[cat]['scroll']['height'] >= 40, detail=sizes[cat])
    page.screenshot(path=str(OUT/'clean-small-settings.png'))

    for font in [12,18]:
        for collapsed in [False,True]:
            load('empty', font_size=font)
            page.evaluate('v=>promptsmithHistory.setCollapsed(v)',collapsed);page.wait_for_timeout(450)
            page.locator('#model-button').click();page.wait_for_timeout(450)
            geometry={k:box(k) for k in ['.picker','.picker-search input','[data-provider=OpenAI]','[data-provider=DeepSeek]']}
            record(f'Picker full bounds font{font}/collapsed{collapsed}', geometry['.picker']['y']>=0 and geometry['.picker']['bottom']<=440, detail=geometry)
            page.screenshot(path=str(OUT/f'picker-bounds-f{font}-c{int(collapsed)}.png'))
    page.set_viewport_size(dict(width=1440,height=810))
    load('interview')
    page.evaluate('promptsmithHistory.setCollapsed(false)');page.wait_for_timeout(400)
    # Rapid reversible disclosure, then cleanup. This is a lab trace, not 180Hz proof.
    for i in range(20):
        page.locator('.trace>button').click();page.wait_for_timeout(24)
    page.wait_for_timeout(500)
    record('Rapid inverse trace transitions preserve final closed state', not page.locator('.trace>.reveal').evaluate('e=>e.classList.contains("open")'))
    load('empty')
    record('Session switch removes former trace nodes', page.locator('.trace').count(),0)

    # History dialogs: focus boundary and empty validation, not real Windows IME.
    page.keyboard.press('Control+k');page.wait_for_timeout(120)
    page.locator('#history-search-input').fill('绝无匹配')
    record('History no match has explanation', bool(page.locator('.history-empty').inner_text()))
    page.keyboard.press('Escape')
    page.locator('.history-row').first.hover();page.locator('.history-more').first.click()
    page.locator('.history-menu button').first.click()
    page.locator('.history-dialog input').fill('');page.get_by_text('保存',exact=True).click()
    record('Blank rename stays open with field error', page.locator('.history-dialog').is_visible() and bool(page.locator('.dialog-error').inner_text()))
    page.keyboard.press('Escape')
    record('Rename cancel restores meaningful focus', page.evaluate('document.activeElement!==document.body'))
    browser.close()

(OUT/'browser-more.json').write_text(json.dumps(dict(observations=observations,settings_geometry=sizes,
    environment='Chrome154/headless/current assets/synthetic bridge; IME event injection'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Additional DOM:',len(observations),'passed',sum(o['passed'] for o in observations),'differences',sum(not o['passed'] for o in observations))
