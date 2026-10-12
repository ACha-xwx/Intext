"""DOM audit against real UI assets with explicitly simulated desktop bridge."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]/'evidence'
fixtures=json.loads((OUT/'fixtures.json').read_text(encoding='utf-8'))
observations=[]; errors=[]; screenshots=[]
def record(name,value,expected=True,detail=None):
    observations.append(dict(name=name,actual=value,expected=expected,passed=value==expected,detail=detail))

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport=dict(width=1440,height=810))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((BASE/'resources/ui/workspace/index.html').as_uri())
    page.evaluate('''s=>{
      window.auditState=s;window.auditCalls=[];window.auditVersion=1;window.auditFail=false;
      window.pywebview={api:{diagnostic:async()=>true,snapshot:async v=>v===auditVersion?null:{version:auditVersion,state:structuredClone(auditState)},dispatch:async(action,data)=>{
        auditCalls.push({action,data});if(auditFail)return {ok:false,error:'合成操作失败，保留数据重试'};
        const s=auditState;if(action==='drafts')return {ok:true};
        if(action==='settings')s.page='settings';if(action==='settings_back')s.page='workspace';
        if(action==='effort')s.effort=data.value;if(action==='model')s.model=data.id;
        if(action==='depth')s.depth=data.value;if(action==='category')s.category=data.value;
        if(action==='settings_save'){s.settings.values=data.values;s.font_size=Number(data.values.font_size);s.theme=data.values.composer_theme;}
        if(['settings_save','settings_confirm','settings_test','settings_models'].includes(action)){s.settings.connection=data.connection;s.settings.revision+='x';}
        if(action==='history_rename')s.history.entries.find(e=>e.id===data.id).title=data.title;
        if(action==='history_pin')s.history.entries.find(e=>e.id===data.id).pinned=data.pinned;
        if(action==='history_delete')s.history.entries=s.history.entries.filter(e=>e.id!==data.id);
        if(action==='new'){s.session+='x';s.cards=[{kind:'welcome',key:'welcome'}];s.drafts={};s.locked=false;}
        auditVersion++;return {ok:true,data:action.startsWith('settings_')?{settings:structuredClone(s.settings)}:['model','effort'].includes(action)?{model:s.model,effort:s.effort}:null};
      }}};window.dispatchEvent(new Event('pywebviewready'));
    }''',fixtures['empty'])
    page.wait_for_selector('#history-list .history-row')
    def load(kind,**changes):
        state=json.loads(json.dumps(fixtures[kind]));state.update(changes)
        page.evaluate('s=>{closePopup(true);auditState=s;auditVersion++;promptsmithView.applySnapshot(s)}',state)
        page.wait_for_timeout(100)
    def shot(name):
        filename=name+'.png';page.screenshot(path=str(OUT/filename));screenshots.append(filename)
    record('Hero centered and visible',page.locator('#hero').is_visible())
    record('Empty send disabled',page.locator('#send').is_disabled())
    record('Six exclusive history groups',page.locator('.history-group h2').all_text_contents(),['置顶','今天','昨天','七天内','30天内','更早'])
    shot('workspace-light')
    page.locator('#message').fill('目标\n补充👩🏽‍💻');page.locator('#message').press('Shift+Enter')
    record('Composer Shift Enter keeps newline',page.locator('#message').input_value().endswith('\n'))
    before=page.evaluate('auditCalls.length')
    page.locator('#message').dispatch_event('keydown',dict(key='Enter',isComposing=True,keyCode=229))
    record('Composer IME Enter does not send',page.evaluate('auditCalls.length')==before)
    page.locator('#model-button').click();page.wait_for_timeout(420)
    record('Picker 5 provider tabs',page.locator('[data-provider]').count(),5)
    record('Picker 8 OpenAI presets',page.locator('.model-row').count(),8)
    record('Picker unnamed dialog',page.locator('.picker').evaluate('e=>!!(e.getAttribute("aria-label")||e.getAttribute("aria-labelledby"))'),True)
    page.locator('[data-provider=DeepSeek]').click()
    record('DeepSeek two models',page.locator('.model-row').count(),2)
    record('DeepSeek no image icons',page.locator('.model-row .capability.image').count(),0)
    page.locator('.picker-search input').fill('不匹配名称');record('Model no-match recovery',page.locator('.models').inner_text(),'没有匹配的模型。')
    page.locator('.clear-search').click();page.locator('[data-effort=high]').focus();page.keyboard.press('ArrowRight');page.wait_for_timeout(200)
    record('Radio keyboard reaches max',page.locator('[data-effort=max]').get_attribute('aria-checked'),'true')
    shot('picker-light')
    page.keyboard.press('Escape');page.wait_for_timeout(300)
    record('Picker close returns focus to trigger',page.locator('#model-button').evaluate('e=>e===document.activeElement'))

    load('interview')
    page.locator('.trace>button').click();page.wait_for_timeout(1600)
    record('Long thought eventually drains',page.locator('.thought').inner_text()==fixtures['interview']['cards'][1]['trace']['reasoning'].replace('\n\n','\n'))
    record('Thought owns wheel scrolling',page.locator('.thought').evaluate('e=>getComputedStyle(e).overscrollBehaviorY'), 'contain')
    before=page.locator('#viewport').evaluate('e=>e.scrollTop');page.locator('.thought').hover();page.mouse.wheel(0,-400);page.wait_for_timeout(100)
    record('Thought wheel leaves page scroll unchanged',page.locator('#viewport').evaluate('e=>e.scrollTop')==before)
    page.locator('.trace>button').click();page.wait_for_timeout(450)
    page.locator('.trace>button').focus();page.keyboard.press('Tab')
    record('Collapsed trace excludes hidden descendants from Tab',page.evaluate('!document.activeElement.closest(".trace .reveal:not(.open)")'))
    load('interview');q=page.locator('.answer-input').first;q.fill('逐题回答');q.press('Shift+Enter')
    record('Answer Shift Enter newline',q.input_value(),'逐题回答\n')
    page.evaluate('auditFail=true');q.press('Enter');page.wait_for_timeout(250)
    record('Failed answer preserves draft',q.input_value(),'逐题回答\n')
    record('Failed action exposes next step',page.locator('#toast').inner_text(),'合成操作失败，保留数据重试')
    page.evaluate('auditFail=false')
    load('interview',locked=True)
    record('Locked state disables editing/send',page.locator('.answer-input').first.is_disabled() and page.locator('#send').is_disabled())
    record('Locked model request has visible cancel control',page.locator('button').filter(has_text='取消本次').count()>0)
    shot('interview-busy')

    load('plan')
    for kind in ['requirements','plan','summary']:
        page.locator('[data-panel='+kind+']').click();page.wait_for_timeout(420)
        record(kind+' panel visible',page.locator('.review-panel').is_visible())
        record(kind+' panel has accessible name',page.locator('.review-panel').evaluate('e=>!!(e.getAttribute("aria-label")||e.getAttribute("aria-labelledby"))'))
        if kind=='requirements':
            record('Requirement selectable rows keyboard reachable',page.locator('.review-panel tbody tr').evaluate_all('rows=>rows.length>0&&rows.every(r=>r.tabIndex>=0||r.querySelector("button,input"))'))
            page.locator('.review-panel tbody tr').first.click();page.wait_for_timeout(80)
            record('Requirement selection reveals full text',bool(page.locator('.detail').inner_text()))
        if kind=='plan':
            record('Plan headings collapse to details',page.locator('.review-panel details').count()>0)
            page.locator('.review-panel summary').first.click();record('Plan disclosure opens',page.locator('.review-panel details').first.get_attribute('open') is not None)
        shot('panel-'+kind);page.locator('.popup-close').click();page.wait_for_timeout(250)
    load('final');page.locator('.message').filter(has=page.locator('[data-action=copy]')).get_by_text('语气和附注',exact=True).click();page.wait_for_timeout(420)
    record('Result options stay in current workspace',page.locator('.review-panel select').is_visible() and page.locator('#viewport').is_visible())
    record('Final stage contains no pending question cards',page.locator('.answer-input').count(),0)
    shot('panel-result');page.locator('.popup-close').click();page.wait_for_timeout(250)
    load('skills')
    record('Skill local and online remain together',page.locator('.table-wrap').last.inner_text().find('frontend-design')>=0 and 'review-frontend-production' in page.locator('.table-wrap').last.inner_text())
    record('Selected Skill action disabled',page.get_by_text('已选中该 Skill',exact=True).is_disabled())
    record('Selected Skill cancel offered',page.get_by_text('取消选用',exact=True).is_visible())
    shot('skills-light')
    load('empty')
    for id in ['depth-button','category-button','file-button']:
        page.locator('#'+id).click();page.wait_for_timeout(420)
        record(id+' options visible',page.locator('.popup button').count()>0)
        page.keyboard.press('Escape');page.wait_for_timeout(250)
    page.locator('.history-row').first.hover();page.locator('.history-more').first.click();page.wait_for_timeout(420)
    record('History menu arrow navigation',page.locator('.history-menu button').first.evaluate('e=>e===document.activeElement'))
    page.keyboard.press('ArrowDown');record('History menu second item focus',page.locator('.history-menu button').nth(1).evaluate('e=>e===document.activeElement'))
    page.keyboard.press('Escape');page.wait_for_timeout(250)
    page.keyboard.press('Control+k');page.wait_for_timeout(250)
    record('History modal has explicit accessible name',page.locator('.history-dialog').get_attribute('aria-label'),'搜索历史会话')
    page.locator('#history-search-input').fill('资料');record('History query filters metadata',page.locator('.history-search-results button').count(),1)
    before=page.evaluate('auditCalls.filter(c=>c.action==="history_open").length')
    page.locator('#history-search-input').dispatch_event('keydown',dict(key='Enter',isComposing=True,keyCode=229));page.wait_for_timeout(120)
    record('History search IME Enter must not open record',page.evaluate('auditCalls.filter(c=>c.action==="history_open").length')==before)
    page.keyboard.press('Escape')
    page.locator('.history-row').first.hover();page.locator('.history-more').first.click();page.locator('.history-menu button').first.click()
    page.locator('.history-dialog input').fill('新名称');before=page.evaluate('auditCalls.filter(c=>c.action==="history_rename").length')
    page.locator('.history-dialog input').dispatch_event('keydown',dict(key='Enter',isComposing=True,keyCode=229));page.wait_for_timeout(200)
    record('Rename IME Enter must not save',page.evaluate('auditCalls.filter(c=>c.action==="history_rename").length')==before)
    page.keyboard.press('Escape')
    page.locator('.history-row').nth(1).hover();page.locator('.history-more').nth(1).click();page.locator('.history-menu button').last.click()
    record('Delete requires explicit confirmation',page.locator('.history-dialog').is_visible() and page.locator('.history-row').count()==6)
    page.get_by_text('取消',exact=True).click();record('Cancel delete preserves records',page.locator('.history-row').count(),6)

    for theme in ['light','dark']:
        load('empty',theme=theme,page='settings')
        for category in ['模型','Skill 搜索','界面','会话与导出','诊断']:
            page.locator('.settings-tabs').get_by_text(category,exact=True).click()
            record(theme+' '+category+' settings controls labeled',page.locator('.settings-form:not([hidden]) input,.settings-form:not([hidden]) select,.settings-form:not([hidden]) textarea').evaluate_all('cs=>cs.every(c=>c.labels.length>0)'))
            record(theme+' '+category+' save reachable',page.get_by_text('保存设置',exact=True).is_visible())
            shot('settings-'+theme+'-'+str(['模型','Skill 搜索','界面','会话与导出','诊断'].index(category)))
        page.locator('.settings-tabs').get_by_text('模型',exact=True).focus();page.keyboard.press('ArrowRight')
        record(theme+' settings Tabs ArrowRight selects next',page.locator('.settings-tabs [aria-selected=true]').inner_text(),'Skill 搜索')
        page.locator('.settings-tabs').get_by_text('模型',exact=True).click()
        model=page.locator('#settings-field-connection-model');model.fill('edited-model');page.evaluate('auditVersion++;promptsmithView.poll()');page.wait_for_timeout(150)
        record(theme+' background snapshot retains settings draft',model.input_value(),'edited-model')
    # Max supported font + minimum supported window, both rail modes.
    page.set_viewport_size(dict(width=720,height=440))
    for font in [12,18]:
        for collapsed in [True,False]:
            load('empty',font_size=font,page='workspace');page.evaluate('v=>promptsmithHistory.setCollapsed(v)',collapsed);page.wait_for_timeout(450)
            record(f'720x440 font={font} collapsed={collapsed} no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            record(f'720x440 font={font} collapsed={collapsed} header fits',page.locator('#settings').evaluate('e=>e.getBoundingClientRect().right<=innerWidth'))
            shot(f'small-f{font}-c{int(collapsed)}')
            page.locator('#model-button').click();page.wait_for_timeout(430)
            record(f'720x440 font={font} picker contains effort controls',page.locator('[data-effort=max]').evaluate('e=>{const r=e.getBoundingClientRect();return r.bottom<=innerHeight&&r.top>=0}'))
            shot(f'small-picker-f{font}-c{int(collapsed)}');page.keyboard.press('Escape');page.wait_for_timeout(250)
    load('empty',page='settings',font_size=18);page.evaluate('promptsmithHistory.setCollapsed(true)');page.wait_for_timeout(450)
    for cat in ['模型','Skill 搜索','界面','会话与导出','诊断']:
        page.locator('.settings-tabs').get_by_text(cat,exact=True).click()
        record('small max font '+cat+' footer not covering form',page.locator('.settings-scroll').evaluate('e=>e.getBoundingClientRect().height>40'))
    shot('small-settings-max-font')
    page.emulate_media(reduced_motion='reduce')
    record('Reduced motion removes transitions',page.locator('#sidebar').evaluate('e=>parseFloat(getComputedStyle(e).transitionDuration)<.01'))

    # Independent Debug, simulated API, including failure then recovery.
    debug=browser.new_page(viewport=dict(width=1120,height=640));debug.goto((BASE/'resources/ui/workspace/debug.html').as_uri())
    debug.evaluate('''()=>{window.failSync=false;window.saved=false;window.pywebview={api:{diagnostic:async()=>true,snapshot:async()=>{if(failSync)throw Error('offline test');return {preferences:{font_size:12,composer_theme:'dark',debug_history:1500,debug_lines:6000,debug_level:'全部'},preference_revision:1,sequence:4,cached:4,saved_sequence:saved?4:0,path:saved?'synthetic.log':'',error:'',directory_exists:saved,entries:window.sent?[]:(window.sent=true,[{id:1,level:10,text:'DEBUG 样本'},{id:2,level:20,text:'INFO 样本'},{id:3,level:30,text:'WARN 样本'},{id:4,level:40,text:'ERROR 堆栈\\nTraceback 合成测试'}])}},save:async()=>{saved=true;return {ok:true}},open_directory:async()=>({ok:true})}};window.dispatchEvent(new Event('pywebviewready'))}''')
    debug.wait_for_selector('.log-error')
    for cls in ['debug','info','warning','error']:record('Debug '+cls+' severity class exists',debug.locator('.log-'+cls).count(),1)
    record('Debug save initially opt-in','未保存' in debug.locator('#save-status').inner_text())
    debug.locator('#clear').click();record('Debug clear only displayed logs',debug.locator('.log-line').count(),0)
    debug.locator('#save').click();debug.wait_for_timeout(250);record('Debug manual save visible', '已保存' in debug.locator('#save-status').inner_text())
    debug.evaluate('failSync=true;promptsmithDebug.poll()');debug.wait_for_timeout(180);record('Debug failure visible',debug.locator('#debug-error').is_visible())
    debug.evaluate('failSync=false;promptsmithDebug.poll()');debug.wait_for_timeout(180);record('Debug successful synchronization clears stale error',not debug.locator('#debug-error').is_visible())
    debug.screenshot(path=str(OUT/'debug-dark.png'));screenshots.append('debug-dark.png')
    record('No uncaught JS exceptions',errors,[])
    (OUT/'browser-observations.json').write_text(json.dumps(dict(browser=browser.version,source='current worktree',data='synthetic Python projection + simulated bridge',observations=observations,errors=errors,screenshots=screenshots),ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print('DOM observations:',len(observations),'passed',sum(x['passed'] for x in observations),'differences',sum(not x['passed'] for x in observations))
