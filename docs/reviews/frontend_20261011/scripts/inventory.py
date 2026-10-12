"""Stable inventory; checks start not_checked, never inferred passed."""
import json
from pathlib import Path
from datetime import datetime, timezone
import sys
BASE=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from promptsmith.preferences import FIELDS
a=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
now=datetime.now(timezone.utc).isoformat()
a['project'].update(target=str(BASE),access_mode='source_runtime',scope='Windows WebView2全部虚拟页、独立Debug、可达Tk兼容编辑与显式Tk回退；所有条件操作与设置字段。',baseline=dict(source_ref='6fd8576 + 审查时未提交源码，SHA256见 evidence/source-manifest.json',runtime_ref='同一工作树；Chrome DOM受控桥接与真实WebView2/Tk；离线合成数据',observed_at=now),inventory_status='discovering',production_profile=dict(users='希望将目标整理成提示词的本机用户',tasks='访谈→确认需求→方案→可选Skill→提示词→保存恢复',identity='Windows当前用户，无租户或云端账户',risk='本地历史、密钥、模型收费请求；审查只用隔离合成数据',scale='默认6项Skill、最多可显示20项推荐；历史和长文本无产品上限',environment='Windows桌面，WebView2默认，Tk显式回退；最小720×440',performance='动画与独立滚动流畅；未承诺180Hz或固定FPS',accessibility='键盘核心旅程；未声明WCAG合规等级',release='未来EXE；本轮不构建或发布',unknown='真实模型服务行为、180Hz实际呈现、跨机EXE'))
a['progress']=dict(current_page=None,completed_batches=['契约、交接与全部Web实现阅读；初步Tk入口核对'],next_actions=['运行DOM矩阵并登记问题','复核Tk兼容编辑及共享业务测试','完成每页和每实例方案'],unresolved_access=['真实付费模型、生产数据及EXE跨机验证本轮不执行'],last_updated=now)
a['evidence']=[dict(id='EV-001',kind='specification',locator='用户请求 + AGENTS.md + HANDOFF.md + docs/ui-handoff.md + review-frontend-production',observed_at=now,baseline_ref='当前会话与交接',summary='完整逐页逐组件审查，audit_plan；默认字体、125%/局部100%、手动日志、明确确认、跳过排除与断点恢复。'),dict(id='EV-002',kind='source',locator='resources/ui/workspace/index.html; workspace.js:1-369; history.js:1-101; settings.js:1-116; debug.js:1-35; workspace.css; debug.css',observed_at=now,baseline_ref='current worktree',summary='已读Web外壳、全部分支、动作、状态、样式和独立Debug实现。'),dict(id='EV-003',kind='source',locator='src/promptsmith/web_workspace.py:1-592; web_debug.py:1-149; ui.py:733-1062,2106-2159,2413-2516,2578-2673; guided_flow.py:112-281; conversation.py:250-480,819-916; preferences.py:29-133',observed_at=now,baseline_ref='current worktree',summary='已核对窄桥接、Tk所属线程、版本检查、可达兼容编辑、全部设置以及模式边界。'),dict(id='EV-004',kind='test',locator='python -X utf8 docs/reviews/frontend_20261011/scripts/make_fixtures.py; evidence/fixtures.json; evidence/tk-constructed-units.json',observed_at=now,baseline_ref='current worktree',summary='本轮实际构造隔离Tk应用、生成当前业务投影和208个原生叶子单元；未调用网络。仅构造证据，不代表控件交互通过。')]
a['project']['inventory_sources']=[dict(kind='Web源码',locator='resources/ui/workspace/',evidence_ids=['EV-002']),dict(kind='Tk结构与桥接',locator='src/promptsmith/web_workspace.py; guided_flow.py; ui.py',evidence_ids=['EV-003']),dict(kind='当前构造与状态投影',locator='evidence/fixtures.json; tk-constructed-units.json',evidence_ids=['EV-004']),dict(kind='产品设计与交接',locator='HANDOFF.md; docs/ui-handoff.md',evidence_ids=['EV-001'])]
a['pages']=[];a['definitions']=[];a['instances']=[]
defs={}
def page(title,route,src,variants):
 p=dict(id=f'PAGE-{len(a["pages"])+1:03}',title=title,route=route,source_locator=src,entry_conditions='对应导航/操作/业务阶段；隔离合成记录',variants=variants,evidence_ids=['EV-002' if src.startswith('resources') else 'EV-003'],scope_status='in_scope')
 a['pages'].append(p);return p
