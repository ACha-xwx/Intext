from __future__ import annotations

import json
import platform
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promptsmith.m2 import M2Assets, apply_m2_response, build_m2_input, parse_m2_response
from promptsmith.session import SessionState
from promptsmith.storage import load_session, save_session


DESIGN = ROOT / "resources" / "prompts"


def make_session(category: str) -> SessionState:
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
    return session


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_m2_release.py OUTPUT_DIR")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    assets = M2Assets.load(DESIGN)

    fixture_input = json.loads(
        (DESIGN / "examples_m2" / "01_报名网站.input.json").read_text(encoding="utf-8")
    )
    fixture_output = json.loads(
        (DESIGN / "examples_m2" / "01_报名网站.output.fixture.json").read_text(encoding="utf-8")
    )
    fixture_output.pop("evidence_type", None)
    parsed = parse_m2_response(
        json.dumps(fixture_output, ensure_ascii=False), fixture_input, assets.output_schema
    )

    categories = []
    for category in (
        "writing",
        "presentation",
        "learning",
        "planning_research",
        "data_analysis",
        "coding",
        "general",
    ):
        session = make_session(category)
        payload = build_m2_input(session, f"verify-{category}", current_date="2026-09-23")
        categories.append(
            {
                "category": category,
                "primary": payload["category"]["primary"],
                "applicable_fields": payload["category"]["applicable_fields"],
                "result": "input_contract_passed",
            }
        )

    session = SessionState.new()
    session.set_task(fixture_input["task"]["text"])
    session.selected_category = fixture_input["category"]["primary"]
    session.requirements = [
        {**deepcopy(row), "confirmation": "confirmed"} for row in fixture_input["requirements"]
    ]
    session.gaps = [
        {
            "gap_id": row["unresolved_id"],
            "field": row["field"],
            "scope": row["scope"],
            "description": row["description"],
            "importance": row["importance"],
            "origin": "user_unsure",
            "source_refs": deepcopy(row["source_refs"]),
            "depends_on": deepcopy(row["depends_on"]),
        }
        for row in fixture_input["unresolved_items"]
    ]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    payload = build_m2_input(session, "verify-roundtrip", current_date="2026-09-23")
    result = deepcopy(fixture_output)
    result["request_id"] = payload["request_id"]
    result["task_id"] = payload["task_id"]
    result["source_requirements_version"] = payload["source_requirements_version"]
    parsed_roundtrip = parse_m2_response(
        json.dumps(result, ensure_ascii=False), payload, assets.output_schema
    )
    apply_m2_response(session, payload, parsed_roundtrip)
    session.edit_plan_goal("完成一个更清楚的课堂演示报名网站。")
    session.mark_key_work_reviewed(session.plan["pending_key_work_review_ids"])
    session.confirm_plan()
    session_path = save_session(session, output / "m2_confirmed_session.json")
    reopened = load_session(session_path)

    summary = {
        "evidence_type": "offline_program_verification",
        "date": "2026-09-23",
        "python": sys.version,
        "platform": platform.platform(),
        "prompt_version": assets.prompt_version,
        "contract_version": assets.contract_version,
        "fixture_schema_and_semantic_check": parsed["status"],
        "categories": categories,
        "round_trip": {
            "plan_id": reopened.plan["plan_id"],
            "plan_version": reopened.plan["plan_version"],
            "status": reopened.plan["status"],
            "confirmed_plan_version": reopened.plan["confirmed_plan_version"],
            "pending_key_work_review_ids": reopened.plan["pending_key_work_review_ids"],
        },
        "real_model_call": False,
        "notes": [
            "人工 fixture 未发送给模型。",
            "本结果验证契约、程序状态和持久化，不代表真实模型内容质量。",
        ],
    }
    (output / "observed_m2_offline.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
