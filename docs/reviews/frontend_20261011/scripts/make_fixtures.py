"""Fresh isolated projection fixtures; no network, keys or personal histories."""
import json
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1] / 'evidence'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(BASE / 'src'), str(BASE)]

with tempfile.TemporaryDirectory(prefix='promptsmith-audit-') as isolation:
    os.environ['LOCALAPPDATA'] = isolation
    for key in list(os.environ):
        if key.startswith('PROMPTSMITH_') or key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'GITHUB_TOKEN', 'GH_TOKEN'):
            os.environ.pop(key)
    import tkinter as tk
    import promptsmith.ui as ui
    from promptsmith.web_workspace import WorkspaceController
    from tests.test_final_delivery import confirmed_plan_session
    from promptsmith.finalization import build_final_draft, stage_final_draft
    ui.warm_local_skill_index = lambda *a: None
    root = tk.Tk()
    root.withdraw()
    app = ui.PromptSmithApp(root)
    view = WorkspaceController(app)
    view.install_native_bridge()
    app.provider_var.set('OpenAI')
    app.api_base_var.set('https://example.invalid/v1')
    app.api_model_var.set('gpt-6.1-sol')
    app.api_key_var.set('synthetic-audit-key')
    app.confirm_model_settings()

    def snapshot():
        result = view.snapshot()
        result['settings'] = view.settings_snapshot()
        result['history'] = dict(active='a' * 32, error='', entries=[dict(id=chr(97+i)*32, title=title, group=group, pinned=group=='置顶', stage='核对方案', updated_at='2026-10-11T12:00:00Z') for i,(title,group) in enumerate([('合成UI设计目标','置顶'),('合成学习任务','今天'),('昨天任务','昨天'),('资料研究','七天内'),('功能规划','30天内'),('旧任务','更早')])])
        return result
    fixtures = {'empty': snapshot()}
    app.widgets['task_text'].insert('1.0', '设计一个清楚易用的 Python 软件界面')
    app._sync_input()
    app.session.pending_questions = [dict(question_id=f'q{i}', gap_id=None, field='audience', scope='用户', text=('用户主要使用什么场景？' if i==0 else '希望页面重点呈现什么内容？'), options=[], reason='', depends_on=[]) for i in range(3)]
    app.session.control['response_traces'] = [dict(id='audit-trace', operation='analyze', status='done', elapsed=2.5, reasoning=('需要核对要求。\n汉字👩🏽‍💻é𠮷\n'*300), history_count=0, activities=[('核对需求','读取合成任务'), ('梳理范围','页面布局')])]
    app.refresh()
    fixtures['interview'] = snapshot()
    app._install_session(confirmed_plan_session(), reason='audit fixture')
    view.panel_kind='plan'
    fixtures['plan'] = snapshot()
    draft = build_final_draft(app.session)
    stage_final_draft(app.session, draft, expected_basis=draft['basis'])
    app.refresh()
    view.panel_kind='result'
    fixtures['final'] = snapshot()
    fixtures['skills'] = json.loads(json.dumps(fixtures['plan']))
    fixtures['skills']['cards'].append(dict(kind='skills', key='audit-skills', rows=[dict(id='s1', name='frontend-design', source='本地', score=.94, selected=False, allowed=True, bindings=[], description='界面设计与实现', details='合成 Skill 说明，非真实网络内容'), dict(id='s2', name='review-frontend-production', source='联网', score=.89, selected=True, allowed=False, bindings=['b2'], description='逐页审查', details='已选用合成候选')]))
    for key,label in [('find_skills','查找本地 Skill'),('find_online','继续联网查找'),('integrate','整合所选 Skill 并生成提示词'),('direct_skills','用已选 Skill 直接生成提示词'),('skip_skills','跳过 Skill，直接生成提示词')]:
        fixtures['skills']['buttons'][key]=dict(text=label,enabled=True)
    # All statically constructed Tk UI units, with stable application keys when present.
    key_by_path={str(widget):name for name,widget in app.widgets.items() if isinstance(widget,tk.Misc)}
    pages=[root.nametowidget(path) for path in app.notebook.tabs()]
    units=[]
    def visit(widget,page):
        cls=widget.winfo_class()
        text=''
        for attr in ('text','label'):
            try: text=str(widget.cget(attr));break
            except tk.TclError: pass
        if cls in ('TButton','Button','Text','TEntry','Entry','TCombobox','Treeview','Listbox','TCheckbutton','Checkbutton','TSpinbox','Spinbox','Scale','TScale') or (cls in ('TLabel','Label','TLabelframe') and text) or (cls=='Canvas' and str(widget) in key_by_path):
            units.append(dict(page=page, widget=str(widget), kind=cls, label=text, key=key_by_path.get(str(widget),''), mapped=bool(widget.winfo_manager())))
        for child in widget.winfo_children(): visit(child,page)
    for index,page in enumerate(pages): visit(page,index)
    (OUT/'tk-constructed-units.json').write_text(json.dumps(units,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'fixtures.json').write_text(json.dumps(fixtures,ensure_ascii=False,indent=2),encoding='utf-8')
    app.shutdown(wait=True)
    app.executor.shutdown(wait=True,cancel_futures=True)
    root.destroy()
print('Fresh synthetic fixtures and Tk inventory written')