def cmp(p,label,locator,definition='Web按钮',src='resources/ui/workspace/workspace.js:32',critical=False,variant='空/有值/忙/失败按实际职责',notes=''):
 if definition not in defs:
  d=dict(id=f'DEF-{len(defs)+1:03}',name=definition,kind='UI逻辑单元',source_locator=src,source_status='located');defs[definition]=d;a['definitions'].append(d)
 c=dict(id=f'CMP-{len(a["instances"])+1:03}',page_id=p['id'],definition_id=defs[definition]['id'],label=label,locator=locator+'; '+src,variant=variant,criticality='high' if critical else 'normal',notes=notes,data_source='SessionState / 公共settings / 本地history元数据，浏览器仅临时呈现')
 a['instances'].append(c);return c
def buttons(p,labels,area):
 for x in labels: cmp(p,x,area+' / '+x,critical=True)

p=page('主工作区与历史侧栏','workspace','resources/ui/workspace/index.html:5-22',['Hero','历史空/有/失败','展开/收起','忙/恢复','浅/深/小窗'])
cmp(p,'外壳与页内滚动','#workspace-shell / #viewport','Web外壳','resources/ui/workspace/index.html:5',True)
cmp(p,'Hero目标说明','#hero','Hero','resources/ui/workspace/index.html:13')
cmp(p,'品牌与历史日期组','#sidebar .sidebar-brand / .history-group h2','历史分组','resources/ui/workspace/history.js:42')
buttons(p,['新建对话','搜索历史','收起/展开','文件','核对需求','核对方案','任务摘要','设置'],'header / sidebar')
cmp(p,'历史记录选择模板','.history-select','历史记录行','resources/ui/workspace/history.js:26',True,variant='当前/非当前/置顶/不可读取；不同日期等价类')
cmp(p,'历史悬停菜单入口','.history-more','历史操作入口','resources/ui/workspace/history.js:32',True)
cmp(p,'历史失败与重试','#history-status','历史错误状态','resources/ui/workspace/history.js:51',True)
cmp(p,'Toast操作反馈','#toast','Web反馈','resources/ui/workspace/workspace.js:65')
cmp(p,'下一步恢复动作','#recovery [data-action=primary]','工作流按钮','resources/ui/workspace/workspace.js:33',True)
cmp(p,'消息输入','#message','消息输入','resources/ui/workspace/workspace.js:79',True)
buttons(p,['选择模型','整理深度','任务类型','发送消息'],'#composer .toolbar')

p=page('访谈与模型处理','workspace / interview','resources/ui/workspace/workspace.js:127-211',['首轮','逐题回答','已回答/跳过','补答','达到五轮/可继续','流式/失败/取消'])
for label,loc,definition,src,critical in [('用户目标与回答气泡','.user .bubble','文本气泡',180,False),('补答按钮','.reanswer','补答入口',181,True),('AI问题全文','.question-title','问题标题',185,False),('逐题回答框','.answer-input','消息输入',79,True),('提交回答','.answer-row .send','Web按钮',32,True),('跳过该题','.skip','Web按钮',32,True),('历史问题文本','.history_question','问题标题',185,False),('取消补答','#reanswer-context button','Web按钮',32,True),('继续询问/结束追问','.interview_unknowns .actions','工作流按钮',33,True),('处理状态与点阵','.trace > button','思考展开器',127,True),('思考子展开器','.trace-body > button','思考展开器',127,True),('思考内容与独立滚动','.thought','思考流',161,False),('检索活动记录','.activities','活动列表',156,False),('模型失败文字','.trace-error','Web反馈',159,False)]: cmp(p,label,loc,definition,f'resources/ui/workspace/workspace.js:{src}',critical)

