"""Run a source or single-file EXE UI chain against a local HTTP model stub."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _m1_response(payload: dict[str, Any]) -> dict[str, Any]:
    source_id = payload["current_source_id"]
    task = next(row["text"] for row in payload["sources"] if row["source_id"] == source_id)
    specs = [
        ("goal", "为摄影社撰写面向新生微信群的招新通知。", "为摄影社写一则发在新生微信群的招新通知"),
        ("deliverable", "一则不超过 500 字的招新通知。", "500 字以内"),
        ("constraints", "不添加未提供的负责人、收费或器材要求。", "不要添加未提供的负责人、收费或器材要求"),
    ]
    proposals = []
    for index, (field, value, quote) in enumerate(specs, 1):
        if quote not in task:
            raise ValueError(f"固定任务缺少来源片段：{quote}")
        proposals.append({
            "proposal_id": f"p{index}", "operation": "new", "target_item_id": None,
            "field": field, "text": value, "kind": "user_decision",
            "strength": "hard" if field == "constraints" else "preference",
            "scope": "摄影社招新通知", "source_refs": [{"source_id": source_id, "quote": quote}],
            "depends_on": [], "reason": "固定离线桩中的用户原话提取。",
        })
    return {
        "schema_version": payload["schema_version"], "request_id": payload["request_id"],
        "task_id": payload["task_id"], "base_version": payload["base_version"],
        "status": "ok", "error": None,
        "category": {"primary": "writing", "secondary": [], "reason": "交付物是文字通知。"},
        "proposals": proposals, "conflicts": [], "review_item_ids": [],
        "gap_updates": [], "question_reopens": [], "gaps": [], "questions": [],
        "readiness": {"goal_identified": True, "deliverable_identified": True,
                      "blocking_gap_ids": [], "reason": "固定任务信息足以进入需求复核。"},
        "next_action": "review_requirements", "assistant_text": "请复核提取的要求。",
    }


def _m2_response(payload: dict[str, Any]) -> dict[str, Any]:
    ids = [row["item_id"] for row in payload["requirements"]]
    coverage = [{"requirement_id": item_id, "summary": "纳入通知写作要求。",
                 "step_ids": ["s1"], "deliverable_ids": ["d1"], "criterion_ids": ["c1"]}
                for item_id in ids]
    unresolved = [{"unresolved_id": f"u{index}", "source_gap_id": row["unresolved_id"],
                   "description": row["description"], "impact": "发布前核对。",
                   "continuable_work": "先完成通知草稿。", "confirm_by": "发布前"}
                  for index, row in enumerate(payload["unresolved_items"], 1)]
    plan = {
        "goal": {"summary": "完成摄影社招新通知。", "audience": "新生微信群成员",
                 "scope": "500 字以内，保留已知活动与报名事实，不补造负责人、费用和器材要求。"},
        "requirement_coverage": coverage,
        "steps": [{"step_id": "s1", "order": 1, "title": "撰写并核对招新通知",
                   "purpose": "提供可供人工复核的通知文案。", "inputs": ["已确认需求"],
                   "actions": ["整理活动事实", "撰写通知", "检查字数及禁止补充的内容"],
                   "outputs": ["招新通知草稿"], "completion_criteria": ["字数不超过 500 字且关键事实准确"],
                   "depends_on_step_ids": [], "requirement_ids": ids}],
        "deliverables": [{"deliverable_id": "d1", "name": "摄影社招新通知草稿",
                          "description": "面向新生微信群的短通知。", "step_ids": ["s1"],
                          "requirement_ids": ids}],
        "completion_criteria": [{"criterion_id": "c1", "text": "通知不超过 500 字且不编造负责人、收费或器材要求。",
                                 "requirement_ids": ids}],
        "unresolved_items": unresolved, "suggestions": [],
        "key_work": [{"key_work_id": "k1", "title": "通知撰写与事实核对", "step_ids": ["s1"],
                      "goal": "得到准确的通知草稿。", "inputs": ["已确认需求"],
                      "outputs": ["招新通知草稿"], "requirement_ids": ids,
                      "depends_on_key_work_ids": [], "checkpoints": ["字数达标", "无虚构要求"]}],
    }
    return {"schema_version": "m2.v0.1", "request_id": payload["request_id"],
            "task_id": payload["task_id"],
            "source_requirements_version": payload["source_requirements_version"],
            "status": "ok", "error": None, "plan": plan}


def _m1_truncation_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Fixed offline data for the same two-answer recovery used in UI tests."""
    result = {
        "schema_version": payload["schema_version"], "request_id": payload["request_id"],
        "task_id": payload["task_id"], "base_version": payload["base_version"],
        "status": "ok", "error": None,
        "category": {"primary": "learning", "secondary": [], "reason": "学生学习讲解。"},
        "proposals": [], "conflicts": [], "review_item_ids": [], "gap_updates": [],
        "question_reopens": [], "gaps": [], "questions": [],
        "readiness": {"goal_identified": True, "deliverable_identified": True,
                      "blocking_gap_ids": [], "reason": "可进入需求复核。"},
        "next_action": "review_requirements", "assistant_text": "请核对当前需求。",
    }
    history = payload["state"]["question_history"]
    if not history:
        result["proposals"] = [{
            "proposal_id": "p-explain", "operation": "new", "target_item_id": None,
            "field": "deliverable", "text": "讲解JGS", "kind": "user_decision", "strength": "hard",
            "scope": "当前讲解", "source_refs": [{"source_id": payload["current_source_id"], "quote": "讲解JGS"}],
            "depends_on": [], "reason": "用户提出讲解任务。",
        }]
        result["gaps"] = [{
            "gap_id": f"g{index}", "field": field, "scope": "当前讲解", "description": description,
            "importance": "blocking_direction", "origin": "missing", "source_refs": [], "depends_on": [],
        } for index, field, description in ((1, "goal", "JGS所指领域未知"), (2, "audience", "讲解对象未知"))]
        result["questions"] = [{
            "question_id": f"q{index}", "gap_id": f"g{index}", "field": field, "scope": "当前讲解",
            "text": text, "options": [], "reason": "明确讲解方向。", "depends_on": [],
        } for index, field, text in ((1, "goal", "JGS是哪个领域的？"), (2, "audience", "讲解给谁学习？"))]
        result["readiness"]["blocking_gap_ids"] = ["g1", "g2"]
        result["next_action"] = "ask"
    else:
        result["gap_updates"] = [{
            "update_id": f"update-{row['answer_id']}", "target_gap_id": row["gap_id"],
            "answer_id": row["answer_id"], "action": "resolved",
            "source_ref": {"source_id": row["answer_source_id"], "quote": row["answer_text"]},
            "remaining_description": None, "reason": "用户已回答此项。",
        } for row in history]
    return result


