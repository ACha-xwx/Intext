"""Bounded real M2 replay; credentials stay in process memory only."""

from __future__ import annotations

import argparse
from copy import deepcopy
import getpass
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from promptsmith.api import ApiConfig, ChatCompletionsClient, structured_request_parameters
from promptsmith.m1 import M1Assets
from promptsmith.session import SessionState
from promptsmith.storage import save_session
from promptsmith.workflow import M2CallFailure, Phase12Workflow


def replay_session(payload: dict) -> SessionState:
    session = SessionState.new()
    session.task_id = payload["task_id"]
    session.task_text = payload["task"]["text"]
    session.selected_category = payload["category"]["primary"]
    session.sources = deepcopy(payload["relevant_materials"])
    session.requirements = [dict(deepcopy(row), confirmation="confirmed") for row in payload["requirements"]]
    session.requirement_version = payload["source_requirements_version"]
    session.confirmed_requirements_version = payload["confirmed_requirements_version"]
    session.analysis_basis_version = session.requirement_version
    session.gaps = [dict(deepcopy(row), gap_id=row["unresolved_id"]) for row in payload["unresolved_items"]]
    session.plan.update(
        plan_id=payload["plan_context"]["current_plan_id"],
        plan_version=payload["plan_context"]["current_plan_version"],
    )
    return session


def writing_session() -> SessionState:
    session = SessionState.new()
    session.set_task("为摄影社写一则发在新生微信群的招新通知，500字以内；活动时间和地点还没确定，不要编造，也不要添加收费或器材要求。")
    session.selected_category = "writing"
    source_id = session.sources[0]["source_id"]
    specs = [
        ("deliverable", "为摄影社写一则发在新生微信群的招新通知", "为摄影社写一则发在新生微信群的招新通知"),
        ("constraints", "通知不超过500字", "500字以内"),
        ("constraints", "不得编造时间地点，不得添加收费或器材要求", "活动时间和地点还没确定，不要编造，也不要添加收费或器材要求"),
    ]
    session.requirements = [
        {"item_id": f"r{index}", "field": field, "text": text, "kind": "user_decision",
         "strength": "hard", "scope": "招新通知", "source_refs": [{"source_id": source_id, "quote": quote}],
         "depends_on": [], "confirmation": "confirmed"}
        for index, (field, text, quote) in enumerate(specs, 1)
    ]
    session.gaps = [{"gap_id": "g-time-place", "field": "context", "scope": "招新活动",
                     "description": "活动时间与地点尚未确定", "importance": "can_defer", "can_defer": True,
                     "source_refs": [{"source_id": source_id, "quote": "活动时间和地点还没确定"}], "depends_on": []}]
    session.analysis_basis_version = session.requirement_version
    session.confirm_requirements()
    return session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_input", type=Path)
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument(
        "--cases", nargs="+",
        choices=["original_jgs_1", "original_jgs_2", "writing_unknown_time_place"],
        default=["original_jgs_1", "original_jgs_2", "writing_unknown_time_place"],
    )
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    api_key = os.environ.get("DEEPSEEK_API_KEY") or getpass.getpass("DeepSeek API key (not saved): ")
    config = ApiConfig("https://api.deepseek.com", "deepseek-flash", api_key)
    client = ChatCompletionsClient(config)
    original = json.loads(args.original_input.read_text(encoding="utf-8"))
    cases = [(name, None if name == "writing_unknown_time_place" else original) for name in args.cases]
    report = {"verification_kind": "real_deepseek_source_m2_replay", "max_calls": len(cases),
              "protocol": config.protocol, "model": config.model, "parameters": structured_request_parameters(config),
              "original_input": str(args.original_input.resolve()), "results": []}
    for name, snapshot in cases:
        session = replay_session(snapshot) if snapshot else writing_session()
        workflow = Phase12Workflow(session, M1Assets.load(), evidence / "calls")
        request_id = f"m2-real-{name}-{uuid4().hex}"
        if snapshot:
            session.begin_m2_request(request_id)
            payload = dict(deepcopy(snapshot), request_id=request_id)
        else:
            payload = workflow.prepare_m2(request_id, current_date="2026-10-01")
        row = {"case": name, "request_id": request_id}
        try:
            outcome = workflow.invoke_m2(
                payload, client, protocol=config.protocol, configured_model=config.model,
                request_parameters={"base_url": config.base_url, "model": config.model,
                                    "timeout_seconds": config.timeout_seconds, **structured_request_parameters(config)},
            )
            workflow.apply_m2(payload, outcome)
        except M2CallFailure as exc:
            row.update(success=False, failure_kind=exc.kind, message=str(exc), evidence_dir=str(exc.evidence_dir))
        else:
            plan = session.plan["content"]
            row.update(success=True, finish_reason=outcome.api_result.finish_reason,
                       latency_ms=outcome.api_result.latency_ms, usage=outcome.api_result.usage,
                       response_chars=len(outcome.raw_response), evidence_dir=str(outcome.evidence_dir),
                       requirement_count=len(plan["requirement_coverage"]),
                       unresolved_count=len(plan["unresolved_items"]), step_count=len(plan["steps"]),
                       plan_status=session.plan["status"])
            save_session(session, evidence / f"{name}.session.json")
        report["results"].append(row)
        (evidence / "verification_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0 if all(row["success"] for row in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
