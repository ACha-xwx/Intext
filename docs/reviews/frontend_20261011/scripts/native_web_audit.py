"""Real WebView2 + Tk bridge. Synthetic task; no HTTP/model operations."""
import json, os, sys, tempfile, time, threading
from pathlib import Path
BASE=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]/"evidence"
sys.path.insert(0,str(BASE/'src'))
fixture=json.loads((OUT/'web-fixtures.json').read_text(encoding='utf-8'))
results={'main':None,'debug':None};errors=[];windows=[]
SCRIPT=r'''(async()=>{
 const delay=ms=>new Promise(r=>setTimeout(r,ms));
 const until=async condition=>{const end=performance.now()+9000;while(!condition()){if(performance.now()>end)throw Error('condition timeout');await delay(30);}};
 const checks=[],assert=(name,value)=>{checks.push({name,passed:!!value});if(!value)throw Error(name);};
 const metrics=[],frames=[];let sampling=true,previous=performance.now();
 function beat(t){if(!sampling)return;frames.push(t-previous);previous=t;requestAnimationFrame(beat);}requestAnimationFrame(beat);
 try{
  await until(()=>window.pywebview?.api&&document.querySelector('.trace'));
  const trace=document.querySelector('.trace'),outer=trace.querySelector(':scope>.reveal'),thought=trace.querySelector('.thought');
  trace.querySelector(':scope>button').click();await delay(900);
  for(let i=0;i<8;i++){
   const inner=i%2===0,target=inner?trace.querySelector('.trace-body>.reveal'):outer,button=inner?trace.querySelector('.trace-body>button'):trace.querySelector(':scope>button');
   const rows=[],start=performance.now();let active=true;
   function sample(t){if(!active)return;rows.push({t:t-start,h:target.getBoundingClientRect().height});requestAnimationFrame(sample);}requestAnimationFrame(sample);
   button.click();await delay(470);active=false;
   const changes=rows.filter((v,j)=>j===0||Math.abs(v.h-rows[j-1].h)>.01),gaps=changes.slice(1).map((v,j)=>v.t-changes[j].t);
   metrics.push({kind:inner?'trace_inner':'trace_outer',changes:changes.length,max_layout_gap_ms:Math.max(0,...gaps),rows});
  }
  assert('all reveal transitions have intermediate layouts',metrics.every(m=>m.changes>=10));
  assert('no >85ms layout gap in transitions',metrics.every(m=>m.max_layout_gap_ms<85));
  await command('settings');await until(()=>document.querySelector('#settings-page').hidden===false);
  assert('settings stays in browser, native window withdrawn',(await window.pywebview.api.snapshot(-1)).state.test_native_state==='withdrawn');
  const font=document.querySelector('#settings-field-font_size');font.value='13';font.dispatchEvent(new Event('input',{bubbles:true}));
  document.querySelector('#settings-key').value='disposable-webview-key';document.querySelector('#settings-key').dispatchEvent(new Event('input',{bubbles:true}));
  await window.promptsmithSettings.submit('settings_confirm');
  assert('model confirmation applies',window.promptsmithSettings.current.confirmed);
  assert('confirmation leaves non-model draft intact',font.value==='13'&&window.promptsmithSettings.dirty.has('font_size'));
  assert('key input cleared after submission',document.querySelector('#settings-key').value==='');
  await window.promptsmithSettings.submit('settings_save');await delay(250);
  assert('saved font reflected',Number(window.promptsmithSettings.current.values.font_size)===13);
  const s=window.promptsmithSettings.current;
  await command('settings_debug',{revision:s.revision,enabled:true});
  await delay(1100);
  await command('settings_back');await delay(250);
  const unicode='汉字👩🏽‍💻é𠮷\n'.repeat(3000);
  const view=new window.promptsmithView.TraceView({status:'working',reasoning:unicode,activities:[]});document.querySelector('#timeline').append(view.el);
  let updates=0,maxChunk=0,last=0,unicodeBroken=false;
  const observer=new MutationObserver(()=>{updates++;maxChunk=Math.max(maxChunk,view.text.data.length-last);last=view.text.data.length;unicodeBroken||=/[\uD800-\uDBFF]$/.test(view.text.data);});observer.observe(view.thought,{characterData:true,subtree:true});
  await until(()=>view.pending.length===0);observer.disconnect();
  assert('long Unicode thought drains progressively',updates>10&&maxChunk<unicode.length&&view.text.data===unicode&&!unicodeBroken);
  view.close();view.el.remove();
  sampling=false;
  window.nativeTestResult={checks,metrics,frames,userAgent:navigator.userAgent,unicode_updates:updates};
 }catch(error){sampling=false;window.nativeTestResult={checks,metrics,frames,error:error.stack};}
})();'''
DEBUG_SCRIPT=r'''(async()=>{
 const delay=ms=>new Promise(r=>setTimeout(r,ms));
 try{
  for(let i=0;i<100&&!window.pywebview?.api;i++)await delay(30);
  window.dispatchEvent(new ErrorEvent('error',{error:new Error('offline Debug browser diagnostic')}));await delay(200);
  await window.promptsmithDebug.poll();
  const before=await window.pywebview.api.snapshot(0);
  const unsaved=!before.path;
  document.querySelector('#clear').click();
  document.querySelector('#level').value='50';document.querySelector('#level').dispatchEvent(new Event('change'));
  const saved=await window.pywebview.api.save();await window.promptsmithDebug.poll();
  const after=await window.pywebview.api.snapshot(0);
  window.nativeDebugResult={unsaved,saved:saved.ok,after_saved_sequence:after.saved_sequence,clear_only_view:after.entries.length>0,own_error_logged:after.entries.some(e=>e.level===40&&e.text.includes('offline Debug browser diagnostic')),colors: [...document.styleSheets].some(s=>[...s.cssRules].some(r=>r.selectorText==='.log-warning')),font:getComputedStyle(document.querySelector('#log-lines')).fontSize};
 }catch(error){window.nativeDebugResult={error:error.stack};}
})();'''
with tempfile.TemporaryDirectory(prefix='promptsmith-native-acceptance-') as isolation:
 os.environ['LOCALAPPDATA']=isolation
 for key in list(os.environ):
  if key.startswith('PROMPTSMITH_') or key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY'):os.environ.pop(key)
 from promptsmith.runtime_log import RuntimeLog
 from promptsmith.ui import PromptSmithApp
 import promptsmith.ui as ui
 import promptsmith.web_workspace as workspace
 import webview
 class FixtureApp(PromptSmithApp):
  def __init__(self,*args,**kwargs):
   super().__init__(*args,**kwargs)
   self.api_base_var.set('https://example.invalid/v1');self.api_model_var.set('gpt-6.1-sol');self.api_key_var.set('offline-native-fixture');self.confirm_model_settings()
   self.widgets['task_text'].insert('1.0','重新设计 Python Tkinter 软件的 UI 页面，改进布局和元素样式');self._sync_input()
   self.session.pending_questions=[card['question'] for card in fixture['sample']['cards'] if card['kind']=='question']
   self.session.control['response_traces']=[card['trace'] for card in fixture['sample']['cards'] if card['kind']=='trace']
   self.refresh()
 ui.warm_local_skill_index=lambda *a:None
 ui.PromptSmithApp=FixtureApp
 original_snapshot=workspace.WorkspaceController.snapshot
 def snapshot(controller):
  state=original_snapshot(controller);state['test_native_state']=controller.app.root.state();return state
 workspace.WorkspaceController.snapshot=snapshot
 original_create=webview.create_window
 def create(*args,**kwargs):
  window=original_create(*args,**kwargs);windows.append(window)
  is_debug='Debug' in args[0]
  def loaded():
   try:
    window.evaluate_js(DEBUG_SCRIPT if is_debug else SCRIPT)
    for i in range(150):
     result=window.evaluate_js('window.nativeDebugResult||null' if is_debug else 'window.nativeTestResult||null')
     if result:
      results['debug' if is_debug else 'main']=result
      if not is_debug:window.destroy()
      return
     time.sleep(.25)
    errors.append('native script timed out')
    if not is_debug:window.destroy()
   except Exception as e:
    errors.append(repr(e))
    if not is_debug:window.destroy()
  window.events.loaded+=loaded
  return window
 webview.create_window=create
 logs=RuntimeLog(Path(isolation)/'PromptSmith/logs').start()
 for level in [10,20,30,40,50]:logs.record('fixture',level,'offline severity sample')
 try:
  workspace.run_web_workspace(logs)
  results['window_count']=len(windows);results['errors']=errors
  results['saved_archive_has_all_levels']=bool(logs.path) and all(level in logs.path.read_text(encoding='utf-8') for level in ['DEBUG','INFO','WARNING','ERROR','CRITICAL'])
 finally:logs.close()
(OUT/'native-web-checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in results.items() if k not in ('main',)},ensure_ascii=False))
print(json.dumps({k:v for k,v in (results['main'] or {}).items() if k not in ('metrics','frames')},ensure_ascii=False))
assert results['main'] and not results['main'].get('error') and not errors
assert results['debug'] and results['debug']['unsaved'] and results['debug']['saved'] and results['debug']['own_error_logged']