def verify_program(
    command: list[str], *, evidence_dir: str | Path, timeout_seconds: int = 60,
    isolated_exe: bool = False, scenario: str = "default",
) -> dict[str, Any]:
    if scenario not in {"default", "m1_truncation"}:
        raise ValueError(f"Unknown offline release scenario: {scenario}")
    evidence = Path(evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    requests: list[str] = []
    request_details: list[dict[str, Any]] = []
    handler_errors: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length))
                payload = json.loads(body["messages"][-1]["content"])
                purpose = "m1" if payload.get("schema_version") == "m1.v0.2" else "m2"
                requests.append(purpose)
                call_number = len(requests)
                if scenario == "m1_truncation":
                    if purpose != "m1" or call_number > 3:
                        raise AssertionError("截断场景只允许三个显式 M1 请求")
                    result = _m1_truncation_response(payload)
                else:
                    result = _m1_response(payload) if purpose == "m1" else _m2_response(payload)
                if scenario == "m1_truncation" and call_number == 2:
                    response_content = '{"schema_version":"m1.v0.2","proposals":['
                    finish_reason = "length"
                    usage = {"prompt_tokens": 1500, "completion_tokens": 8192, "total_tokens": 9692}
                else:
                    response_content = json.dumps(result, ensure_ascii=False)
                    finish_reason = "stop"
                    usage = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
                envelope = {"id": f"stub-{purpose}-{call_number}", "model": "release-stub",
                            "choices": [{"finish_reason": finish_reason, "message": {"content": response_content}}],
                            "usage": usage}
                if scenario == "m1_truncation":
                    transport = evidence / "transport"
                    transport.mkdir(exist_ok=True)
                    (transport / f"request_{call_number}.body.json").write_text(
                        json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    (transport / f"response_{call_number}.envelope.json").write_text(
                        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    system_prompt = body["messages"][0]["content"]
                    request_details.append({
                        "request_id": payload["request_id"], "purpose": purpose,
                        "max_tokens": body.get("max_tokens"), "finish_reason": finish_reason,
                        "raw_content_chars": len(response_content),
                        "pending_answer_count": sum(row.get("assessment_status") == "pending"
                                                    for row in payload["state"]["question_history"]),
                        "incremental_prompt": "本提示用于增量响应" in system_prompt,
                        "compact_retry_instruction": "【精简重试】" in system_prompt,
                    })
                raw = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
            except Exception as exc:
                handler_errors.append(f"{type(exc).__name__}: {exc}")
                raw = json.dumps({"error": {"message": "Offline verification fixture failed"}}).encode("utf-8")
                self.send_response(500)
            else:
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    run_command = list(command)
    isolated_dir = None
    exe_sha256 = None
    try:
        if isolated_exe:
            isolated_dir = Path(tempfile.mkdtemp(prefix="promptsmith-exe-chain-"))
            copied_exe = isolated_dir / Path(command[0]).name
            shutil.copy2(command[0], copied_exe)
            run_command[0] = str(copied_exe)
            digest = hashlib.sha256()
            with copied_exe.open("rb") as executable:
                for chunk in iter(lambda: executable.read(1024 * 1024), b""):
                    digest.update(chunk)
            exe_sha256 = digest.hexdigest()
        environment = os.environ.copy()
        environment["PROMPTSMITH_RELEASE_STUB_URL"] = f"http://127.0.0.1:{server.server_port}"
        environment["PROMPTSMITH_API_BASE_URL"] = environment["PROMPTSMITH_RELEASE_STUB_URL"]
        environment["PROMPTSMITH_MODEL"] = "release-stub"
        environment["PROMPTSMITH_RELEASE_SCENARIO"] = scenario
        completed = subprocess.run(
            [*run_command, "--verify-release-chain", str(evidence)],
            cwd=isolated_dir or evidence,
            env=environment, capture_output=True, text=True, timeout=timeout_seconds,
        )
        chain_path = evidence / "chain_result.json"
        chain = json.loads(chain_path.read_text(encoding="utf-8")) if chain_path.exists() else {}
        result = {"exit_code": completed.returncode, "http_purposes": requests,
                  "isolated_exe_dir": str(isolated_dir) if isolated_dir else None,
                  "isolated_dir_contents": sorted(path.name for path in isolated_dir.iterdir()) if isolated_dir else None,
                  "exe_sha256": exe_sha256,
                  "stderr_tail": completed.stderr[-2000:], **chain}
        if scenario == "m1_truncation":
            result.update({"http_request_count": len(requests), "http_request_details": request_details,
                           "http_handler_errors": handler_errors})
            transport_valid = (
                requests == ["m1", "m1", "m1"] and not handler_errors
                and [row["finish_reason"] for row in request_details] == ["stop", "length", "stop"]
                and [row["pending_answer_count"] for row in request_details] == [0, 2, 2]
                and [row["incremental_prompt"] for row in request_details] == [False, True, True]
                and [row["compact_retry_instruction"] for row in request_details] == [False, False, True]
                and all(row["max_tokens"] == 8192 for row in request_details)
            )
            result["http_transport_check_passed"] = transport_valid
            if not transport_valid:
                result["success"] = False
                result["error"] = "Offline HTTP request sequence or incremental prompt check failed"
        (evidence / "verification_summary.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify the standalone PromptSmith EXE with a local HTTP stub")
    parser.add_argument("exe", type=Path)
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--scenario", choices=["default", "m1_truncation"], default="default")
    args = parser.parse_args()
    result = verify_program([str(args.exe.resolve())], evidence_dir=args.evidence_dir,
                            isolated_exe=True, scenario=args.scenario)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["exit_code"] == 0 and result.get("success") else 1)