p=page('Skill选择','workspace / skills','resources/ui/workspace/workspace.js:196-208',['无结果/多来源','选中/取消','来源过滤','推荐/全部','搜索/整合失败'])
cmp(p,'Skill阶段说明','.message p.notice','阶段说明','resources/ui/workspace/workspace.js:197')
for action in ['find_skills','find_online','integrate','direct_skills','skip_skills']:cmp(p,action,f'[data-action={action}]','工作流按钮','resources/ui/workspace/workspace.js:33',True)
for source in ['全部来源','本地','联网','内置','已选']:cmp(p,'来源 '+source,'.actions / '+source,'Web筛选','resources/ui/workspace/workspace.js:199')
cmp(p,'推荐/全部切换','显示全部/只显示推荐','Web筛选','resources/ui/workspace/workspace.js:200')
cmp(p,'Skill名称/来源/推荐列','.table-wrap table','Skill比较表','resources/ui/workspace/workspace.js:201')
for label in ['选用此Skill/已选中','取消选用','用途摘要与详细说明']:cmp(p,label,'.table-wrap tbody / '+label,'Skill行操作','resources/ui/workspace/workspace.js:203',True)

p=page('最终提示词','workspace / result','resources/ui/workspace/workspace.js:192-195',['草稿/已确认/过期','复制/导出','修改语气/附注'])
cmp(p,'提示词分层正文','.message .reading','正文与标题','resources/ui/workspace/workspace.js:40')
for key in ['copy','export','save','confirm_final']:cmp(p,key,f'[data-action={key}]','工作流按钮','resources/ui/workspace/workspace.js:33',True)
buttons(p,['语气和附注'],'.message[result]')

for kind,title in [('requirements','一起核对需求'),('plan','核对方案'),('summary','任务摘要'),('result','语气和附注')]:
 p=page(title,'workspace / panel:'+kind,'resources/ui/workspace/workspace.js:274-302',['空/有内容','打开/更新/关闭','忙/可用'])
 cmp(p,'面板外壳与关闭','.review-panel','Web浮层','resources/ui/workspace/workspace.js:260',True)
 if kind=='requirements':
  for label in ['需求表头/行/选择','完整需求详情','冲突与确认前原因']:cmp(p,label,'.review-panel / '+label,'需求表','resources/ui/workspace/workspace.js:290',True)
  for key in ['edit_requirement','remove_requirement','accept_requirement','adopt_requirement','confirm_requirements']:cmp(p,key,f'[data-action={key}]','工作流按钮','resources/ui/workspace/workspace.js:33',True)
 elif kind=='plan':
  cmp(p,'方案状态','.notice','阶段说明','resources/ui/workspace/workspace.js:287')
  cmp(p,'方案全文与折叠章节','.reading details','正文与标题','resources/ui/workspace/workspace.js:40')
  for key in ['edit_plan_goal','edit_plan','review_plan','confirm_plan','find_skills']:cmp(p,key,f'[data-action={key}]','工作流按钮','resources/ui/workspace/workspace.js:33',True)
 elif kind=='summary':cmp(p,'当前摘要全文','.reading','正文与标题','resources/ui/workspace/workspace.js:40')
 else:
  cmp(p,'提示词语气','select[aria-label=提示词语气]','语气选择','resources/ui/workspace/workspace.js:298',True)
  cmp(p,'用户附注/空说明','.reading / .notice','附注文本','resources/ui/workspace/workspace.js:299')
  cmp(p,'添加附注','[data-action=add_final_note]','工作流按钮','resources/ui/workspace/workspace.js:33',True)

p=page('模型选择','workspace / model-picker','resources/ui/workspace/workspace.js:309-339',['五供应商','搜索无/有','自定义模型','四档强度','快切/失败'])
cmp(p,'模型浮层外壳','.picker','Web浮层','resources/ui/workspace/workspace.js:260',True)
for label,loc in [('搜索模型','.picker-search input'),('清空搜索','.clear-search'),('模型列表与无结果','.models')]:cmp(p,label,loc,'模型目录','resources/ui/workspace/workspace.js:309',True)
for provider in ['OpenAI','Anthropic','Google','xAI','DeepSeek']:cmp(p,provider+'供应商与图标','[data-provider='+provider+']','供应商Tab','resources/ui/workspace/workspace.js:334',True)
cmp(p,'模型名称/说明/能力图标/选中勾','.model-row','模型行','resources/ui/workspace/workspace.js:329',True,variant='推理/图像；当前/非当前/自定义')
for value in ['low','medium','high','max']:cmp(p,'思考强度 '+value,'[data-effort='+value+']','思考强度Radio','resources/ui/workspace/workspace.js:320',True)
cmp(p,'思考强度信号与滑块','.effort-indicator / .thinking-indicator','强度装饰','resources/ui/workspace/workspace.js:32')
for kind,title,labels in [('depth','整理深度菜单',['quick','standard','deep']),('category','任务类型菜单',['自动判断','CATEGORY_LABELS全枚举']),('file','文件菜单',['new','open','save','save_as'])]:
 p=page(title,'workspace / menu:'+kind,'resources/ui/workspace/workspace.js:303-307,345',['打开/关闭','当前选择','忙态/键盘','长标题'])
 cmp(p,'浮层菜单外壳','.popup','Web浮层','resources/ui/workspace/workspace.js:260',True)
 for label in labels:cmp(p,label,'.menu-row / '+label,'Web菜单项','resources/ui/workspace/workspace.js:307',True,notes='任务类别按当前固定类别数据等价；自动判断与显式类别契约分别登记')

