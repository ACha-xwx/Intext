"""Edit every native preference widget, save/reload, and reject invalid numbers."""
import json
import os
import sys
import tempfile
from pathlib import Path

BASE=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]/'evidence'
sys.path[:0]=[str(BASE/'src'),str(BASE)]
observations=[]
with tempfile.TemporaryDirectory(prefix='promptsmith-review-fields-') as directory:
    os.environ['LOCALAPPDATA']=directory
    for name in list(os.environ):
        if name.startswith('PROMPTSMITH_') or name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','GITHUB_TOKEN','GH_TOKEN'):
            os.environ.pop(name)
    import tkinter as tk
    import promptsmith.ui as ui
    from promptsmith.preferences import FIELDS,load_preferences
    ui.warm_local_skill_index=lambda *a:None
    root=tk.Tk();root.withdraw();app=ui.PromptSmithApp(root)
    app.api_key_var.set('')
    notices=[];app._show_error=lambda *a,**kw:notices.append(a)
    try:
        app.show_settings()
        for name,spec in FIELDS.items():
            if name=='debug_console_enabled':continue # Actual open/save/close already EV-007.
            widget=app.widgets['setting_'+name];kind=widget.winfo_class()
            old=app.preferences[name]
            if spec.choices:
                index=1 if len(spec.choices)>1 else 0
                widget.current(index);widget.event_generate('<<ComboboxSelected>>')
                expected=spec.choices[index]
            elif isinstance(spec.default,bool):
                widget.invoke();expected=not old
            else:
                if spec.minimum is not None: value=min(spec.maximum,max(spec.minimum,float(old)+1))
                elif name=='temperature':value='0.6'
                elif name=='top_p':value='0.8'
                elif name in ('session_directory','export_directory','extra_skill_roots'):value=str(Path(directory)/name)
                elif name=='skill_search_url':value='https://example.test/skills'
                elif name=='web_search_url':value='https://example.test/search?q={query}'
                else:value=str(old)
                if isinstance(spec.default,int):value=int(value)
                start='1.0' if kind=='Text' else 0
                widget.delete(start,'end');widget.insert(start,str(value))
                expected=value
            root.update_idletasks()
            saved=app.save_settings()
            loaded=load_preferences(app._preferences_path)[0]
            observations.append(dict(field=name,kind=kind,status='save_reload',passed=bool(saved and loaded[name]==expected),actual=loaded[name],expected=expected))
            if spec.minimum is not None:
                prior=app.preferences[name]
                widget.delete(0,'end');widget.insert(0,'invalid-number')
                rejected=app.save_settings() is False
                observations.append(dict(field=name,kind=kind,status='invalid_numeric',passed=rejected and app.preferences[name]==prior and bool(notices),actual=app.preferences[name],expected=prior))
                widget.delete(0,'end');widget.insert(0,str(prior))
    finally:
        app.shutdown(wait=True);app.executor.shutdown(wait=True,cancel_futures=True);root.destroy()
(OUT/'native-settings-fields.json').write_text(json.dumps(dict(environment='Real Tk widgets; isolated settings save/load; no key/API call',observations=observations),ensure_ascii=False,indent=2),encoding='utf-8')
print('Native setting fields:',len(observations),'observations;',sum(o['passed'] for o in observations),'passed')
