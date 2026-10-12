"""Remaining native local entry/scroll/reading and component cleanup audit."""
import json,os,sys,tempfile,time
from pathlib import Path
from copy import deepcopy
BASE=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]/'evidence'
sys.path[:0]=[str(BASE/'src'),str(BASE)]
checks=[]
def record(name,value,ids):checks.append(dict(name=name,passed=bool(value),instance_ids=ids))
with tempfile.TemporaryDirectory(prefix='promptsmith-review-actions-') as temp:
 os.environ['LOCALAPPDATA']=temp
 for key in list(os.environ):
  if key.startswith('PROMPTSMITH_') or key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','GITHUB_TOKEN','GH_TOKEN'):os.environ.pop(key)
 import tkinter as tk
 import promptsmith.ui as ui
 import promptsmith.settings_ui as settings
 from tests.test_final_delivery import confirmed_plan_session
 from promptsmith.response_ui import ResponseTrace
 ui.warm_local_skill_index=lambda *a:None
 root=tk.Tk();root.geometry('720x440+0+0');app=ui.PromptSmithApp(root)
 app._show_error=lambda *a,**k:None;app._show_info=lambda *a,**k:None
 def pump(t=.12):
  end=time.monotonic()+t
  while time.monotonic()<end:root.update();time.sleep(.005)
 def fresh():app._install_session(confirmed_plan_session(),reason='local audit actions');app.refresh();pump()
 try:
  fresh()
  canvas_ids={'requirements_page_canvas':['CMP-204','CMP-206','CMP-222'],'plan_page_canvas':['CMP-229','CMP-230'],'skills_page_canvas':['CMP-260','CMP-261'],'export_page_canvas':['CMP-288','CMP-289'],'settings_page_canvas':['CMP-322','CMP-323'],
    'settings_category_0_page_canvas':['CMP-326'],'settings_category_1_page_canvas':['CMP-353'],'settings_category_2_page_canvas':['CMP-380'],'settings_category_3_page_canvas':['CMP-387'],'settings_category_4_page_canvas':['CMP-398']}
  for name,ids in canvas_ids.items():
   widget=app.widgets[name]
   index=0 if name=='requirements_page_canvas' else 1 if name=='plan_page_canvas' else 2 if name=='skills_page_canvas' else 3 if name=='export_page_canvas' else 4
   app.show_workspace(index)
   if name.startswith('settings_category_'):app.widgets['settings_categories'].select(int(name.split('_')[2]))
   pump();widget.yview_moveto(0);before=widget.yview();widget.yview_moveto(1);after=widget.yview()
   record(name+' bounded scroll moves or whole content fits',widget.winfo_ismapped() and (before[1]>=.999 or after[0]>before[0]),ids)
  fresh();app.show_workspace(1);app.widgets['plan_editor_panel']._show(True);pump()
  for name,cid in [('plan_reading_text','CMP-233'),('plan_overview_text','CMP-252')]:
   text=app.widgets[name];record(name+' full text read-only and selectable',bool(text.get('1.0','end-1c')) and text.cget('state')=='disabled',[cid])
  before=deepcopy(app.session.to_dict());app.go_to_requirements();pump()
  record('Modify requirements returns without invalidating plan',app.notebook.index(app.notebook.select())==0 and before==app.session.to_dict(),['CMP-257'])
  app.show_workspace(1)
  def walk(w):
   for c in w.winfo_children():yield c;yield from walk(c)
  back=next(w for w in walk(app.root) if w.winfo_class()=='TButton' and str(w.cget('text'))=='返回当前需求');back.invoke()
  record('Return requirements button navigates',app.notebook.index(app.notebook.select())==0,['CMP-235'])
  fresh();called=[];app.find_skills=lambda:called.append(True);app.confirm_plan_and_find_skills()
  record('Optional Skill entry dispatches and navigates',called==[True] and app.notebook.index(app.notebook.select())==2,['CMP-234'])
  fresh();tree=app.widgets['plan_key_work_tree'];rows=tree.get_children()
  tree.selection_set(rows[0]);old=app._key_work_dialog
  app._key_work_dialog=lambda row:dict(title='合成关键工作修改',goal=row['goal'],inputs=row['inputs'],outputs=row['outputs'],checkpoints=row['checkpoints'],step_ids=row['step_ids'],requirement_ids=row['requirement_ids'],depends_on_key_work_ids=row.get('depends_on_key_work_ids',[]))
  app.edit_selected_key_work()
  record('Key-work selection edits same stable id',app.session.plan['content']['key_work'][0]['key_work_id']==rows[0] and app.session.plan['content']['key_work'][0]['title']=='合成关键工作修改',['CMP-254','CMP-255'])
  app._key_work_dialog=old
  app.show_workspace(3);app.toggle_result_options();pump()
  text=app.widgets['final_preview_text'];record('Result canonical preview remains read-only',text.cget('state')=='disabled',['CMP-300'])
  # Explicit path chooser mock tests consumers, not the OS dialog.
  old_choose=settings.filedialog.askdirectory
  for name,cid in [('session_directory','CMP-394'),('export_directory','CMP-397')]:
   v=app.preference_vars[name];before=v.get();settings.filedialog.askdirectory=lambda **k:'';app._choose_settings_directory(v)
   record(name+' chooser cancel preserves draft',v.get()==before,[cid])
   settings.filedialog.askdirectory=lambda **k:str(Path(temp)/name);app._choose_settings_directory(v)
   record(name+' chooser result stages correct field',v.get()==str(Path(temp)/name),[cid])
  settings.filedialog.askdirectory=old_choose
  composer=app.widgets['conversation_composer'];app.show_workspace(0);pump()
  composer.toggle_picker();pump();picker=composer.picker
  composer.discard_picker();pump()
  record('Native model picker cleanup cancels focus timer',picker._focus_after is None and not picker.window.winfo_exists(),['CMP-453','CMP-454','CMP-455','CMP-490'])
  composer.toggle_choices('depth');pump();menu=composer.choice_menu;menu.close(immediate=True);pump()
  record('Native choice close destroys window and Tween',not menu.window.winfo_exists() and menu.tween.job is None,['CMP-456','CMP-477','CMP-478'])
  trace=ResponseTrace(app.widgets['conversation_timeline'],dict(id='local-cleanup',status='working',reasoning='合成长思考👩🏽‍💻\n'*300,activities=[]));trace.grid(row=50,column=0);pump(.04)
  trace.destroy();pump()
  record('Native trace destroy closes writer and indicators',trace.writer.closed and trace.writer.after is None and trace._indicator_after is None,['CMP-483','CMP-484','CMP-485','CMP-486'])
  app.shutdown(wait=True)
  record('Native app shutdown cancels completion/response polling',app._completion_after_id is None and app._response_after is None,['CMP-204','CMP-229','CMP-260','CMP-288','CMP-322'])
 finally:
  app.shutdown(wait=True);root.destroy()
(OUT/'native-final-actions.json').write_text(json.dumps(dict(checks=checks,environment='Real isolated Tk; Skill search and dialog-return explicitly mocked, no OS picker automation or APIs'),ensure_ascii=False,indent=2),encoding='utf-8')
print('Native final actions',len(checks),'passed',sum(o['passed'] for o in checks))