p=page('历史会话操作菜单','history / menu','resources/ui/workspace/history.js:35-47',['置顶/非置顶','键盘/鼠标','关闭'])
cmp(p,'历史菜单外壳','.history-menu','Web浮层','resources/ui/workspace/workspace.js:260',True)
for label in ['重命名','置顶/取消置顶','删除']:cmp(p,label,'.history-menu / '+label,'历史菜单项','resources/ui/workspace/history.js:38',True)
for kind,title in [('search','搜索历史'),('rename','重命名历史'),('delete','删除历史')]:
 p=page(title,'history / dialog:'+kind,'resources/ui/workspace/history.js:54-99',['取消/成功/失败','长名/同名/空','IME/键盘'])
 cmp(p,'模态框与关闭','.history-dialog','历史模态框','resources/ui/workspace/history.js:56',True)
 if kind!='delete':cmp(p,'搜索/名称输入','.history-dialog input','历史输入','resources/ui/workspace/history.js:66',True)
 if kind=='search':
  cmp(p,'搜索匹配记录','.history-search-results button','历史搜索结果','resources/ui/workspace/history.js:88',True)
  cmp(p,'没有匹配说明','.history-empty','阶段说明','resources/ui/workspace/history.js:94')
 else:
  buttons(p,['取消','保存' if kind=='rename' else '删除'],'.history-dialog .actions')
  cmp(p,'字段/操作错误','.dialog-error','Web反馈','resources/ui/workspace/history.js:65')
  if kind=='delete':cmp(p,'删除范围说明','.history-dialog p','阶段说明','resources/ui/workspace/history.js:73')

for cat in ['模型','Skill 搜索','界面','会话与导出','诊断']:
 p=page('Web设置 · '+cat,'settings / '+cat,'resources/ui/workspace/settings.js:1-116',['未改/草稿/保存','忙/失败/恢复默认','隐藏再返回'])
 cmp(p,'分类Tab和标题','.settings-tabs / h1','设置导航','resources/ui/workspace/settings.js:54',True)
 buttons(p,['返回工作区','恢复本类默认','保存设置'],'.settings-heading / .settings-footer')
 cmp(p,'草稿/保存/请求/错误状态','.settings-status','设置状态','resources/ui/workspace/settings.js:15')
 if cat=='模型':
  for field in ['provider','protocol','base_url','model']:cmp(p,'connection.'+field,'#settings-field-connection-'+field,'设置字段','resources/ui/workspace/settings.js:37',True)
  cmp(p,'API Key输入与保存保护','#settings-key','密钥字段','resources/ui/workspace/settings.js:75',True)
  buttons(p,['清空密钥','获取模型','测试连接','确认'],'.settings-model-actions / .settings-input-row')
  cmp(p,'模型确认依据','.settings-status','设置状态','resources/ui/workspace/settings.js:22')
 for key,spec in FIELDS.items():
  if spec.category==cat:cmp(p,spec.label,'#settings-field-'+key,'设置字段','resources/ui/workspace/settings.js:37',critical=cat=='模型' or key=='debug_console_enabled',notes='字段 '+key+': 默认 '+str(spec.default)+'；范围 '+str((spec.minimum,spec.maximum))+'；枚举 '+str(spec.choices))
 if cat=='会话与导出':buttons(p,['会话目录浏览','导出目录浏览'],'.settings-input-row')
 if cat=='诊断':cmp(p,'日志目录与手动保存说明','.settings-diagnostics-note','阶段说明','resources/ui/workspace/settings.js:90')

