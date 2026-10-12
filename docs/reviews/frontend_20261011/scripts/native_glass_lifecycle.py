"""Check actual three GlassButton instances' hover/tooltip/cache destruction."""
import json,os,sys,tempfile,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parents[1]/'evidence'
sys.path[:0]=[str(BASE/'src'),str(BASE)];checks=[]
with tempfile.TemporaryDirectory(prefix='promptsmith-review-glass-') as temp:
 os.environ['LOCALAPPDATA']=temp
 for k in list(os.environ):
  if k.startswith('PROMPTSMITH_') or k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','GITHUB_TOKEN','GH_TOKEN'):os.environ.pop(k)
 import tkinter as tk
 import promptsmith.ui as ui
 from tests.test_response_workspace import questions
 ui.warm_local_skill_index=lambda *a:None
 root=tk.Tk();root.geometry('1440x810+0+0');app=ui.PromptSmithApp(root)
 def pump(t):
  end=time.monotonic()+t
  while time.monotonic()<end:root.update();time.sleep(.004)
 try:
  app.widgets['task_text'].insert('1.0','合成目标');app._sync_input();app.session.pending_questions=questions();app.session.record_question('q1','answered','合成回答');app.refresh();pump(.1)
  answer=app.session.question_history[-1];composer=app.widgets['conversation_composer']
  buttons=[('CMP-476',app._conversation_buttons['question:'+answer['answer_id']]),('CMP-477',composer.depth_button),('CMP-478',composer.category_button)]
  for cid,b in buttons:
   b._hover(True);pump(.08);intermediate=0<b.amount<1
   b._hover(False);pump(.02)
   if b.icon_name:b._show_tip()
   b.destroy();pump(.03)
   checks.append(dict(instance_id=cid,passed=intermediate and b.tween.job is None and b._tip is None and len(b.images)<=32,intermediate_hover=intermediate,timer_cleared=b.tween.job is None,tooltip_cleared=b._tip is None,cache_entries=len(b.images)))
 finally:app.shutdown(wait=True);root.destroy()
(OUT/'native-glass-lifecycle.json').write_text(json.dumps(dict(environment='Actual Tk loop/depth/category instances; isolated app; lifecycle not FPS or long soak',checks=checks),ensure_ascii=False,indent=2),encoding='utf-8')
print('Native glass lifecycle',len(checks),'passed',sum(c['passed'] for c in checks))
