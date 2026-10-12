"""Supplement explicit native controls and callbacks in disposable local state.

Dialogs are real Tk except callback-only plan edits explicitly marked below.
No production settings, external services, or paid models are used.
"""
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path

BASE = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / 'evidence'
sys.path[:0] = [str(BASE/'src'), str(BASE)]
observations = []

def record(name, value, instances, detail=''):
    observations.append(dict(name=name, passed=bool(value), instance_ids=instances,
                             detail=detail, actual=value, expected=True))

with tempfile.TemporaryDirectory(prefix='promptsmith-review-supplement-') as directory:
    os.environ['LOCALAPPDATA'] = directory
    for key in list(os.environ):
        if key.startswith('PROMPTSMITH_') or key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','GITHUB_TOKEN','GH_TOKEN'):
            os.environ.pop(key)
    import tkinter as tk
    from tkinter import simpledialog
    import promptsmith.ui as ui
    from tests.test_final_delivery import confirmed_plan_session
    ui.warm_local_skill_index = lambda *args: None
    root = tk.Tk()
    root.geometry('1440x810+0+0')
    app = ui.PromptSmithApp(root)
    messages=[]
    app._show_info=lambda *a,**kw: messages.append(a)
    app._show_error=lambda *a,**kw: messages.append(a)
    def pump(seconds=.06):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            root.update();time.sleep(.004)
    def fresh():
        app._install_session(confirmed_plan_session(),reason='isolated native review')
        app.refresh();pump()
    def descendants(w):
        result=[]
        for child in w.winfo_children(): result.append(child);result.extend(descendants(child))
        return result
    try:
        fresh();app.show_workspace(1);app.widgets['plan_editor_panel']._show(True);pump()
        record('Native plan editor explicitly expands',app.widgets['plan_steps_tree'].winfo_ismapped(),['CMP-244','CMP-259'])
        goal=app.widgets['plan_goal_text'];goal.delete('1.0','end');goal.insert('1.0','合成目标修改')
        app.save_plan_goal()
        record('Goal callback invalidates plan confirmation',app.session.plan['content']['goal']['summary']=='合成目标修改' and app.session.plan['status']!='confirmed',['CMP-240','CMP-241'])
        fresh();before=deepcopy(app.session.to_dict());old_multi=app._multi_text_dialog
        app._multi_text_dialog=lambda *a,**kw: None;app.edit_plan_goal_details()
        record('Audience/scope cancel leaves session intact',app.session.to_dict()==before,['CMP-242'])
        app._multi_text_dialog=lambda *a,**kw: dict(audience='合成受众',scope='合成范围');app.edit_plan_goal_details()
        record('Audience/scope callback saves only explicit values',app.session.plan['content']['goal']['audience']=='合成受众',['CMP-242'], 'Dialog return simulated; actual fields separately tested in native-ui-audit.')
        app._multi_text_dialog=old_multi
        fresh();tree=app.widgets['plan_steps_tree'];first=tree.get_children()[0];tree.selection_set(first)
        old_step=app._plan_step_dialog
        app._plan_step_dialog=lambda step: {k:deepcopy(step[k]) for k in ('title','purpose','inputs','actions','outputs','completion_criteria','depends_on_step_ids','requirement_ids')} | dict(title='合成步骤编辑')
        app.edit_selected_plan_step()
        record('Selected-step callback retains stable id',app.session.plan['content']['steps'][0]['step_id']==first and app.session.plan['content']['steps'][0]['title']=='合成步骤编辑',['CMP-244','CMP-245'], 'Dialog return simulated; actual dialog save/error in EV-010.')
        fresh();tree=app.widgets['plan_steps_tree'];tree.selection_set(tree.get_children()[0]);before=deepcopy(app.session.to_dict())
        app._plan_step_dialog=lambda step: None;app.edit_selected_plan_step();app.add_plan_step()
        record('Edit/add cancel do not commit',app.session.to_dict()==before,['CMP-245','CMP-246'])
        prototype=deepcopy(app.session.plan['content']['steps'][0])
        app._plan_step_dialog=lambda step: {k:deepcopy(prototype[k]) for k in ('title','purpose','inputs','actions','outputs','completion_criteria','depends_on_step_ids','requirement_ids')} | dict(title='合成新增步骤',depends_on_step_ids=[])
        count=len(app.session.plan['content']['steps']);app.add_plan_step()
        record('Add callback creates one distinct step',len(app.session.plan['content']['steps'])==count+1 and app.session.plan['content']['steps'][-1]['title']=='合成新增步骤',['CMP-246'])
        tree.selection_set(tree.get_children()[-1]);selected=tree.selection()[0]
        app.move_selected_plan_step(-1)
        record('Move-up changes order with selection preserved',tree.selection()==(selected,) and app.session.plan['content']['steps'][-2]['step_id']==selected,['CMP-248'])
        app.move_selected_plan_step(1)
        record('Move-down restores order',app.session.plan['content']['steps'][-1]['step_id']==selected,['CMP-249'])
        before=deepcopy(app.session.to_dict());old_ask=ui.messagebox.askyesno
        ui.messagebox.askyesno=lambda *a,**kw: False;app.delete_selected_plan_step()
        record('Delete cancellation preserves step',app.session.to_dict()==before,['CMP-247'])
        ui.messagebox.askyesno=lambda *a,**kw: True;app.delete_selected_plan_step()
        record('Delete explicit confirmation removes only selected id',all(s['step_id']!=selected for s in app.session.plan['content']['steps']),['CMP-247'])
        ui.messagebox.askyesno=old_ask;app._plan_step_dialog=old_step
        fresh();selected=next(iter(app._plan_section_lookup));app.plan_section_var.set(selected);old_multi=app._multi_text_dialog
        app._multi_text_dialog=lambda title, fields: {key:value+' 合成修改' for key,label,value in fields}
        version=app.session.plan['plan_version'];app.edit_selected_plan_section()
        record('Section choice routes explicit update and invalidates',app.session.plan['plan_version']>version,['CMP-250','CMP-251'])
        app._multi_text_dialog=old_multi
        fresh();app.show_workspace(3);pump()
        hidden_before=not app._result_optional_controls.winfo_ismapped();app.toggle_result_options();pump()
        record('Optional result controls explicitly reveal',hidden_before and app._result_optional_controls.winfo_ismapped(),['CMP-321'])
        app.toggle_result_options();pump()
        record('Optional result controls can close',not app._result_optional_controls.winfo_ismapped(),['CMP-321'])
        # Real simpledialog: no mock of askstring, scheduled actual widget interaction.
        for mode in ('save','cancel'):
            def drive(mode=mode):
                ds=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
                if not ds:root.after(20,drive);return
                d=ds[-1];children=descendants(d);entry=next(w for w in children if w.winfo_class()=='Entry')
                entry.delete(0,'end');entry.insert(0,'合成短输入👩🏽‍💻')
                b=next(w for w in children if w.winfo_class()=='Button' and str(w.cget('text'))==('OK' if mode=='save' else 'Cancel'))
                b.invoke()
            root.after(90,drive)
            result=simpledialog.askstring('合成短输入','附注',parent=root)
            record('Real simpledialog '+mode,result=='合成短输入👩🏽‍💻' if mode=='save' else result is None,['CMP-437','CMP-438'] if mode=='save' else ['CMP-439'])
        # Record reachability separately; not a callback-pass claim for hidden buffers.
        fresh();app.show_workspace(3);pump()
        keys=['final_task_prompt_text','m2_suggestions_tree','m4_changes_tree','final_review_items_tree','accept_m2_suggestion_button','reject_m2_suggestion_button','process_final_review_item_button']
        reachability={k:bool(app.widgets[k].winfo_ismapped()) for k in keys if k in app.widgets}
        record('Conditional empty result panels remain hidden',not any(reachability.get(k,False) for k in keys[1:]),['CMP-303','CMP-308','CMP-312'],json.dumps(reachability))
        record('Visible task prompt buffer has read-only state',app.widgets['final_task_prompt_text'].cget('state')=='disabled',['CMP-302'])
    finally:
        app.shutdown(wait=True);app.executor.shutdown(wait=True,cancel_futures=True);root.destroy()

(OUT/'native-supplement.json').write_text(json.dumps(dict(observations=observations,environment='Windows/Tk8.6/source; disposable LOCALAPPDATA; explicit actual-vs-mocked scope'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Native supplement:',len(observations),'observations;',sum(o['passed'] for o in observations),'passed')