p=page('Web Debug控制台','debug.html','resources/ui/workspace/debug.html',['全部级别/过滤','清空/复制/保存失败','滚动/缓存截断','浅/深/小窗'])
cmp(p,'Debug标题与缓存计数','header / #count','Debug标题','resources/ui/workspace/debug.html:6')
for label,loc in [('日志级别','#level'),('自动滚动','#autoscroll'),('复制日志','#copy'),('清空显示','#clear'),('保存日志','#save'),('打开日志目录','#directory')]:cmp(p,label,loc,'Debug工具','resources/ui/workspace/debug.js:26',True)
cmp(p,'日志正文与颜色','#log-lines / #debug-scroll','Debug日志流','resources/ui/workspace/debug.js:7')
cmp(p,'保存状态和错误','#save-status / #debug-error','Debug状态','resources/ui/workspace/debug.js:22')

# Retain every constructed native leaf; concealed buffers are explicitly not interactive UI.
units=json.loads((OUT/'evidence/tk-constructed-units.json').read_text(encoding='utf-8'))
for index,title in enumerate(['Tk统一对话回退','Tk方案兼容编辑','Tk Skill详情','Tk结果高级选项','Tk五类设置']):
 p=page(title,'native notebook:'+str(index),'src/promptsmith/guided_flow.py:177-187',['浅/深','空/有/失效','滚动/小窗','业务条件可见'])
 cmp(p,'页面壳与滚动区',f'notebook[{index}]','Tk页面壳','src/promptsmith/guided_flow.py:177',True)
 for unit in units:
  if unit['page']!=index or unit['key']=='task_text':continue
  label=unit['key'] or unit['label'] or unit['kind']
  if unit['kind']=='TLabelframe':continue # grouping decoration checked in shell layout
  src='src/promptsmith/conversation.py:819' if index==0 else f'src/promptsmith/ui.py:{[0,733,839,935,0][index]}'
  if index==4:src='src/promptsmith/settings_ui.py:1'
  definition=('Tk设置字段' if index==4 and (unit['key'].startswith('setting_') or unit['kind'] in ('TEntry','TCombobox','TSpinbox','TCheckbutton')) else 'Tk '+unit['kind'])
  cmp(p,label,unit['widget'],definition,src,critical=unit['kind'] not in ('Label','TLabel'),variant='mapped='+str(unit['mapped'])+'；真实可见性还取决于祖先折叠/业务条件',notes='程序构造清单：'+unit['key'])

for title,src,labels in [('Tk多文本编辑（需求/目标/栏目）','src/promptsmith/ui.py:2106',['动态字段标签','文本编辑与滚动','取消','保存']),('Tk步骤编辑','src/promptsmith/ui.py:2413',['title','purpose','inputs','actions','outputs','completion_criteria','依赖步骤','关联需求','取消','保存草稿','校验错误']),('Tk关键工作编辑','src/promptsmith/ui.py:2578',['title','goal','inputs','outputs','checkpoints','关联步骤','关联需求','取消','保存草稿','校验错误']),('Tk简短输入（附注/目标/新增需求）','src/promptsmith/ui.py:4453',['单行输入','确定','取消']),('Tk Debug回退','src/promptsmith/debug_console.py:1',['级别筛选','自动滚动','复制','清空显示','保存日志','日志目录','日志正文与严重颜色','错误与保存状态']),('Tk菜单/审查浮层/模型菜单','src/promptsmith/interaction_ui.py:1; src/promptsmith/composer.py:1',['文件菜单（新建/打开/保存/另存/退出）','需求核对表与操作','方案核对章节与操作','任务摘要','语气和附注','模型搜索/清空/目录','五供应商选择','四档思考选择','任务类型与整理深度菜单']),('Windows文件对话框','src/promptsmith/web_workspace.py:112; src/promptsmith/ui.py:4990',['打开会话','保存/另存会话','导出Markdown','设置目录选择','覆盖/取消/无权限错误'])]:
 p=page(title,'native dialog / '+title,src,['鼠标/键盘','保存/取消/错误','长内容/小屏'])
 for label in labels:cmp(p,label,'native / '+label,title,src,True)

(OUT/'audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Inventory:',len(a['pages']),'pages',len(a['definitions']),'definitions',len(a['instances']),'instances')
