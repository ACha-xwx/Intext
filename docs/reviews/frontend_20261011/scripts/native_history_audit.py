"""Actual WebView2 bridge, two startups, isolated history; no model/network calls."""
import json,os,sys,tempfile,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]/"evidence"
sys.path.insert(0,str(BASE/'src'));sys.path.insert(0,str(BASE))
import webview
from promptsmith.session_history import SessionHistory
from promptsmith.session import SessionState
from tests.test_final_delivery import confirmed_plan_session
from promptsmith.finalization import build_final_draft,stage_final_draft,confirm_final
from promptsmith.runtime_log import RuntimeLog
import promptsmith.web_workspace as workspace
import promptsmith.ui as ui

SCRIPT=r'''(async()=>{
  const results=[];const delay=ms=>new Promise(r=>setTimeout(r,ms));
  const assert=(name,ok)=>{results.push({check:name,passed:!!ok});if(!ok)throw new Error(name);};
  const until=async test=>{for(let i=0;i<150;i++){if(await test())return;await delay(40);}throw new Error('timeout');};
  const call=async(action,data={})=>{const snap=await pywebview.api.snapshot(0);const result=await pywebview.api.dispatch(action,data,snap.state.stamp);if(!result.ok)throw new Error(result.error);await promptsmithView.poll();return result;};
  try{
    await until(()=>document.querySelectorAll('.history-row').length===3);
    assert('startup catalogue visible without opening record',!document.querySelector('#hero').hidden);
    const entries=(await pywebview.api.snapshot(0)).state.history.entries;
    const questions=entries.find(e=>e.title==='恢复逐题回答'),plan=entries.find(e=>e.title==='恢复确认方案'),final=entries.find(e=>e.title==='恢复最终提示');
    if(window.testRun===1){
      document.querySelector(`.history-row[data-id="${questions.id}"] .history-select`).click();
      await until(()=>document.querySelector('.answer-input')?.value==='预存回答');
      assert('click loads full question state and draft',document.querySelector('#message').value==='预存补充');
      const answer=document.querySelector('.answer-input');answer.value='实际WebView2修改的草稿';answer.dispatchEvent(new Event('input',{bubbles:true}));
      const input=document.querySelector('#message');input.value='实际WebView2补充草稿';input.dispatchEvent(new Event('input',{bubbles:true}));
      await delay(300);await promptsmithHistory.flushDrafts();
      await call('new');
      assert('new chat checkpoints clears old output and unlocks',!document.querySelector('#hero').hidden&&document.querySelector('#message').value==='');
      await call('history_open',{id:questions.id});
      assert('click resumes changed draft after switch',document.querySelector('.answer-input')?.value==='实际WebView2修改的草稿');
      await call('history_rename',{id:questions.id,title:'WebView已保存的对话'});await call('history_pin',{id:questions.id,pinned:true});
      const meta=(await pywebview.api.snapshot(0)).state.history.entries.find(e=>e.id===questions.id);
      assert('rename and pin reflected by real store',meta.title==='WebView已保存的对话'&&meta.pinned&&meta.group==='置顶');
      await call('history_open',{id:plan.id});
      assert('confirmed plan recovery permits next workflow step',(await pywebview.api.snapshot(0)).state.cards.some(c=>c.kind==='plan'&&c.status==='confirmed'));
      await call('history_open',{id:final.id});
      assert('confirmed prompt restored and copy enabled',(await pywebview.api.snapshot(0)).state.buttons.copy?.enabled&&document.querySelector('[data-action=copy]'));
      document.querySelector('#sidebar-toggle').click();await delay(350);
      assert('real engine horizontal collapse and controls visible',getComputedStyle(document.querySelector('.sidebar-tools')).flexDirection==='row'&&document.querySelector('#history-list').offsetParent===null);
      document.dispatchEvent(new KeyboardEvent('keydown',{key:'k',ctrlKey:true,bubbles:true}));
      assert('Ctrl K works in real engine',document.querySelector('#history-search-input')===document.activeElement);
    }else{
      const renamed=entries.find(e=>e.title==='WebView已保存的对话');assert('second startup sees saved rename and pin',renamed?.pinned);
      await call('history_open',{id:renamed.id});
      assert('restart resumes unsent answer and composer',document.querySelector('.answer-input')?.value==='实际WebView2修改的草稿'&&document.querySelector('#message').value==='实际WebView2补充草稿');
      await call('history_delete',{id:renamed.id});
      assert('active deletion creates clean usable workspace',!document.querySelector('#hero').hidden&&(await pywebview.api.snapshot(0)).state.history.entries.length===2);
    }
    window.testResult={checks:results,userAgent:navigator.userAgent};
  }catch(error){window.testResult={checks:results,error:error.stack};}
})();'''

with tempfile.TemporaryDirectory(prefix='promptsmith-native-history-') as isolation:
    os.environ['LOCALAPPDATA']=isolation
    for key in list(os.environ):
        if key.startswith('PROMPTSMITH_') or key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','GITHUB_TOKEN','GH_TOKEN'):os.environ.pop(key)
    ui.warm_local_skill_index=lambda *a:None
    store=SessionHistory()
    session=SessionState.new();session.set_task('恢复逐题回答')
    session.pending_questions=[dict(question_id='q1',gap_id=None,field='audience',scope='用户',text='主要用户是谁？',options=[],reason='',depends_on=[])]
    session.control['workspace_drafts']={'message':'预存补充','answers':{'q1':'预存回答'},'scroll':0}
    store.save(session.to_dict())
    plan=confirmed_plan_session();identity=store.save(plan.to_dict());store.rename(identity,'恢复确认方案')
    final=confirmed_plan_session();draft=build_final_draft(final);stage_final_draft(final,draft,expected_basis=draft['basis']);confirm_final(final)
    identity=store.save(final.to_dict());store.rename(identity,'恢复最终提示')
    original=webview.create_window
    for run in (1,2):
        result={};errors=[]
        def create(*a,**kw):
            window=original(*a,**kw)
            def loaded():
                try:
                    window.evaluate_js(f'window.testRun={run};')
                    window.evaluate_js(SCRIPT)
                    for i in range(160):
                        current=window.evaluate_js('window.testResult||null')
                        if current:result.update(current);break
                        time.sleep(.2)
                    else:errors.append('native script timed out')
                except Exception as exc:errors.append(repr(exc))
                finally:window.destroy()
            window.events.loaded+=loaded
            return window
        webview.create_window=create
        logs=RuntimeLog(Path(isolation)/'PromptSmith/logs').start()
        try:workspace.run_web_workspace(logs)
        finally:logs.close()
        result['errors']=errors
        result['logs_auto_written']=bool(list((Path(isolation)/'PromptSmith/logs').glob('*.log')))
        (OUT/f'native-run-{run}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        assert not result.get('error') and not errors and result.get('checks') and not result['logs_auto_written']
    assert len(SessionHistory().list())==2
