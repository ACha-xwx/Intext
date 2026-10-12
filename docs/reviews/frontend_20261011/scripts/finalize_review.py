"""Assemble curated audit judgments and reports, preserving the discovered IDs.

This script renders human-reviewed evidence. It does not perform tests or infer
success from construction. Runtime gaps remain blocked and mechanically visible.
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from review_contracts import CONTRACTS, PAGE_NOTES

OUT=Path(__file__).resolve().parents[1]
BASE=OUT.parents[2]
a=json.loads((OUT/'audit.json').read_text(encoding='utf-8'))
for p in a['pages']:
    if isinstance(p['entry_conditions'],str):
        p['entry_conditions']=[p['entry_conditions']]
now=datetime.now(timezone.utc).isoformat()
baseline='6fd8576 + source-manifest.json current-worktree SHA256'

def ev(identity,kind,locator,summary):
    value=dict(id=identity,kind=kind,locator=locator,observed_at=now,baseline_ref=baseline,summary=summary)
    a['evidence']=[e for e in a['evidence'] if e['id']!=identity]+[value]

ev('EV-005','test','scripts/browser_audit.py; evidence/browser-observations.json','本轮Chrome154无头真实资源/合成桥接100项，79符合/21差异；失败文案一项为工具模拟范围导致，不能计产品缺陷。')
ev('EV-006','test','scripts/browser_more.py; evidence/browser-more.json','清洁小窗、菜单/焦点/IME事件注入、HTML惰性与反向动画27项，9符合/18差异；几何保留原值。')
ev('EV-007','test','evidence/focused-tests.xml','首批18模块258项通过；Tk/业务和窄桥接离线测试，不代表真实模型。')
ev('EV-008','measurement','scripts/native_web_audit.py; evidence/native-web-checks.json','真实Windows WebView2/Edge154，主窗8项通过；8次动画均有中间帧，最大布局变化间隔27.8ms；长Unicode123次更新；Debug实际手动完整保存/自身异常捕获通过。')
ev('EV-009','test','scripts/native_history_audit.py; evidence/native-run-1.json; native-run-2.json','真实WebView2两次应用/窗口重建13项通过；同一验收进程内重建，不是两个独立OS进程；合成磁盘历史确实读写，无自动日志。')
ev('EV-010','test','scripts/native_ui_audit.py; evidence/native-ui-observations.json','本轮真实Windows Tk 21项通过，五页构造/显示、实际多文本/步骤/关键工作保存取消、错误留开及Debug；单个叶子被构造不等于各自操作全通过。')
ev('EV-011','artifact','evidence/contact-1.png..contact-4.png; native-contact-1.png; native-contact-2.png; clean-small-settings.png; picker-bounds-*.png','本轮已实际查看28张首批截图和12张原生截图的联系表，及小窗几何；截图只证明对应状态的视觉，不当作键盘/后端证据。')
ev('EV-012','test','evidence/native-adjacent-tests.xml; evidence/skill-multiwork-recheck.xml; evidence/test-node-results.json','扩展12模块172项：157通过、15失败；14项与已批准旧控件/建议/跳过/模型目录合同变化相关；1项异步3秒等待批量超时，隔离复验通过。两批412不同节点，最后398通过、14旧合同失败。')
ev('EV-013','source','src/promptsmith/credentials.py:1-119; preferences.py:29-135; session_history.py:1-125; history_workspace.py:66-180; PromptSmith.spec; requirements.txt','已读DPAPI当前用户/公开设置界限、偏好验证、受管UUID/原子写盘/草稿排序、资源打包声明；跨机EXE与真实服务仍待验。')
ev('EV-014','test','evidence/integration-busy-snapshot.json; conversation.py:755-763; workspace.js:196-255','真实隔离app设delivery_busy并refresh后snapshot包含enabled cancel_request，当前Web时间线及recovery均未渲染它；不是仅凭伪造locked状态推断。')
ev('EV-015','test','evidence/save-directory-error.json; src/promptsmith/ui.py:5149-5172','模拟Path.mkdir PermissionError，app.save抛到调用者且_show_error未调用；Web桥接外层会给通用提示，原生回退缺保存位置恢复提示。')
ev('EV-016','source','response_ui.py:23-52,64-396; composer.py:263-382; interaction_ui.py:1-253,410-449; guided_flow.py:77-109,221-265; settings_ui.py:114-300','补读自绘、逐帧writer、默认字体、原生兼容实际入口、五类字段与保存生命周期；原生构造清单的动态Canvas漏项已补账。')
ev('EV-017','test','scripts/native_supplement.py; evidence/native-supplement.json','18项原生补验全部通过：展开、目标/受众/栏目回调、步骤编辑/新增/排序/删除/取消、结果展开/关闭、真实askstring确认/取消。回调编辑返回值的模拟与实际对话操作在每项detail区分。')
ev('EV-018','test','python -X utf8 -m pytest tests/test_skill_browser.py -q --junitxml=docs/reviews/frontend_20261011/evidence/skill-browser-tests.xml','18个新增不同节点全部通过，实际Tk比较表：来源累计、筛选/推荐/全部、批量选择、完整详情、已选禁用/取消、保存恢复和迟到隔离。三批最新430个不同节点416通过，14旧合同失败。')
ev('EV-019','test','scripts/native_settings_fields.py; evidence/native-settings-fields.json','逐个实际编辑30个原生偏好控件并保存/读取；17个数字字段无效文本被拒且旧值保留，共47项全部通过。无API Key和真实服务；Debug开关由EV-007单独验证。')
ev('EV-020','test','scripts/native_final_actions.py; evidence/native-final-actions.json','25项原生补验全通过：五页/五分类实际滚动、全文只读、返回/修改需求不失效、Skill入口派发、关键工作编辑、目录选择取消/写草稿消费者，以及模型/菜单/trace/主应用计时器清理。OS目录返回和Skill搜索模拟已明示。首次脚本pack/grid混用已修脚本，无应用变化。')
ev('EV-021','measurement','scripts/browser_lifecycle.py; evidence/browser-lifecycle.json','Chrome154真实资源/模拟桥接：20次访谈/Skill/方案/结果/空态循环100次布局，DOM计数回基线、traces清空、模型/深度/类别/文件/历史浮层关闭无残留、无JS异常；8项通过，中位0.9ms/p95=1.6ms/最大2.2ms。不是180Hz、堆GC或长期性能证明。')
ev('EV-022','test','scripts/native_glass_lifecycle.py; evidence/native-glass-lifecycle.json','实际loop/整理深度/任务类型三个GlassButton在hover中间帧销毁后Tween.job清空、tooltip销毁、图形内存缓存<=32，3项全部通过。生命周期结果不等于Tk180Hz。')

# Append discovered dynamic UI responsibility units without replacing earlier IDs.
new_defs=[('Tk动态回复按钮','src/promptsmith/response_ui.py:23-52',4),('Tk圆形/玻璃按钮','src/promptsmith/interaction_ui.py:135-236',12),('Tk逐题回答组合','src/promptsmith/interaction_ui.py:410-449; conversation.py:513',10),('Tk思考与活动展开','src/promptsmith/response_ui.py:244-396',14),('TkMarkdown回复','src/promptsmith/response_ui.py:142-241',21),('Tk输入组件','src/promptsmith/composer.py:263-568',10),('TkGlyphButton','src/promptsmith/composer.py:94-176',4)]
for name,loc,contract in new_defs:
    if not any(d['name']==name for d in a['definitions']):
        d=dict(id=f'DEF-{len(a["definitions"])+1:03}',name=name,kind='原生自绘组合/叶子',source_locator=loc,source_status='located')
        a['definitions'].append(d);CONTRACTS[int(d['id'][4:])]=CONTRACTS[contract]
    else:CONTRACTS[int(next(d['id'][4:] for d in a['definitions'] if d['name']==name))]=CONTRACTS[contract]
CONTRACTS.update({
 62:('执行原生对话动态工作流动作','ReplyButton(parent,text,command,theme)/invoke()/_conversation_buttons[key]','空/忙禁用、完成、失败恢复、阶段删除重建','command直接调用当前app业务方法；不独立确认或写SessionState','ttk.Button原生焦点/Return/space；动态重建后的回落逐实例核对','按palette浅深显示并随默认内存字体调整，不做HTML按钮'),
 63:('原生loop补答与整理深度/类型玻璃按钮','GlassButton(...command,icon_name,...)/Tween.start()','hover/按下/disabled、鼠标离开、弹层反向、销毁','补答传当前question_id；菜单选择交category/thinking变量，不伪造确认','Canvas绑定焦点和激活，真实辅助技术名称待验','圆形loop图标或胶囊文字；Pillow层在内存，Tween销毁取消'),
 64:('构造原生紧凑逐题回答及跳过','_inline_question(parent,row)/_question_inputs[id]/submit:{id}/SkipButton','空白禁用、有草稿、Enter提交、ShiftEnter换行、跳过、重建','单题提交走submit_guided_answer；草稿从控件采集并保留，整批统一M1','Tk Text平台输入；提交/跳过具有事件绑定；实际IME另验','两行高度，圆角原生Text背景及独立圆形提交/红色SkipButton'),
 65:('原生思考/活动层连续展开与流式显示','ResponseTrace(record)/toggle()/toggle_thought()/scroll_thought()/close()','working/done/failed/cancelled、展开/收起/反向、增量排空','AdaptiveWriter只用于显示；响应元数据按TaskScope投影，不回传思考','ChevronButton原生Canvas焦点，隐藏后代Tab及读屏按原生路径补证','RevealFrame两层有界裁切、chevron随Tween旋转、思考100%字号/滚轮独占'),
 66:('原生用户气泡和Markdown回复','MessageShell(...)/MarkdownText.render(content)/configure(state="disabled")','用户/AI、标题/列表/代码、长文、主题重绘','只渲染投影文本，HTML不作为可执行脚本；复制仍走当前结果','正文可原生选择复制；标题tag视觉层级不等于真实读屏层级','用户右侧气泡；MarkdownText真实Text标签，默认平台字体与长文折行'),
 67:('原生固定底部输入、模型与常驻发送','PromptComposer(app)/ComposerText/changed()/toggle_picker()/_destroyed()','空/有字/忙、placeholder、autogrow、选择模型/强度、菜单缓存','发送走send_conversation_message；同一确认接口内模型切换经原保存契约','Enter发送/ShiftEnter换行；模型/发送GlyphButton焦点；IME真机待验','原生文字避免字库生成；placeholder与插入光标同行，正文125%/模型100%'),
 68:('原生图形按钮焦点与激活','GlyphButton(command,arrow,choice,...)/configure(state)/invoke()','normal/disabled、focus、hover、press、主题与图标重绘','invoke执行当前command；disabled不调用，不改变业务版本','Canvas Return/space及focus绘制；真实Windows名称/角色待读屏','Pillow图形内存反锯齿，文字仍默认原生；圆形发送和模型按钮分开配置')
})

def append_cmp(page,label,definition,locator,critical=True):
    if any(c['page_id']==page and c['label']==label for c in a['instances']):return
    d=next(d for d in a['definitions'] if d['name']==definition)
    a['instances'].append(dict(id=f'CMP-{len(a["instances"])+1:03}',page_id=page,definition_id=d['id'],label=label,locator=locator+'; '+d['source_locator'],variant='动态合成状态/业务条件/隐藏与重开',criticality='high' if critical else 'normal',data_source='同一SessionState，不独立保存业务确认',notes='本轮深查补充：初始构造清单漏未绑定app.widgets的动态Canvas'))

append_cmp('PAGE-002','整合忙态取消入口（当前Web遗漏）','工作流按钮','state.buttons.cancel_request / 缺少DOM渲染')
for label in ['查找本地 Skill','继续联网查找','整合所选 Skill','用已选 Skill 直接生成','跳过 Skill','复制提示词','导出方案和提示词','保存会话','确认最终提示词','语气和附注','取消本次整合','继续询问','结束追问']:
    append_cmp('PAGE-023','动态回复动作 · '+label,'Tk动态回复按钮','ConversationWorkspaceMixin._conversation_buttons / '+label)
for label in ['补答loop','整理深度','任务类型']:
    append_cmp('PAGE-023','玻璃动作 · '+label,'Tk圆形/玻璃按钮','conversation/composer Canvas '+label)
for label in ['题意全文','多行回答','圆形提交','红色跳过']:
    append_cmp('PAGE-023','逐题 · '+label,'Tk逐题回答组合','_inline_question / '+label)
for label in ['处理外展开','思考子展开','独立思考滚动','活动内容']:
    append_cmp('PAGE-023','思考 · '+label,'Tk思考与活动展开','ResponseTrace / '+label,critical=label!='活动内容')
for label in ['用户气泡','提示词标题与正文']:
    append_cmp('PAGE-023','正文 · '+label,'TkMarkdown回复','MessageShell / MarkdownText / '+label,False)
for label in ['占位/插入光标/文本','选择模型','常驻发送']:
    append_cmp('PAGE-023','底部 · '+label,'Tk输入组件','PromptComposer / '+label)
append_cmp('PAGE-033','Canvas键盘焦点与激活','TkGlyphButton','GlyphButton focus/Return/space')

by_page=defaultdict(list)
for c in a['instances']:by_page[c['page_id']].append(c)
definitions={d['id']:d for d in a['definitions']}
pages={p['id']:p for p in a['pages']}
def ids(page=None,defs=None,labels=None):
    return [c['id'] for c in a['instances'] if (page is None or c['page_id'] in page) and (defs is None or c['definition_id'] in defs) and (labels is None or any(s in c['label'] for s in labels))]

# Root-cause findings are explicit judgments backed by observation files.
FINDINGS=[
('整合提示词忙态没有可见取消入口','P1','workflow',ids(['PAGE-002'],labels=['整合忙态']),['EV-005','EV-014'],
 '真实busy快照有cancel_request，Web无对应按钮；用户只能等请求或切换会话。','整合期间可取消当前请求并保留本会话与已选Skill。',
 'workspace.js只消费列举卡片动作；recovery受!locked限制，遗漏动态cancel_request投影。',
 '渲染显式cancel_request，沿用command("button")/cancel_delivery_request和request scope；不能解除所有业务保护。',
 '模拟未返回整合→点取消→当前会话解锁；迟到内容丢弃，仍可重试/直接生成。'),
('最大字号下小窗header越界','P2','layout',ids(['PAGE-001'],labels=['外壳','核对需求','核对方案','任务摘要','设置']),['EV-005','EV-011'],
 '720×440/font18展开侧栏，header右端超出窗口，设置按钮无法完整看见。','合法最小窗口与设置字号组合下顶部核心操作可达。',
 '展开侧栏固定占258px，header-actions不换行，响应式缩短仅覆盖收起侧栏。',
 '按可用内容宽度让header换行/收纳，调整expanded断点；避免删任务入口或压缩字体回避。',
 '720×440/font9/12/18，展开/收起，长标题及浅深主题检查每一header控件不被截断。'),
('小窗大字号设置正文与保存区域被挤出','P2','layout',ids([f'PAGE-{i:03}' for i in range(17,22)]),['EV-005','EV-006','EV-011'],
 '清洁720×440/font18：五类scroll仅36px；footer底488.5px，保存按钮跨422.5–488.5px，超过440px窗口。','设置正文可阅读且保存/恢复/返回全部能滚动到达。',
 'settings布局将heading/tabs/footer固定而scroll独自收缩；父容器overflow hidden无整页补偿。',
 '设置单一有界滚动，短窗允许footer入滚动内容或sticky精简；不要扩大应用最小窗口掩盖合法组合。',
 '干净与有草稿/错误长文两状态，五类在720×440/font18均能读完并点击完整保存按钮。'),
('模型浮层上界未约束，搜索和首供应商被裁切','P2','layout',ids(['PAGE-009'],labels=['外壳','搜索','供应商','列表']),['EV-006','EV-011'],
 '展开720×440：font12菜单top=-21px，font18=-78px且搜索top=-67px；收起font18菜单top=-3.5px。','菜单搜索、五供应商和四档强度在窗口内，可通过内部滚动查看模型。',
 'makePopup在填入内容前测量；用anchor bottom推位置，未针对最终高度钳制top。',
 '内容完成后测量；按可用上/下空间选择placement，夹取四边，模型列表承担剩余高度；resize重算。',
 '重放四个font12/18+rail组合，菜单bounds>=0且<=viewport；查询输入与首供应商可点击。'),
('公共dialog浮层缺可访问名称','P2','accessibility',ids(defs=['DEF-022'],page=['PAGE-005','PAGE-006','PAGE-007','PAGE-008','PAGE-009','PAGE-010','PAGE-011','PAGE-012']),['EV-002','EV-005'],
 '模型与核对面板role=dialog没有aria-label/labelledby，标题div未关联。','dialog有各自用途名称；菜单使用与交互一致的menu角色。',
 'makePopup统一role=dialog，调用者没有传名称；renderReview标题未赋ID。',
 'makePopup接收label或labelledby/trigger；dialog显式命名，文件/选择菜单使用menu契约。',
 '逐个模型、需求、方案、摘要、结果和菜单检查可访问树名称/角色，真实读屏再验。'),
('浮层焦点进入、返回及展开语义不完整','P2','accessibility',ids(page=['PAGE-001','PAGE-005','PAGE-006','PAGE-007','PAGE-008','PAGE-009','PAGE-010','PAGE-011','PAGE-012','PAGE-013','PAGE-014','PAGE-015','PAGE-016'],defs=['DEF-022','DEF-033'])+ids(['PAGE-001'],labels=['核对需求','核对方案','任务摘要']),['EV-005','EV-006','EV-002'],
 'review打开焦点仍在header；模型/深度Escape后焦点落body；rename退出时原行已重建导致returnFocus失效。review触发器无aria-expanded。','进入浮层时焦点到标题/首控件；关闭返回存活触发器，消失则合理后继；展开状态同步。',
 '公共closePopup不保存anchor；review不focus。历史保存旧DOM节点但后台重建整行。',
 '存储触发器稳定标识（history id+action），打开初始化焦点；关闭重新查询fallback。非模态panel不强制trap；history模态保留现有trap。',
 '鼠标/Enter打开、Tab/ShiftTab、Escape、点外部、快速替换；后台快照重建时焦点仍有业务上下文。'),
('需求表只有鼠标选择，键盘无法编辑指定需求','P1','accessibility',ids(['PAGE-005'],defs=['DEF-023']),['EV-005','EV-002'],
 'tbody tr没有tabIndex或button/input，仅click能选；键盘不能选择行读全文再编辑/移除。','键盘用户能选择任意需求、阅读详情并执行已授权核对。',
 'renderReview用tr.click完成selection，没有相应键盘可聚焦选择入口。',
 '每行加入原生单选/按钮或完整grid键盘模式；优先简单原生入口，传同一id保留后端selection校验。',
 '仅键盘选proposal/confirmed行，读全文、修改/取消、移除/取消；ID过期不误改邻行。'),
('收起思考后不可见内容仍进入Tab顺序','P2','accessibility',ids(['PAGE-002'],defs=['DEF-014','DEF-015']),['EV-005','EV-002'],
 '关闭外trace后Tab进入隐藏子展开按钮；thought tabindex=0也仍可达。','视觉关闭区不可聚焦；展开后恢复原键盘路径，动画继续。',
 'reveal只使用grid0fr/opacity/overflow裁切，没有inert或tabindex状态处理。',
 '关闭开始设置inert；若包含焦点先回展开器；打开解除。别删连续展开动画。',
 '外/内两层分别关闭，Tab及ShiftTab跳过所有隐藏后代；动画反转和stream完成时保持一致。'),
('搜索和重命名Enter未保护中文组合输入','P2','input',ids(page=['PAGE-009'],defs=['DEF-026'])+ids(page=['PAGE-014','PAGE-015'],defs=['DEF-034']),['EV-005','EV-006','EV-002'],
 '注入isComposing=true/keyCode229的Enter：历史搜索触发open，重命名触发save，模型搜索触发model选择。真实系统候选序列尚未记录。','候选确认不执行打开/保存/模型选择，下一次正常Enter按约定操作。',
 '这些keydown分支直接处理Enter，未使用消息输入已有的composition保护。',
 '抽出共享组合输入判断并应用三个入口，按Edge154真实事件序列补验，不无理由扩大全站快捷键拦截。',
 '单元注入与真实Windows中文输入法均验：候选Enter不dispatch；正常Enter只一次。'),
('设置Tab声明角色但缺方向键与单TabStop','P2','accessibility',ids(page=[f'PAGE-{i:03}' for i in range(17,22)],defs=['DEF-036']),['EV-005','EV-002'],
 'ArrowRight不切类别，五个role=tab都留在Tab序列；浅深一致。','tablist具方向键/Home/End与selected roving tabindex，字段草稿不丢。',
 'selectCategory仅hidden与aria-selected，build未注册keydown/tabIndex。',
 '复用供应商tab现有键盘模式，按水平设置Left/Right；状态由category唯一拥有。',
 '键盘遍历五类、保持未保存连接/数字草稿、返回再开；只有选中Tab在TabStop。'),
('Debug同步恢复后残留过期红色错误','P2','recovery',ids(['PAGE-022'],defs=['DEF-043']),['EV-005','EV-002'],
 'snapshot先抛错再恢复成功，#debug-error仍显示同步未完成；新日志已正常显示。','成功同步清除该次同步错误，同时不误清复制/保存/目录错误。',
 'poll.catch调用showError，成功分支不清，所有错误共用一个字符串。',
 '错误按operation归属；成功poll只清sync错误，动作结果清各自错误；更新Debug生命周期测试。',
 '同步失败→恢复、保存失败→同步成功、复制失败→重试成功三序列分别核对。'),
('原生保存创建目录失败未进入恢复提示','P2','recovery',ids(['PAGE-034'],labels=['保存','覆盖'])+ids(['PAGE-012'],labels=['save']),['EV-015','EV-003'],
 'Path.mkdir权限失败从app.save直接抛出，_show_error未调用；Web外层有通用捕获，但原生用户没有保存位置的下一步提示。','失败保留会话和旧文件，提示选择其它目录或重试。',
 '创建默认目录在save的try之外，捕获只围绕_sync_input和save_session。',
 '目录准备/选择/实际保存统一异常边界，明确无权限提示；保留用户取消为正常退出，Debug含完整cause。',
 'mkdir、写入、rename权限失败与用户取消分别验；原生与Web都保留当前会话，另存可恢复。'),
('14项旧UI测试仍依赖退役控件和旧合同','P2','maintainability',[],['EV-012','EV-001'],
 '退役details/requirements/answer/category控件KeyError；旧options、skipped必须补答、两款OpenAI与新合同不符；当前回归不能直接全绿。','测试按当前同一工作区、显式跳过、无选项建议、八款OpenAI核对实际用户结果。',
 '多轮UI迁移保留旧用例未同步，当前active布局不再构造其查询键。',
 '逐项迁移断言到当前入口和同等用户结果；保留历史失败记录；不可为测试恢复已删除界面或盲删安全断言。',
 '当前14失败节点迁移后专项通过，需求确认/冲突/复制/多行编辑等原目标继续保留。'),
]

a['findings']=[];a['scenarios']=[];a['tasks']=[];a['component_blueprints']=[];a['component_plans']=[]

def scenario(title,page_ids,instance_ids,steps,expected,status='planned',evidence_ids=None,findings=None,reason='',risk='high'):
    s=dict(id=f'SCN-{len(a["scenarios"])+1:03}',title=title,page_ids=page_ids,instance_ids=instance_ids,
        preconditions=['当前工作树；隔离合成任务/历史/设置；不操作个人资料或付费服务'],steps=steps,expected=expected,
        context=dict(role='Windows本机当前用户，无租户',data='合成Python学习/UI重设计目标；受管临时历史及假密钥',network='离线或模拟桥接；无真实模型/网络Skill请求',viewport='1440×810及注明的720×440/font12或18',input='鼠标/键盘自动化；IME若涉及为事件注入，真实候选另列',lifecycle='本轮构造、重开/退出及受控中断；非EXE'),
        risk=risk,status=status,evidence_ids=evidence_ids or [],finding_ids=findings or [],reason=reason)
    a['scenarios'].append(s);return s['id']

for n,(title,severity,category,components,evidence,actual,expected,cause,fix,regression) in enumerate(FINDINGS,1):
    fid=f'FND-{n:03}';components=list(dict.fromkeys(components))
    ps=sorted({c['page_id'] for c in a['instances'] if c['id'] in components})
    ds=sorted({c['definition_id'] for c in a['instances'] if c['id'] in components})
    f=dict(id=fid,title=title,category=category,severity=severity,confidence='confirmed',status='open',owner='前端/UI开发' if n!=13 else '测试维护者',page_ids=ps,instance_ids=components,definition_ids=ds,check_ids=[],scenario_ids=[],evidence_ids=evidence,actual=actual,expected=expected,impact=expected+'目前不能保证；'+('键盘核心任务被阻断。' if severity=='P1' and n==7 else '整合等待时不能在当前会话停止。' if severity=='P1' else '可恢复但影响操作/诊断或回归可信度。'),root_cause=cause,root_cause_confidence='confirmed',remediation=fix,regression_test=regression,reproduction=dict(preconditions=['本轮记录的合成状态；具体几何/注入/测试节点见EV'],steps=[actual,'按evidence对应脚本重放并检查原始actual/expected值']),resolution_evidence_ids=[])
    sid=scenario('复现 '+title,ps or ['PAGE-001'],components,[actual,'检查对应DOM/原生返回或JUnit断言'],[expected],status='failed',evidence_ids=evidence,findings=[fid])
    f['scenario_ids']=[sid];a['findings'].append(f)
    tid=f'TASK-{n:03}'
    a['tasks'].append(dict(id=tid,title=title,phase=1 if severity=='P1' else 2 if n<=10 else 3,phase_name='核心缺陷' if severity=='P1' else '共享交互/布局' if n<=10 else '恢复与回归',owner=f['owner'],scope_ids=components or ['PRJ-001'],finding_ids=[fid],depends_on=['TASK-005'] if n==6 else [],change_locations=[definitions[d]['source_locator'] for d in ds] or ['tests/test_experience_iteration.py; tests/test_guided_ui.py; tests/test_ui_delivery_interactions.py; tests/test_composer.py; tests/test_ui_contract.py'],implementation_steps=[fix,'同步Debug诊断：事件、阶段、完整exception cause与脱敏；不自动写日志。'],acceptance_criteria=[regression],verification_scenario_ids=[sid],rollback='按局部补丁恢复展示/事件层，保留SessionState/DPAPI/历史格式与已保存数据；不恢复已取消旧产品能力。',risk='焦点/动画/版本检查互相影响；修复不绕过业务确认。',status='planned',evidence_ids=evidence))

# Actual page observations: source and runtime are deliberately distinct.
runtime_ev={i:['EV-005','EV-006','EV-007'] for i in range(1,23)}
runtime_ev.update({23:['EV-010','EV-007','EV-020'],24:['EV-010','EV-012','EV-017','EV-020'],25:['EV-010','EV-012','EV-018','EV-020'],26:['EV-010','EV-007','EV-017','EV-020'],27:['EV-010','EV-007','EV-019','EV-020'],28:['EV-010'],29:['EV-010'],30:['EV-010'],31:['EV-017'],32:['EV-010','EV-007'],33:['EV-012','EV-020']})
page_scenarios={}
for p in a['pages']:
    n=int(p['id'][5:]);allids=[c['id'] for c in by_page[p['id']]]
    # This scenario covers the concrete observation scope described, not every child action.
    status='passed' if n!=34 else 'blocked'
    scope='当前页构造/投影与报告中的受控状态' if n not in [28,29,30,32] else '真实原生保存/取消及记录的错误/Debug操作'
    sid=scenario(p['title']+'：'+scope,[p['id']],allids,[PAGE_NOTES[n],'对照本页证据中的已执行条件；未执行的真实服务/系统输入另列'],['页面入口对应当前业务投影；测试与截图所覆盖的返回/状态符合其显式断言'],status=status,evidence_ids=runtime_ev.get(n,[]),reason='' if n!=34 else '原生Windows OS文件选择器、覆盖与读屏交互未获可用原生自动化；已做磁盘/取消/异常的离线测试。需目标机人工补验，不用模拟选路径冒充实机。')
    page_scenarios[p['id']]=sid

blocked_sid=scenario('真实系统输入/辅助技术/跨DPI/EXE/真实供应商边界',list(pages),[c['id'] for c in a['instances']],
 ['在目标Windows用真实中文候选确认、Narrator/屏幕阅读器完成核心旅程','跨DPI与180Hz实屏采样；隔离EXE跨机启动','使用获准的模型和网络Skill样本核对结果及超时/403恢复'],
 ['不误提交；控件名称与焦点可用；EXE资源与模型协议正确；实际帧和服务质量有证据'],status='blocked',reason='本轮未使用真实付费模型、生产凭据、跨机EXE、180Hz外部帧采集或系统输入法/读屏操作；浏览器注入和实验室rAF不能替代这些证据。')

TASK_ACCESS='TASK-014'
a['tasks'].append(dict(id=TASK_ACCESS,title='补齐平台与真实服务验收',phase=4,phase_name='发布前补证',owner='Windows验收者/模型集成开发',scope_ids=['PRJ-001']+list(pages),finding_ids=[],depends_on=[f'TASK-{i:03}' for i in range(1,14)],change_locations=['verification/ 下一批验收记录；PromptSmith.spec；真实Windows目标设备'],implementation_steps=['按verification-handoff逐条运行真实候选输入/读屏/跨DPI/180Hz和独立EXE测试','真实模型及联网Skill仅使用下一轮获准凭据和预算；保留失败样本、推荐结果与完整脱敏日志'],acceptance_criteria=['每个blocked检查附对应环境/步骤/结果，不以DOM模拟替代真实平台','13项本轮问题复验及EXE/真实模型界限分别报告'],verification_scenario_ids=[blocked_sid],rollback='只补证；如需应用改动另以局部任务执行，不操作用户原历史或覆盖生产settings。',risk='服务成本、不同电脑运行时与输入法事件差异；当前不能承诺180Hz或完整WCAG符合性。',status='blocked',evidence_ids=[]))
local_sid=scenario('逐实例补验尚未运行的条件动作和组件生命周期',list(pages),[c['id'] for c in a['instances']],
 ['按各CMP locator和BP构造缺少的合法状态；优先复用本轮已有离线fixture','逐个执行未覆盖动作并核对确认失效、退出与资源清理，登记实例ID和具体测量'],
 ['有本实例的运行结果，或明确不适用理由；不继承父页/共享模块全部通过'],reason='可在本地继续执行；当前运行证据不足，属于planned而非环境blocked。')
TASK_LOCAL='TASK-015'
a['tasks'].append(dict(id=TASK_LOCAL,title='补齐本地逐实例条件动作与生命周期证据',phase=0,phase_name='补证基线',owner='UI开发/离线验收',scope_ids=[c['id'] for c in a['instances']],finding_ids=[],depends_on=[],change_locations=['各CMP定位；本目录scripts与evidence'],implementation_steps=['按not_checked检查逐实例补合法状态/动作，不用页面构造替代回调','性能仅测实际独立计时器/缓存/布局；无独立生命周期的静态叶子注明归属父单元'],acceptance_criteria=['not_checked逐条闭合，证据包含实例、前提、步骤、结果','继续区分真实平台blocked，不伪造通过'],verification_scenario_ids=[local_sid],rollback='只增补隔离证据，恢复临时目录，不写个人配置或修改应用。',risk='原生条件控件和测试旧合同可能混淆；保持明确当前入口。',status='planned',evidence_ids=[]))

# Evidence is linked to specific observations rather than inherited from a page.
native_observed={cid for obs in json.loads((OUT/'evidence/native-supplement.json').read_text(encoding='utf-8'))['observations'] if obs['passed'] for cid in obs['instance_ids']}
native_final_observed={cid for obs in json.loads((OUT/'evidence/native-final-actions.json').read_text(encoding='utf-8'))['checks'] if obs['passed'] for cid in obs['instance_ids']}
native_test_labels={
 23: {'Text','conversation_skill_source_filter','conversation_skill_show_all','conversation_skill_candidates_tree','conversation_skill_select_skills','conversation_skill_cancel_skills','conversation_skill_details_text','conversation_input','conversation_composer','conversation_model_button','conversation_send_button',
      '动态回复动作 · 查找本地 Skill','动态回复动作 · 继续联网查找','动态回复动作 · 整合所选 Skill','动态回复动作 · 用已选 Skill 直接生成','动态回复动作 · 跳过 Skill','动态回复动作 · 复制提示词','动态回复动作 · 导出方案和提示词','动态回复动作 · 保存会话','动态回复动作 · 确认最终提示词','动态回复动作 · 语气和附注','动态回复动作 · 取消本次整合','动态回复动作 · 继续询问','动态回复动作 · 结束追问',
      '玻璃动作 · 补答loop','玻璃动作 · 整理深度','玻璃动作 · 任务类型','逐题 · 题意全文','逐题 · 多行回答','逐题 · 圆形提交','逐题 · 红色跳过','思考 · 处理外展开','思考 · 思考子展开','思考 · 独立思考滚动','思考 · 活动内容','正文 · 用户气泡','正文 · 提示词标题与正文','底部 · 占位/插入光标/文本','底部 · 选择模型','底部 · 常驻发送'},
 24: {'confirm_plan_button','review_key_work_button','generate_plan_button'},
 25: {'skill_find_button','skill_online_button','skill_search_url_entry','skill_select_button','skill_analyze_button','skill_cancel_button','skill_cancel_request_button','skill_skip_button','skill_integrate_button','skill_direct_button','skill_source_filter','skill_show_all','skill_candidates_tree','skill_selected_tree','skill_details_text','skill_prerequisites_tree','skill_prerequisite_status_combo','skill_update_prerequisite_button'},
 26: {'生成无 Skill 草稿','确认当前最终结果','final_tone_combo','copy_draft_button','copy_final_button','导出 Markdown','导出草稿','final_task_prompt_text','m2_suggestions_tree','m2_suggestion_details_text','accept_m2_suggestion_button','reject_m2_suggestion_button','process_m2_suggestion_button','m4_changes_tree','m4_change_details_text','accept_m4_change_button','reject_m4_change_button','final_review_items_tree','final_review_details_text','process_final_review_item_button','添加用户附注','复制提示','导出方案和提示','保存会话','修改方案'},
 27: {'provider_combo','protocol_combo','api_base_entry','api_model_entry','api_key_entry','model_list_button','test_connection_button','confirm_model_settings_button','settings_return_button','settings_restore_button','settings_save_button','debug_console_toggle'}
}

# Static evidence is specific to renderer; no construction-only behavior pass.
a['checks']=[]
def check(scope,target,dimension,question,status,evidence=None,scenarios=None,findings=None,reason=''):
    c=dict(id=f'CHK-{len(a["checks"])+1:04}',scope=scope,target_id=target,dimension=dimension,question=question,status=status,evidence_ids=evidence or [],scenario_ids=scenarios or [],finding_ids=findings or [],reason=reason)
    a['checks'].append(c)
    for fid in findings or []:next(f for f in a['findings'] if f['id']==fid)['check_ids'].append(c['id'])
    return c

check('project','PRJ-001','reproducibility','当前资源/版本与可执行测试是否形成可信回归基线？','failed',['EV-012','EV-013'],[a['findings'][12]['scenario_ids'][0]],['FND-013'])
check('project','PRJ-001','architecture','业务权威、Tk所属线程和Web公开快照是否分离且拒绝过期操作？','passed',['EV-003','EV-007','EV-009'])
check('project','PRJ-001','security_boundaries','密钥是否不进入公共快照/会话/明文settings，正文是否不能执行HTML？','passed',['EV-007','EV-006','EV-013'])
check('project','PRJ-001','delivery_observability','运行诊断是否覆盖完整异常且只在手动保存后写文件？','passed',['EV-007','EV-008','EV-010'])
check('project','PRJ-001','reproducibility','独立EXE及跨机资源/运行时是否已复验？','blocked',scenarios=[blocked_sid],reason='未构建或运行独立EXE；spec静态资源声明不证明打包成功。')

for p in a['pages']:
    pid=p['id'];n=int(pid[5:]);source=['EV-002'] if n<=22 else ['EV-003','EV-016']
    fs=[f for f in a['findings'] if pid in f['page_ids']]
    for dimension,question in [('routing_history','入口、退出和业务阶段是否与当前投影一致？'),('state_coverage','已执行合成状态/恢复路径是否保持当前对象与草稿？'),('responsive_content','已观察主题/默认布局与注明的小窗组合是否无不可达内容？'),('journey_integration','确认、取消及复制/导出是否沿现有业务方法而不假确认？')]:
        affected=[f for f in fs if (dimension=='responsive_content' and f['category']=='layout') or (dimension=='journey_integration' and f['id'] in ['FND-001','FND-007','FND-012'])]
        if affected:check('page',pid,dimension,p['title']+'：'+question,'failed',list(dict.fromkeys(e for f in affected for e in f['evidence_ids'])),[s for f in affected for s in f['scenario_ids']],[f['id'] for f in affected])
        elif n==34:check('page',pid,dimension,p['title']+'：'+question,'blocked',scenarios=[page_scenarios[pid]],reason='OS选择器真实交互缺口见SCN；业务与文件异常已单独静态/模拟核对。')
        else:check('page',pid,dimension,p['title']+'：'+question+'（仅本页已记录条件）','passed',source+runtime_ev[n],[page_scenarios[pid]])

for c in a['instances']:
    did=c['definition_id'];dn=int(did[4:]);pn=int(c['page_id'][5:]);contract=CONTRACTS[dn];source=['EV-002'] if pn<=22 else ['EV-003','EV-016']
    runtime=runtime_ev.get(pn,[]);sid=page_scenarios[c['page_id']]
    fs=[f for f in a['findings'] if c['id'] in f['instance_ids']]
    # Native leaf observations cannot prove every callback; keep that boundary visible.
    native_leaf=23<=pn<=27
    for dimension,index in [('behavior',1),('states',2),('semantics_accessibility',4),('layout_content',5),('data_effects',3),('security_privacy',3),('performance_lifecycle',0),('maintainability_integration',1)]:
        question=c['label']+' @ '+c['locator']+'：'+contract[index]
        affected=[f for f in fs if (dimension in ['behavior','states'] and f['category'] in ['workflow','recovery','input']) or (dimension=='semantics_accessibility' and f['category'] in ['accessibility','input']) or (dimension=='layout_content' and f['category']=='layout') or (dimension=='maintainability_integration' and f['category']=='maintainability')]
        if affected:
            check('component',c['id'],dimension,question,'failed',list(dict.fromkeys(e for f in affected for e in f['evidence_ids'])),[s for f in affected for s in f['scenario_ids']],[f['id'] for f in affected]);continue
        if pn==34 and dimension in ['behavior','states','semantics_accessibility','layout_content','performance_lifecycle']:
            check('component',c['id'],dimension,question,'blocked',scenarios=[sid],reason='本实例属于真实Windows文件选择器；没有将路径mock当作UI交互。需按PAGE-034人工步骤补证。');continue
        if pn==34:
            check('component',c['id'],dimension,question+'（业务代码的保存/安装边界，非OS界面验证）','passed',source+['EV-007','EV-013']);continue
        if dimension=='semantics_accessibility' and pn>=23:
            check('component',c['id'],dimension,question+'（真实平台辅助技术）','blocked',scenarios=[blocked_sid],reason='已读原生键盘/标签与部分Tab操作，实际Windows读屏可访问名称/角色尤其Canvas未执行；没有从Tk视觉推断播报。');continue
        if dimension=='performance_lifecycle':
            if dn in [14,15,22]:
                check('component',c['id'],dimension,question+'；本轮对应展开/流式场景是否有连续更新（非长期/180Hz证明）？','passed',source+['EV-008'],[sid])
            elif dn in [1,10,19,21,26,33]:
                check('component',c['id'],dimension,question+'；对应视图/浮层反复建立和退出后DOM是否有残留，布局耗时是否记录？','passed',source+['EV-021'],[sid])
            elif dn in [42]:
                check('component',c['id'],dimension,question+'；显示缓存有界、完整归档独立且Debug窗口关闭是否退出？','passed',source+['EV-007','EV-008'],[sid])
            elif dn in [44,55,56,57,59,60,63,65,67]:
                check('component',c['id'],dimension,question+'；对应实际关闭/保存取消是否销毁窗口并取消持有的writer/after/动画（不含长期堆内存）？','passed',source+(['EV-010'] if dn in [55,56,57] else ['EV-022'] if dn==63 else ['EV-007','EV-012','EV-020']),[sid])
            elif dn in [2,3,4,5,6,7,8,9,11,12,13,16,17,18,20,23,24,25,27,28,29,30,31,32,34,35,36,37,38,39,40,41,43,45,46,47,48,49,50,51,52,53,54,58,62,64,66,68]:
                check('component',c['id'],dimension,c['label']+'：是否承担独立轮询、动画计时器或持续缓存？','not_applicable',source,reason='本叶子没有独立性能/计时器生命周期；事件与数据副作用在本实例其它维度核对，持续调度/布局归属父页、输入组合或浮层。不能把本项不适用当作整体性能通过。')
            else:
                check('component',c['id'],dimension,question+'；本实例持续调度/缓存/销毁是否有实际测量？','not_checked',source,scenarios=[local_sid],reason='已静态核对资源归属，尚无针对本实例的完整生命周期测量；本地可继续，不能用source代替runtime或套用共享动画数据。')
            continue
        if dimension in ['behavior','states'] and native_leaf:
            if dn in [45,47]:
                check('component',c['id'],dimension,question+'（无独立交互/状态）','not_applicable',source,reason='静态label；文案和条件可见性归layout_content及消费者状态投影，不另虚构点击或请求状态。');continue
            if pn==27 and c['label'].startswith('setting_'):
                check('component',c['id'],dimension,question+'（实际字段编辑、保存恢复；数字无效文本失败保持旧值）','passed',source+['EV-019'],[sid]);continue
            if c['id'] in native_observed or c['id'] in native_final_observed or c['label'] in native_test_labels.get(pn,set()):
                specific=['EV-020'] if c['id'] in native_final_observed else ['EV-017'] if c['id'] in native_observed else ['EV-007','EV-012']
                if pn==25 or c['label'].startswith('conversation_skill_'):specific+=['EV-018']
                check('component',c['id'],dimension,question+'（仅明确执行的回调/受控状态，非穷举全部组合）','passed',source+specific,[sid]);continue
            check('component',c['id'],dimension,question+'（本实例尚缺条件动作）','not_checked',source,scenarios=[local_sid],reason='本地控件已经构造并读源码；未获得该具体动作/完整状态的运行结果。可用隔离合法fixture继续；属于未检查，非环境阻塞。');continue
        evidence=source+runtime if dimension in ['behavior','states','layout_content'] else source+['EV-007','EV-013']
        check('component',c['id'],dimension,question+('（源码契约）' if dimension in ['data_effects','security_privacy','maintainability_integration'] else '（本页已执行受控状态）'),'passed',list(dict.fromkeys(evidence)),[sid])
    # Make real device and duration gaps atomic instead of silently inheriting pass.
    if did in ['DEF-010','DEF-034','DEF-039','DEF-052','DEF-053','DEF-054','DEF-064','DEF-067']:
        check('component',c['id'],'behavior',c['label']+'：真实Windows候选确认是否不会触发提交或覆写？','blocked',scenarios=[blocked_sid],reason='只做过DOM composing事件注入/程序化Text编辑；未记录真实系统候选事件序列。')

# The local supplement is finished; platform-only gaps remain distinct.
local_components=native_observed|native_final_observed|{'CMP-476','CMP-477','CMP-478'}|set(ids(['PAGE-027'],labels=['setting_']))
local_scenario=next(s for s in a['scenarios'] if s['id']==local_sid)
local_scenario.update(instance_ids=sorted(local_components),status='passed',evidence_ids=['EV-017','EV-019','EV-020','EV-021','EV-022'],reason='',
 steps=['真实Tk逐个30字段编辑/保存读取与17项数字拒绝','18项编辑/短输入，25项原生滚动/剩余入口/计时器清理，3个玻璃实例生命周期','Chrome20次阶段循环100布局与8项关闭/无残留核对；模拟回调和实际控件操作分开'],
 expected=['全部补验显式断言通过；静态叶子无独立调度按职责不适用；平台缺口仍保留blocked'])
next(t for t in a['tasks'] if t['id']==TASK_LOCAL).update(scope_ids=sorted(local_components),status='verified',evidence_ids=local_scenario['evidence_ids'])

# Every definition has an actual contract; every instance has one disposition.
for d in a['definitions']:
    n=int(d['id'][4:]);r,i,s,data,key,layout=CONTRACTS[n]
    fs=[f for f in a['findings'] if d['id'] in f['definition_ids']]
    security=('key_action/DPAPI仅Python可信层，公开投影无密钥。' if n==39 else '文本/ID由业务层校验；本组件不安装或执行Skill，也不直接读取个人文件。' if n<=43 else 'Tk线程拥有控件；业务写操作走原SessionState，日志脱敏，系统选择必须来自用户明确动作。')
    perf=('TraceView按16ms增量追赶；关闭取消rAF，按Intl.Segmenter保持Unicode；真实WebView2长文排空有123次更新。' if n in [14,15] else '不增加组件独立轮询；共享snapshot 100ms，Debug150ms；保留现有增量/signature检查及销毁清理。' if n<=43 else '保留after/trace解绑与图片内存缓存界限；主线程仅Tk更新，阻塞业务放既有executor。')
    obs=('将'+','.join(f['id'] for f in fs)+'复现条件写入Debug，完整cause和task/request上下文脱敏，日志仍手动保存。' if fs else '沿现有command/后台日志记录失败及生命周期；静态label/图标不增加每帧日志。')
    a['component_blueprints'].append(dict(id=f'BP-{n:03}',definition_id=d['id'],current_contract=d['name']+'位于 '+d['source_locator']+'。'+i+'。现状问题：'+('；'.join(f['actual'] for f in fs) if fs else '本轮未确认该定义的缺陷，范围与阻塞见实例检查；不宣称全部真实环境通过。'),target_contract=dict(responsibility=r,interface=i,states=s,data_effects=data,semantics_accessibility=key,styling_layout=layout,performance_lifecycle=perf,security_privacy=security,observability=obs,integration='消费者：'+','.join(sorted({c['page_id'] for c in a['instances'] if c['definition_id']==d['id']}))+'。继续共用SessionState和Workflow；'+('共享浮层先修名称/placement，再迁移所有调用者。' if n==22 else '原生兼容与Web呈现分开验收，不能将构造当完整旅程通过。')),change_locations=[d['source_locator']]))

for c in a['instances']:
    relevant=[f for f in a['findings'] if c['id'] in f['instance_ids']]
    checks=[k for k in a['checks'] if k['scope']=='component' and k['target_id']==c['id']]
    blocked=any(k['status']=='blocked' for k in checks)
    unchecked=any(k['status']=='not_checked' for k in checks)
    incomplete=blocked or unchecked
    task_ids=[f'TASK-{int(f["id"][4:]):03}' for f in relevant]
    disposition='refactor' if relevant else 'investigate' if incomplete else 'retain'
    if blocked:task_ids.append(TASK_ACCESS)
    if unchecked:task_ids.append(TASK_LOCAL)
    finding_ids=[f['id'] for f in relevant]
    a['component_plans'].append(dict(instance_id=c['id'],blueprint_id='BP-'+c['definition_id'][4:],disposition=disposition,rationale='本位置 '+c['page_id']+' / '+c['label']+'：'+('已复现 '+','.join(finding_ids)+'，按共享根因修改本调用处。' if relevant else '源码及可得证据未发现确定偏差；'+('具体运行/平台证据不足，先补证后决定保留或变更。' if incomplete else '保留当前职责，限定在已执行条件。')),instance_changes=['本实例定位：'+c['locator'],'数据/状态差异：'+c.get('notes','')+'；'+c['variant']]+([f['remediation'] for f in relevant] or ['不引入新样式或确认门槛；'+('补运行与平台证据，不预先改实现。' if incomplete else '保持当前行为。')]),finding_ids=finding_ids,task_ids=list(dict.fromkeys(task_ids)),acceptance_criteria=[c['label']+'在 '+pages[c['page_id']]['title']+' 的入口、禁用/退出与完整文案符合BP；按本实例原locator及业务ID复验',*(f['regression_test'] for f in relevant),*(['补齐该实例blocked/not_checked维度，真实平台与本地待验分开；不得套用其它位置通过。'] if incomplete else [])],regression_scenario_ids=list(dict.fromkeys([page_scenarios[c['page_id']],*[s for f in relevant for s in f['scenario_ids']],*([blocked_sid] if blocked else []),*([local_sid] if unchecked else [])]))))

a['project']['inventory_status']='reconciled'
a['project']['baseline']['runtime_ref']='当前工作树：Chrome154模拟桥接、真实Edge154/WebView2与Tk；隔离离线合成数据；非EXE'
a['project']['scope']='34个独立任务/虚拟页、68个共享定义与全部已发现逻辑UI实例；包含默认Web、独立Debug、可达Tk编辑/回退与OS选择器。覆盖以台账为准，运行/设备阻塞明确保留。'
a['release_gates']=[dict(id='GATE-001',name='核心流程的当前取消与键盘核对入口',required=True,status='failed',evidence_ids=['EV-005','EV-014'],reason='FND-001/FND-007未修'),dict(id='GATE-002',name='支持小窗+合法字号不阻断核心操作',required=True,status='failed',evidence_ids=['EV-005','EV-006'],reason='FND-002/003/004未修'),dict(id='GATE-003',name='密钥/草稿/完整诊断与业务版本保护',required=True,status='passed',evidence_ids=['EV-007','EV-008','EV-009','EV-013'],reason='本轮离线及真实源码环境内验证通过，非跨机证明'),dict(id='GATE-004',name='独立EXE与系统输入/真实模型/长期性能',required=True,status='blocked',evidence_ids=[],reason='缺独立EXE、真输入法/读屏/跨DPI/180Hz实屏及真实服务质量证据'),dict(id='GATE-005',name='当前UI回归合同可执行且没有未解释失败',required=True,status='failed',evidence_ids=['EV-012'],reason='14个旧合同失败；批量3秒异步超时隔离复验通过，不能伪装全绿')]
a['progress']=dict(current_page=None,completed_batches=['全量发现和原生动态漏项补账','Web静态+127项DOM观察与截图目视','真实WebView2主窗/Debug/两次历史恢复','真实Tk五页/编辑/Debug21项','430个不同定向/相邻测试节点，416通过/14旧合同失败独立解释','全部共享蓝图/逐实例处置/问题任务已落盘；本地补验93项与8项浏览器生命周期通过'],next_actions=['按TASK-001~013处理确认缺陷与测试合同','按TASK-014补真实平台/服务；TASK-015本地补验已完成'],unresolved_access=['真实系统IME/辅助技术与跨DPI/180Hz/EXE/付费模型未执行','本地原先not_checked经TASK-015补验或按静态职责明确不适用，未继承父页全部通过'],last_updated=now)
(OUT/'audit.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Readable reports are generated from the same ledger, with evidence limits.
def write(path,text):
    p=OUT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
for p in a['pages']:
    pid=p['id'];n=int(pid[5:]);text=f'# {pid} · {p["title"]}\n\n入口：`{p["route"]}`。源码：`{p["source_locator"]}`。\n\n{PAGE_NOTES[n]}\n\n变体：'+ '、'.join(p['variants'])+'。\n\n本页全部逻辑实例（不是抽样）：\n\n|实例|单元/定位|处置|问题|未闭合维度|\n|---|---|---|---|---|\n'
    for c in by_page[pid]:
        plan=next(x for x in a['component_plans'] if x['instance_id']==c['id'])
        gap=sorted({k['dimension'] for k in a['checks'] if k['target_id']==c['id'] and k['status'] in ['blocked','not_checked']})
        text+=f'|{c["id"]}|{c["label"]} · `{c["locator"]}`|[{plan["disposition"]}](../components/{plan["blueprint_id"]}.md)|'+(', '.join(plan['finding_ids']) or '无确定发现')+'|'+(', '.join(gap) or '已判定，范围见检查问题')+'|\n'
    text+='\n本页SCN：'+page_scenarios[pid]+'；EV：'+','.join(runtime_ev.get(n,[]))+'。每实例八维的具体问题、判定与证据在[audit.json](../audit.json)，blocked/not_checked/not_applicable均不计为通过。\n'
    text+='\n本页问题：'+('、'.join(f['id'] for f in a['findings'] if pid in f['page_ids']) or '当前没有确定缺陷；不代表未执行环境通过。')+'。保留正常业务结果、草稿与显式确认；平台补证按TASK-014，已完成本地补验见TASK-015，不删除原实例范围。\n'
    write('pages/'+pid+'.md',text)
for bp in a['component_blueprints']:
    d=definitions[bp['definition_id']];text=f'# {bp["id"]} · {d["name"]}\n\n源码：`{d["source_locator"]}`。\n\n'+bp['current_contract']+'\n\n'
    for key,value in bp['target_contract'].items():text+=f'**{key}**：{value}\n\n'
    text+='全部实例的主处置与本位置差异：\n'
    for plan in a['component_plans']:
        if plan['blueprint_id']!=bp['id']:continue
        c=next(x for x in a['instances'] if x['id']==plan['instance_id'])
        text+=f'\n## {c["id"]} · [{pages[c["page_id"]]["title"]}](../pages/{c["page_id"]}.md) / {c["label"]}\n\n'+plan['rationale']+'\n\n'+ '\n'.join('- '+v for v in plan['instance_changes'])+'\n\n验收：'+ '；'.join(plan['acceptance_criteria'])+'\n\n场景：'+','.join(plan['regression_scenario_ids'])+'。任务：'+(','.join(plan['task_ids']) or '无变更任务，保留当前契约')+'。\n'
    write('components/'+bp['id']+'.md',text)
text='# 确认问题与复验\n\n共13个合并根因；P1两个，P2十一个。未改源码，全部open。真实IME候选影响未冒充实测。\n'
for f in a['findings']:
    text+=f'\n## {f["id"]} · {f["severity"]} · {f["title"]}\n\n位置：'+(','.join(f['page_ids']) or '项目回归基线')+'；'+(','.join(f['definition_ids']) or '测试文件')+'。实例：'+(','.join(f['instance_ids']) or '不伪造页面实例')+'。\n\n实际：'+f['actual']+'\n\n预期与影响：'+f['expected']+' '+f['impact']+'\n\n根因（'+f['root_cause_confidence']+'）：'+f['root_cause']+'\n\n复现：'+ '；'.join(f['reproduction']['steps'])+'\n\n证据：'+','.join(f['evidence_ids'])+'（[台账证据索引](audit.json)）。\n\n修改机制：'+f['remediation']+'\n\n复验：'+f['regression_test']+'\n\n负责人：'+f['owner']+'；任务：TASK-'+f['id'][4:]+'；状态open，尚无修复后证据。\n'
write('findings.md',text)

text='# 逐步整改计划\n\n当前是audit_plan，13项修复均未实施。TASK-015是本轮已完成的补验，不是应用修复。优先保证当前会话取消和键盘核对，再修改共享浮层/小窗布局，最后清理诊断和测试契约；沿用WebView2，不建议再换框架。\n\n共享改动顺序：makePopup命名/placement → 焦点进入返回 → 每调用者菜单模式；其它任务仅在依赖明确时排序。保持本次已验证的滑块/连续动画、默认字体、SessionState、DPAPI和手动日志。\n'
for t in a['tasks']:
    text+=f'\n## {t["id"]} · {t["title"]}\n\n阶段：{t["phase"]}；负责人：{t["owner"]}；状态：{t["status"]}。依赖：'+(','.join(t['depends_on']) or '无')+'。\n\n位置：'+ '; '.join(t['change_locations'])+'\n\n'+ '\n'.join('- '+s for s in t['implementation_steps'])+'\n\n验收：'+ '；'.join(t['acceptance_criteria'])+'\n\n验证场景：'+','.join(t['verification_scenario_ids'])+'。\n\n恢复：'+t['rollback']+'\n\n风险：'+t['risk']+'\n'
write('refactor-plan.md',text)
write('verification-handoff.md','# 验收交接\n\n必须区分Chrome模拟桥接、真实WebView2源码、Tk程序化交互、系统人工输入、真实模型和EXE；本轮没有把它们混计。\n\n1. 重放13个FND脚本/节点，保留修复前EV，新增修复后EV，不覆盖老证据。\n2. 全部Web浮层检查打开/关闭/反向/点外部/背景快照/只用键盘；需求表选择及思考两层Tab必须成立。\n3. 720×440，pt9/12/18，展开/收起，浅深，设置错误/草稿长文；读完所有类并完整点击保存。\n4. 模型/历史查询与rename用真实Windows中文候选输入，记录composition及Enter顺序；DOM注入不等于真机。\n5. 原生兼容每个investigate实例按其locator展开，准备有效方案/绑定/最终状态，用真实辅助技术与系统输入核对；本轮已补主要本地动作，读屏/真实候选及跨DPI条件仍须独立记录，不能从局部成功继承。\n6. Narrator或可用读屏器完成发目标、核对、模型/Tab和删除取消；验证自绘Canvas真实名称与焦点。\n7. 独立EXE在干净Windows与不同DPI启动、退出、无WebView2降级，核对资源、DPAPI同用户恢复与其它用户失败；不复制个人密钥。\n8. 对180Hz设备录制实际呈现，长时间快速滚动/开关/大历史/长Debug测资源和交互延迟；本轮rAF间隔不等于180Hz达标。\n9. 下一轮获得明确预算后，真实模型和联网Skill样本验证完成/超时/403/取消与最终质量；不要仅为样式收费调用。\n10. 修复测试旧合同，保留原目标的实际用户结果，按最新不同节点汇总，不报告全部430次执行为不同节点。\n\n只做局部复验并覆盖同DEF其它位置； passing checks不无理由重复。所有新增行为同步Debug，运行日志仅点保存才写盘。\n')

stats=Counter(k['status'] for k in a['checks']);plans=Counter(p['disposition'] for p in a['component_plans'])
summary=f'''# PromptSmith 完整前端审查（2026-10-11）

已核对全部可得入口，覆盖34个逻辑页、{len(a['definitions'])}个共享定义、{len(a['instances'])}个实例；每实例八维检查和唯一处置、每定义十维蓝图已落盘。审查与方案已交付，**运行覆盖尚未完全闭合，产品不满足发布门槛**。未修改应用源码。

基线为`6fd857659ec6fe1c8e83c4fb61841e50d593731b`加当前未提交工作树，[源码SHA256](evidence/source-manifest.json)固定版本。应用源码与运行资源未改，HANDOFF/UI指南仅新增审查入口；初始SHA256清单保留，最终差异见[evidence/final-integrity.json](evidence/final-integrity.json)。已有用户/前轮改动全部保留；默认WebView2、独立Debug、可达Tk兼容编辑/显式回退、OS文件选择器全部在范围。历史archive不是本轮指令。

重点是2项P1：整合忙态未渲染取消按钮，需求表不能用键盘选择。另有11项P2，包含小窗header/设置/模型菜单裁切、dialog名称/焦点、隐藏思考进入Tab、三个输入的组合确认误触、设置Tab键盘、Debug过期错误、原生保存目录错误和旧回归合同。见[全部问题](findings.md)。

|验证层|本轮证据与边界|
|---|---|
|Chrome154真实资源/模拟桌面桥接|100+27项观察；88符合、39差异，差异不能直接等于39个bug；按根因合并并剔除工具模拟文案误判|
|真实WebView2/Edge154|主窗8项、两次应用重建历史13项、Debug完整保存/异常捕获；同一进程源码运行，非EXE/付费模型|
|真实Tk|首批21项与五页记录，随后93项补验全部通过：18项编辑/短输入、47项字段保存/非法值、25项剩余入口/滚动/清理、3项玻璃按钮生命周期。回调/OS返回模拟与实际控件操作已分开|
|定向/相邻pytest|三批定向/相邻检查合并430个不同节点；最新416通过、14旧UI合同失败。一次批量Skill多工作等待超时隔离复验通过，保留前证据|
|视觉与性能|已目视首批28张Web和12张Tk截图联系表；8次真实展开动画有中间帧、最大变化间隔27.8ms；长Unicode123次渐进更新。另8项Chrome生命周期与100次布局采样通过，中位0.9ms/p95=1.6ms/最大2.2ms；不能推出180Hz/长期堆内存达标|

检查共{len(a['checks'])}条：{dict(stats)}。`blocked`仅表示真实候选/读屏/跨DPI/EXE/服务与原生OS自动化缺口；本地`not_checked`已归零；静态叶子无独立生命周期明确`not_applicable`，不冒充性能通过。全部实例方案：{dict(plans)}；investigate逐实例说明真实平台缺口并链接TASK-014；本地补验记录见TASK-015。**发现与全实例方案覆盖完整；本地可执行补验已收尾，真实系统/EXE/服务运行覆盖仍未闭合。**

发现渠道已核对：HTML虚拟页、所有Web条件分支与31项偏好/连接字段、Tk构造清单、真实运行导航、现行产品交接。初始461实例之外，补登记动态Canvas/ReplyButton及遗漏的取消入口；装饰包装归父组件检查，重复数据按不同职责/来源/状态等价类登记。无限记录与输入不宣称穷举。

保留现有已验证行为：逐题批量回答、充分就停的访谈、显式确认、选用禁重复与来源累计、结果仍在Web、跳过不入最终提示、历史草稿和版本隔离、系统默认字体与局部100%、Windows当前用户DPAPI、诊断内存完整归档与手动保存。没有证据支持再次换渲染引擎或删除复刻动画。

13项缺陷修复任务均未实施；TASK-015本地补验已verified，TASK-014平台补证仍blocked。Debug覆盖与异常cause要求随每项变更同步。DPAPI保护依赖Windows当前用户，不能称抵御同用户恶意进程的绝对安全。

入口索引：

- [机器台账](audit.json) / [机械覆盖结果](coverage.md)
- [13项问题详单](findings.md) / [整改任务与依赖](refactor-plan.md)
- [真实验收交接与全部缺口](verification-handoff.md)
- 34份页面报告见下表；68份组件蓝图及全部实例方案从对应页面进入。

|页面|入口报告|
|---|---|
'''
for p in a['pages']:summary+=f'|{p["id"]} {p["title"]}|[全部实例](pages/{p["id"]}.md)|\n'
summary+='\n依据：当前用户/交接合同、WAI-ARIA APG dialog/tabs/menu建议、MDN isComposing与本轮实际DOM；未声明WCAG等级合规。参见[Skill一手来源](../../../../../.codex/skills/review-frontend-production/references/source-register.md)仅作方法来源，该机器相对链接不作为项目可移植资料；正式依据使用https://www.w3.org/WAI/ARIA/apg/patterns/ 与 https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/isComposing 。\n'
summary=summary.replace('[Skill一手来源](../../../../../.codex/skills/review-frontend-production/references/source-register.md)仅作方法来源，该机器相对链接不作为项目可移植资料；正式依据使用','正式依据使用')
write('review.md',summary)
print('Ledger written:',len(a['pages']),'pages',len(a['definitions']),'definitions',len(a['instances']),'instances',len(a['checks']),'checks',len(a['findings']),'findings')
print('Checks:',dict(stats),'Plans:',dict(plans))
