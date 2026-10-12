"""Real isolated Tk construction/editing audit. No network or personal state."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from PIL import ImageGrab

BASE=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]/'evidence'
sys.path[:0]=[str(BASE/'src'),str(BASE)]
checks=[];screens=[];units=[];errors=[]

def record(name,actual,expected=True,detail=None):
    checks.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected,detail=detail))

with tempfile.TemporaryDirectory(prefix='promptsmith-native-audit-') as isolation:
    os.environ['LOCALAPPDATA']=isolation
    for key in list(os.environ):
        if key.startswith('PROMPTSMITH_') or key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','GITHUB_TOKEN','GH_TOKEN'):
            os.environ.pop(key)
    import tkinter as tk
    import promptsmith.ui as ui
    from promptsmith.runtime_log import RuntimeLog
    from promptsmith.web_workspace import WorkspaceController
    from tests.test_final_delivery import confirmed_plan_session
    from promptsmith.finalization import build_final_draft,stage_final_draft
    ui.warm_local_skill_index=lambda *a:None
    logs=RuntimeLog(Path(isolation)/'PromptSmith/logs').start()
    root=tk.Tk();root.geometry('1440x810+0+0')
    app=ui.PromptSmithApp(root,runtime_log=logs)
    app._show_error=lambda title,text,**kw:errors.append(dict(title=title,text=text))
    view=WorkspaceController(app)
    app._install_session(confirmed_plan_session(),reason='native audit fixture')
    draft=build_final_draft(app.session);stage_final_draft(app.session,draft,expected_basis=draft['basis']);app.refresh()
    def pump(seconds=.15):
        end=time.monotonic()+seconds
        while time.monotonic()<end:root.update();time.sleep(.008)
    def descendants(widget):
        result=[]
        for w in widget.winfo_children():result.append(w);result+=descendants(w)
        return result
    def screenshot(widget,name):
        pump(); x=widget.winfo_rootx();y=widget.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+widget.winfo_width(),y+widget.winfo_height())).save(OUT/name)
        screens.append(name)
    try:
        root.deiconify();pump()
        for index in range(5):
            app.notebook.select(index);pump()
            tab=root.nametowidget(app.notebook.tabs()[index])
            for w in descendants(tab):
                kind=w.winfo_class()
                if kind not in ('Label','TLabel','Text','Canvas','TButton','Button','TEntry','Entry','TCombobox','Treeview','TCheckbutton','TSpinbox'):continue
                text=''
                try:text=str(w.cget('text'))
                except tk.TclError:pass
                units.append(dict(page=index,path=str(w),kind=kind,text=text,mapped=bool(w.winfo_ismapped()),
                    rect=[w.winfo_rootx(),w.winfo_rooty(),w.winfo_width(),w.winfo_height()],
                    key=next((k for k,v in app.widgets.items() if v is w),'')))
            record('Native notebook '+str(index)+' is selected and mapped',tab.winfo_ismapped()==1)
            screenshot(root,f'native-page-{index}.png')
        # Real projection of the busy integration button, not a made-up locked fixture.
        app.notebook.select(0);app.delivery_busy=True;app.refresh();pump()
        busy=view.snapshot()
        record('Real busy projection contains cancel_request',bool(busy['buttons'].get('cancel_request')),detail=busy['buttons'].get('cancel_request'))
        (OUT/'integration-busy-snapshot.json').write_text(json.dumps(busy,ensure_ascii=False,indent=2),encoding='utf-8')
        app.delivery_busy=False;app.refresh();pump()

        def drive_dialog(name,mode='save',invalid=False):
            def drive():
                dialogs=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
                if not dialogs:root.after(50,drive);return
                dialog=dialogs[-1];pump(.05)
                children=descendants(dialog);texts=[w for w in children if w.winfo_class()=='Text']
                for i,w in enumerate(texts):
                    w.delete('1.0','end');w.insert('1.0',('' if invalid and i==0 else '合成编辑 '+str(i)+'\n第二行👩🏽‍💻'))
                screenshot(dialog,name+'.png')
                record(name+' owns grab',root.grab_current() is dialog)
                if mode=='cancel':dialog.event_generate('<Escape>');root.after(50,lambda:dialog.destroy() if dialog.winfo_exists() else None);return
                button=next(w for w in children if w.winfo_class()=='TButton' and str(w.cget('text')).startswith('保存'))
                button.invoke()
                if invalid:
                    record(name+' invalid stays open with error',dialog.winfo_exists()==1 and bool(errors))
                    dialog.destroy()
            root.after(120,drive)
        drive_dialog('native-multitext-save')
        value=app._multi_text_dialog('合成需求编辑',[('goal','目标','原值'),('details','细节','原细节')])
        record('Multitext preserves multiline Unicode',value['goal'].endswith('第二行👩🏽‍💻'))
        drive_dialog('native-multitext-cancel','cancel')
        value=app._multi_text_dialog('合成取消编辑',[('goal','目标','原值')])
        record('Multitext cancel returns no write',value is None)
        step=app.session.plan['content']['steps'][0]
        drive_dialog('native-step-save')
        value=app._plan_step_dialog(step)
        record('Step save returns actual actions and stable links',bool(value['title']) and len(value['actions'])==2 and 'requirement_ids' in value)
        drive_dialog('native-step-invalid',invalid=True)
        record('Invalid step returns no committed value',app._plan_step_dialog(step) is None)
        work=next(iter(app.session.plan['content'].get('key_work_plan',[])),dict(title='合成关键工作',goal='核对界面',inputs=[],outputs=[],checkpoints=[],step_ids=[],requirement_ids=[],depends_on_key_work_ids=[]))
        drive_dialog('native-work-save')
        value=app._key_work_dialog(work)
        record('Key work save preserves input and dependency shape',len(value['checkpoints'])==2 and 'depends_on_key_work_ids' in value)
        drive_dialog('native-work-cancel','cancel')
        record('Key work cancellation does not commit',app._key_work_dialog(work) is None)
        # Debug actual Tk widget and archive contract.
        from promptsmith.debug_console import DebugConsole
        console=DebugConsole(root,logs,lambda:None)
        for n in [10,20,30,40,50]:logs.record('audit',n,'合成严重级别 '+str(n)+'\n合成堆栈')
        pump(.5);screenshot(console.window,'native-debug.png')
        record('Native Debug exposes all five severity tags',all(str(level) in console.text.tag_names() for level in [10,20,30,40,50]))
        console.close()
        record('Native diagnostics remain unsaved',not list((Path(isolation)/'PromptSmith/logs').glob('*.log')))
    finally:
        app.shutdown(wait=True);app.executor.shutdown(wait=True,cancel_futures=True);root.destroy();logs.close()

(OUT/'native-ui-observations.json').write_text(json.dumps(dict(checks=checks,units=units,screenshots=screens,
    captured_validation_errors=errors,environment='Windows/Tk8.6/current source/isolated synthetic session'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Native observations:',len(checks),'passed',sum(x['passed'] for x in checks),'differences',sum(not x['passed'] for x in checks))
