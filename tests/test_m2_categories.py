from __future__ import annotations

import pytest

from promptsmith.categories import CATEGORY_CONFIG
from promptsmith.m2 import build_m2_input
from promptsmith.session import SessionState


@pytest.mark.parametrize(
    ("category", "specific_field"),
    [
        ("writing", "style"),
        ("presentation", "duration"),
        ("learning", "baseline"),
        ("planning_research", "evidence_policy"),
        ("data_analysis", "metric_definition"),
        ("coding", "runtime"),
        ("general", "goal"),
    ],
)
def test_all_entry_categories_use_the_same_m2_contract(category: str, specific_field: str) -> None:
    session = SessionState.new()
    session.set_task("完成一个可核对的任务交付。")
    session.selected_category = category
    session.requirements = [
        {
            "item_id": "r1",
            "field": "deliverable",
            "text": "一个可核对的任务交付",
            "kind": "user_decision",
            "strength": "hard",
            "scope": "整体任务",
            "source_refs": [],
            "depends_on": [],
            "confirmation": "confirmed",
        }
    ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()

    payload = build_m2_input(session, f"m2-{category}", current_date="2026-09-23")

    assert payload["category"]["primary"] == category
    assert specific_field in payload["category"]["applicable_fields"]
    assert payload["category"]["config_version"] == CATEGORY_CONFIG["version"]
