from __future__ import annotations

import pytest

from promptsmith.finalization import build_final_draft
from promptsmith.session import SessionState


CASES = [
    {
        "category": "writing",
        "task": "为城市公共图书馆撰写一篇面向家长的阅读推广文章",
        "goal": "介绍亲子共读如何培养儿童阅读兴趣",
        "deliverable": "一篇约 1200 字中文文章，包含三条可执行建议",
        "step": "整理亲子共读的核心观点",
        "output": "文章初稿",
    },
    {
        "category": "presentation",
        "task": "为社区节能活动制作阶段汇报",
        "goal": "说明活动成果并争取下一季度资源",
        "deliverable": "面向街道工作人员的八页 PPT 大纲",
        "step": "梳理活动数据和汇报主线",
        "output": "逐页内容大纲",
    },
    {
        "category": "learning",
        "task": "为零基础成人制定西班牙语入门学习计划",
        "goal": "帮助学习者掌握基础问候和日常表达",
        "deliverable": "十四天学习计划，每天安排二十分钟练习",
        "step": "按学习难度安排每日练习",
        "output": "逐日学习安排",
    },
    {
        "category": "planning_research",
        "task": "调研校园食堂减少一次性餐具的可行方案",
        "goal": "比较替代方案并支持校方选择试点措施",
        "deliverable": "包含证据来源、成本因素和建议的调研简报",
        "step": "定义比较维度并收集现有材料",
        "output": "方案比较表和简报",
    },
    {
        "category": "data_analysis",
        "task": "分析一学期图书馆到馆人数数据并提出排班建议",
        "goal": "识别到馆高峰时段及其变化",
        "deliverable": "一份含关键图表、发现和排班建议的分析报告",
        "step": "核对数据口径并按时段汇总人数",
        "output": "高峰时段图表和分析报告",
    },
    {
        "category": "coding",
        "task": "修复 Python 命令行工具读取 UTF-8 CSV 空行时崩溃的问题",
        "goal": "使工具稳定处理含空行的 CSV 输入",
        "deliverable": "最小代码修改及覆盖空行情况的回归测试",
        "step": "复现 CSV 空行输入导致的异常",
        "output": "修复补丁和回归测试",
    },
    {
        "category": "general",
        "task": "为社区读书角设计一个月的活动安排",
        "goal": "提高居民参与度并形成稳定的每周活动",
        "deliverable": "包含每周主题、活动流程和物资清单的月度安排",
        "step": "根据参与对象规划每周主题",
        "output": "四周活动安排",
    },
]

CODING_MARKERS = ("代码", "编程", "Python", "运行时", "现有代码")
CODING_ONLY_FIELDS = {"use_context", "features", "runtime", "existing_code", "io_behavior"}


def _confirmed_session(case: dict[str, str]) -> SessionState:
    session = SessionState.new()
    session.set_task(case["task"])
    session.selected_category = case["category"]
    session.requirements = [
        {
            "item_id": "r-goal",
            "field": "goal",
            "text": case["goal"],
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "pending",
        },
        {
            "item_id": "r-deliverable",
            "field": "deliverable",
            "text": case["deliverable"],
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "pending",
        },
    ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    session.plan = {
        "plan_id": f"plan-{case['category']}",
        "plan_version": 1,
        "status": "confirmed",
        "content": {
            "goal": {
                "summary": case["goal"],
                "audience": "由任务输入指定的对象",
                "scope": "仅限当前任务描述的范围",
            },
            "steps": [
                {
                    "step_id": "s1",
                    "order": 1,
                    "title": case["step"],
                    "purpose": case["goal"],
                    "inputs": ["用户提供的任务背景和材料"],
                    "actions": [case["step"]],
                    "outputs": [case["output"]],
                    "completion_criteria": [case["deliverable"]],
                    "depends_on_step_ids": [],
                    "requirement_ids": ["r-goal", "r-deliverable"],
                }
            ],
            "deliverables": [
                {
                    "deliverable_id": "d1",
                    "name": case["output"],
                    "description": case["deliverable"],
                    "step_ids": ["s1"],
                    "requirement_ids": ["r-goal", "r-deliverable"],
                }
            ],
            "completion_criteria": [
                {"criterion_id": "c1", "text": case["deliverable"], "requirement_ids": ["r-deliverable"]}
            ],
            "key_work": [
                {
                    "key_work_id": "k1",
                    "title": case["step"],
                    "step_ids": ["s1"],
                    "goal": case["goal"],
                    "inputs": ["用户提供的任务背景和材料"],
                    "outputs": [case["output"]],
                    "requirement_ids": ["r-goal", "r-deliverable"],
                    "depends_on_key_work_ids": [],
                    "checkpoints": [case["deliverable"]],
                }
            ],
            "unresolved_items": [],
            "suggestions": [],
        },
        "original_content": None,
        "source_requirements_version": session.requirement_version,
        "confirmed_plan_version": 1,
        "pending_key_work_review_ids": [],
        "reviewed_key_work_ids": ["k1"],
        "source_snapshot": {"requirements": session.requirements, "unresolved_items": []},
    }
    return session


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["category"])
def test_no_skill_final_assembly_preserves_each_task_category(case: dict[str, str]) -> None:
    session = _confirmed_session(case)

    assert session.skill_state["bindings"] == []
    draft = build_final_draft(session)

    baseline = draft["content"]["baseline"]
    assert draft["status"] == "draft"
    assert baseline["task"] == case["task"]
    assert baseline["category"] == case["category"]
    assert baseline["requirements"] == session.requirements
    assert draft["content"]["skill_contributions"] == []
    assert "本方案未采用外部 Agent Skill" in draft["canonical_body"]
    for expected in (case["task"], case["goal"], case["deliverable"], case["step"], case["output"]):
        assert expected in draft["canonical_body"]
    assert session.api_runs == []

    if case["category"] != "coding":
        assert not (CODING_ONLY_FIELDS & {row["field"] for row in baseline["requirements"]})
        assert not any(marker in draft["canonical_body"] for marker in CODING_MARKERS)
