from __future__ import annotations

from promptsmith.guided_flow import GuidedFlowMixin


def test_guided_question_formatter_keeps_question_options_and_reason_in_one_paragraph():
    text = GuidedFlowMixin._format_guided_question({
            "text": "在学分部积分法之前，你已经学过下面哪些内容？",
            "options": ["定积分", "分部积分公式", "都没有"],
            "reason": "这有助于确定讲解起点。",
    })

    assert text == (
        "在学分部积分法之前，你已经学过下面哪些内容？"
        "可选内容包括：定积分、分部积分公式、都没有。"
        "这有助于确定讲解起点。"
    )
    assert "\n" not in text


def test_guided_question_formatter_supports_multiple_questions_with_complete_bodies():
    text = GuidedFlowMixin._format_guided_questions([
            {"text": "问题一", "options": ["A", "B"], "reason": "原因一"},
            {"text": "问题二", "options": [], "reason": "原因二"},
    ])

    assert "1. 问题一" in text
    assert "问题一可选内容包括：A、B。原因一" in text
    assert "确认原因" not in text
    assert "2. 问题二" in text
    assert "问题二原因二" in text


def test_guided_context_appends_draft_explanation_to_question_body_inline():
    text = GuidedFlowMixin._format_guided_context(
        "在学分部积分法之前，你已经学过哪些内容？可选内容包括：定积分、函数求导。",
        "这有助于确定讲解起点。",
    )

    assert text == (
        "在学分部积分法之前，你已经学过哪些内容？"
        "可选内容包括：定积分、函数求导。"
        "这有助于确定讲解起点。"
    )
    assert "\n" not in text
    assert "补充说明" not in text


def test_guided_interpretations_are_rendered_as_part_of_the_question_body():
    text = GuidedFlowMixin._format_guided_interpretations([
        {
            "text": "比较 Jacobi 与 Gauss-Seidel 两种迭代方法",
            "interpretation_for": {
                "reason": "结合你提到的数值分析，这是一种可能理解。",
            },
        }
    ])

    assert text == (
        "AI 可能的理解：比较 Jacobi 与 Gauss-Seidel 两种迭代方法。"
        "结合你提到的数值分析，这是一种可能理解。"
    )
    assert "下方解释" not in text
