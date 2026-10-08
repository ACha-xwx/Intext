from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .categories import CATEGORY_CONFIG
from .paths import m1_asset_dir
from .session import SessionState


class M1ValidationError(ValueError):
    pass


class M1JsonError(M1ValidationError):
    """The provider returned content that is not a strict JSON object."""


M1_INCREMENTAL_PROMPT_VERSION = "M1_incremental_v0.15"
M1_SYSTEM_PROMPT_VERSION = "M1_system_v0.22"


def m1_request_mode(*, has_pending_answers: bool, compact_retry: bool = False) -> str:
    """Return the application-controlled M1 response mode.

    The input contract remains m1.v0.2.  The mode only changes the instruction
    wrapper sent around that contract, so old fixtures and saved sessions remain
    compatible.
    """
    if compact_retry:
        return "compact_retry"
    if has_pending_answers:
        return "incremental"
    return "full"


_COMPACT_RETRY_INSTRUCTION = """
【精简重试】
上次输出未完整结束。仅依据原输入评估 pending 回答，不加入非必要建议或追问；没有 pending 回答时仅处理 current_source_id 的本次任务。
优先输出必要 gap_updates 和有证据的需求变化，其他无变化集合使用[]。不重述旧需求，不要求用户重新回答，不处理或引用失败输出。
assistant_text 至多一句；reason、description、quote 使用最短但完整、准确的内容。语法、必需字段、来源、未决项保护和确认边界不变。
""".strip()


def m1_system_prompt(system_prompt: str, *, mode: str) -> str:
    if mode == "full":
        return system_prompt
    if mode not in {"incremental", "compact_retry"}:
        raise ValueError(f"不支持的M1请求模式：{mode}")
    root = m1_asset_dir()
    incremental = (root / "M1_incremental_v0.11.txt").read_text(encoding="utf-8-sig")
    addendum = root / f"{M1_INCREMENTAL_PROMPT_VERSION}.txt"
    if addendum.exists():
        incremental = f"{incremental}\n\n{addendum.read_text(encoding='utf-8-sig')}"
    return f"{incremental}\n\n{_COMPACT_RETRY_INSTRUCTION}" if mode == "compact_retry" else incremental


@dataclass(frozen=True)
class M1Assets:
    system_prompt: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    prompt_version: str = M1_SYSTEM_PROMPT_VERSION
    contract_version: str = "m1.v0.2"

    @classmethod
    def load(cls, directory: str | Path | None = None, *, legacy: bool = False) -> "M1Assets":
        root = Path(directory) if directory else m1_asset_dir()
        if legacy:
            return cls(
                system_prompt=(root / "M1_system_v0.3.txt").read_text(encoding="utf-8-sig"),
                input_schema=json.loads((root / "M1_input.schema.json").read_text(encoding="utf-8-sig")),
                output_schema=json.loads((root / "M1_output.schema.json").read_text(encoding="utf-8-sig")),
                prompt_version="M1_system_v0.3",
                contract_version="m1.v0.1",
            )
        system_prompt = (root / "M1_system_v0.18.txt").read_text(encoding="utf-8-sig")
        addendum = root / f"{M1_SYSTEM_PROMPT_VERSION}.txt"
        if addendum.exists():
            system_prompt = f"{system_prompt}\n\n{addendum.read_text(encoding='utf-8-sig')}"
        return cls(
            system_prompt=system_prompt,
            input_schema=json.loads((root / "M1_input_v0.4.schema.json").read_text(encoding="utf-8-sig")),
            output_schema=json.loads((root / "M1_output_v0.3.schema.json").read_text(encoding="utf-8-sig")),
        )


def _open_conflict_for_input(conflict: dict[str, Any]) -> dict[str, Any]:
    item_ids = conflict.get("item_ids")
    if item_ids is None:
        item_ids = conflict.get("existing_item_ids", [])
    result = {
        "conflict_id": conflict["conflict_id"],
        "item_ids": list(item_ids),
        "description": conflict["description"],
    }
    if conflict.get("proposal_ids"):
        result["proposal_ids"] = list(conflict["proposal_ids"])
    return result


def build_m1_input(
    session: SessionState,
    request_id: str,
    *,
    current_date: str | None = None,
) -> dict[str, Any]:
    session._validate_active_references()
    request = session.begin_request(request_id)
    source_count = len(session.sources)
    question_history = []
    for row in session.question_history:
        question_history.append(
            {
                "question_id": row["question_id"],
                "field": row["field"],
                "scope": row["scope"],
                "text": row["text"],
                "disposition": row["disposition"],
                "gap_id": row.get("gap_id"),
                "answer_id": row.get("answer_id"),
                "answer_source_id": row.get("answer_source_id"),
                "answer_text": row.get("answer_text", ""),
                "state_version": row.get("state_version", 0),
                # Older sessions may not have this field.  Do not fabricate
                # an earlier source count, or a skipped question could look as
                # if it had received new context and be asked again forever.
                "recorded_source_count": (
                    row["recorded_source_count"]
                    if row.get("recorded_source_count") is not None
                    else source_count
                ),
                "assessment_status": row.get("assessment_status", "legacy_unverified"),
            }
        )
        for key in ("context_gap_ids", "assessed_gap_ids"):
            if key in row:
                question_history[-1][key] = deepcopy(row[key])
    reopen_history = [
        {
            "reopen_id": row["reopen_id"],
            "target_gap_id": row["target_gap_id"],
            "source_ref": deepcopy(row["source_ref"]),
            "reason": row["reason"],
        }
        for row in session.question_reopen_history
    ]
    assets = M1Assets.load()
    state_properties = assets.input_schema["properties"]["state"]["properties"]

    def semantic_rows(name: str) -> list[dict[str, Any]]:
        allowed = state_properties[name]["items"]["properties"]
        return [
            {key: deepcopy(value) for key, value in row.items() if key in allowed}
            for row in getattr(session, name, [])
        ]

    payload = {
        "schema_version": "m1.v0.2",
        "request_id": request_id,
        "task_id": session.task_id,
        "base_version": request["base_version"],
        "control": {
            # Keep the old keys in the wire contract for saved sessions and
            # older providers. They are deliberately non-authoritative: the
            # model must continue until the selected coverage target is met.
            "max_questions": 3,
            "remaining_rounds": 9999,
            "allow_questions": True,
            "context_coverage": session.control.get("context_coverage", "complete"),
            "current_date": current_date or date.today().isoformat(),
            "thinking_level": session.control.get("thinking_level", "standard"),
            "thinking_policy": "coverage_based",
            # Compatibility fields remain for older sessions and UI, but this
            # policy tells the model which signal controls interview quality.
            "quality_policy": "model_judgment_first",
        },
        "state": {
            "selected_category": session.selected_category,
            "requirements": deepcopy(session.requirements),
            "gaps": deepcopy(session.gaps),
            "question_history": question_history,
            "question_reopen_history": reopen_history,
            "open_conflicts": [_open_conflict_for_input(row) for row in session.open_conflicts],
            "pending_proposals": semantic_rows("pending_proposals"),
            "pending_questions": semantic_rows("pending_questions"),
            "interpretation_history": semantic_rows("interpretation_history"),
        },
        "sources": deepcopy(session.sources),
        "current_source_id": session.current_source_id,
        "category_config": deepcopy(CATEGORY_CONFIG),
    }
    errors = sorted(Draft202012Validator(assets.input_schema).iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        session.pending_requests.pop(request_id, None)
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise M1ValidationError(f"M1输入不符合契约（{path}）：{errors[0].message}")
    return payload


def _strict_json_loads(raw: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise M1JsonError(f"模型JSON包含重复键：{key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise M1JsonError(f"模型JSON包含非法数值：{value}")

    try:
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except M1ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise M1JsonError(f"模型未返回有效JSON：第{exc.lineno}行第{exc.colno}列") from None
    if not isinstance(parsed, dict):
        raise M1JsonError("模型JSON根节点必须是对象。")
    return parsed


def _fail(condition: bool, message: str) -> None:
    if condition:
        raise M1ValidationError(message)


def _semantic_tokens(text: str) -> set[str]:
    tokens = {word for word in re.findall(r"[a-z0-9_]+", text.casefold()) if len(word) >= 3}
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.update(run[index : index + 2] for index in range(max(0, len(run) - 1)))
    return tokens


def _reopen_evidence_matches(
    quote: str,
    gap: dict[str, Any],
    histories: list[dict[str, Any]],
) -> bool:
    lowered = quote.casefold()
    directives = (
        "重新问",
        "再问",
        "继续问",
        "可以问",
        "可以聊",
        "重新聊",
        "重新讨论",
        "ask again",
        "ask me again",
        "revisit",
    )
    if not any(marker in lowered for marker in directives):
        return False
    target_text = " ".join(
        [gap.get("scope", ""), gap.get("description", "")]
        + [row.get("text", "") for row in histories]
    )
    return bool(_semantic_tokens(quote) & _semantic_tokens(target_text))


def _validate_interpretations(
    result: dict[str, Any],
    payload: dict[str, Any],
    *,
    closed_gap_ids: set[str],
    reopened_gap_ids: set[str],
) -> None:
    """Validate optional, contextual guesses without turning them into facts.

    Legacy pending_interpretation proposals remain ordinary reviewable drafts.
    Only proposals carrying interpretation_for support the targeted choice UI.
    """
    proposals = [row for row in result["proposals"] if "interpretation_for" in row]
    if not proposals:
        return
    _fail(len(proposals) > 2, "本轮最多提供两个待确认解释。")
    target_ids = {row["interpretation_for"]["gap_id"] for row in proposals}
    _fail(len(target_ids) != 1, "本轮解释必须围绕同一个关键缺口。")
    state = payload["state"]
    gaps = {
        row["gap_id"]: row
        for row in [*state["gaps"], *result["gaps"]]
    }
    questions = {
        row["question_id"]: row
        for row in [*state["question_history"], *state.get("pending_questions", []), *result["questions"]]
    }
    user_ids = {row["source_id"] for row in payload["sources"] if row["role"] == "user"}
    previous_options = [
        row for row in state.get("pending_proposals", [])
        if row.get("interpretation_for", {}).get("gap_id") in target_ids
    ]
    source_count = len(payload["sources"])

    def recorded_source_count(row: dict[str, Any]) -> int:
        # Very old saved sessions did not record this value.  Treat the
        # missing timestamp as "no proven new context" rather than allowing a
        # repeated interpretation merely because the current session has
        # several sources already.
        value = row.get("recorded_source_count")
        return source_count if value is None else int(value)

    def has_new_context(gap_id: str) -> bool:
        return any(
            source_count > recorded_source_count(row)
            for row in state.get("interpretation_history", [])
            if row.get("gap_id") == gap_id
        )

    _fail(len(previous_options) + len(proposals) > 2, "同一缺口的未处理解释最多保留两个。")
    normalized_texts = {" ".join(row["text"].casefold().split()) for row in previous_options}
    for proposal in proposals:
        link = proposal["interpretation_for"]
        gap_id = link["gap_id"]
        gap = gaps.get(gap_id)
        _fail(
            proposal["kind"] != "pending_interpretation"
            or proposal["operation"] != "new"
            or proposal["strength"] != "unspecified",
            "上下文解释只能作为未确认推测，不能冒充用户决定或硬约束。",
        )
        _fail(gap is None or gap_id in closed_gap_ids, "待确认解释没有引用仍未知的具体缺口。")
        _fail(gap["importance"] != "blocking_direction", "解释卡仅用于影响方向的关键含义。")
        _fail(
            (proposal["field"], proposal["scope"]) != (gap["field"], gap["scope"]),
            "待确认解释的字段与适用范围没有对齐目标缺口。",
        )
        question_id = link["question_id"]
        if question_id is not None:
            question = questions.get(question_id)
            _fail(
                question is None
                or question.get("gap_id") != gap_id
                or (question["field"], question["scope"]) != (gap["field"], gap["scope"]),
                "待确认解释没有引用对应缺口的真实问题。",
            )
        _fail(not link["reason"].strip(), "待确认解释必须说明已有信息与推测之间的关系。")
        _fail(
            not any(ref["source_id"] in user_ids for ref in proposal["source_refs"]),
            "待确认解释必须引用用户提供的上下文来源。",
        )
        normalized = " ".join(proposal["text"].casefold().split())
        _fail(normalized in normalized_texts, "不能重复新增同一个未处理解释草稿。")
        normalized_texts.add(normalized)
        _fail(
            gap_id not in reopened_gap_ids
            and not has_new_context(gap_id)
            and any(
                row.get("gap_id") == gap_id and row.get("decision") in {"skipped", "rejected"}
                for row in state.get("interpretation_history", [])
            ),
            "用户已跳过或拒绝解释，不能在没有明确重开时重复猜测。",
        )


def _compat_model_judgment(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Create a quality signal for older valid responses that omitted it.

    The signal is derived from the response's own gaps and next action only to
    preserve compatibility with saved fixtures.  It never closes a gap or
    changes the model's action; new models should still provide the richer
    judgment explicitly.
    """
    returned_gaps = result.get("gaps", [])
    blocking_ids = [
        row["gap_id"] for row in returned_gaps
        if row.get("importance") == "blocking_direction"
    ]
    next_action = result.get("next_action")
    if next_action in {"ask", "need_goal", "resolve_conflict"}:
        assessment = "partial" if blocking_ids or returned_gaps else "unclear"
        continue_interview = True
        confidence = "medium"
    elif next_action == "review_requirements":
        assessment = "sufficient"
        continue_interview = False
        confidence = "medium"
    else:
        assessment = "partial" if blocking_ids or returned_gaps else "sufficient"
        continue_interview = bool(result.get("questions"))
        confidence = "low" if returned_gaps else "medium"
    return {
        "answer_assessment": assessment,
        "critical_gap_ids": blocking_ids,
        "continue_interview": continue_interview,
        "confidence": confidence,
        "reason": "根据当前缺口和下一步建议补充的兼容判断；新响应应优先提供明确的模型判断。",
    }


def _validate_model_judgment_consistency(result: dict[str, Any]) -> None:
    """Reject contradictions between the model signal and its action.

    The judgment is the model's quality bridge to the program.  It does not
    decide whether a user may skip an optional detail, but it must point to
    real current gaps and describe a next step that the response actually
    provides.  These checks catch malformed bridge signals without replacing
    the model's semantic judgment with fixed question counts.
    """
    judgment = result.get("model_judgment")
    if judgment is None or result.get("status") != "ok":
        return
    action = result["next_action"]
    assessment = judgment["answer_assessment"]
    critical = judgment.get("critical_gap_ids", [])
    continue_interview = judgment["continue_interview"]
    gap_ids = {row["gap_id"] for row in result.get("gaps", [])}
    unknown_critical = set(critical) - gap_ids
    if unknown_critical:
        raise M1ValidationError(
            "模型判断引用了本轮没有返回的缺口：" + ", ".join(sorted(unknown_critical))
        )
    if action == "review_requirements" and (
        continue_interview or assessment != "sufficient" or critical
    ):
        raise M1ValidationError(
            "模型判断与需求复核步骤不一致：仍有阻断缺口，回答不充分或仍建议继续追问。"
        )
    if action in {"ask", "need_goal", "resolve_conflict"} and not continue_interview:
        raise M1ValidationError("模型判断与当前追问步骤不一致：模型已判断不必继续，但下一步仍要求追问。")
    if assessment == "sufficient" and (continue_interview or critical):
        raise M1ValidationError("模型判断为信息充分时不能同时声明仍需追问或存在关键缺口。")
    if assessment in {"partial", "unclear", "not_provided"} and not continue_interview:
        if action not in {"pause_with_unknowns", "review_requirements"}:
            raise M1ValidationError("模型判断为信息未完整时，必须继续追问或明确暂停。")
    if continue_interview and action in {"ask", "need_goal"}:
        has_interpretation = any(
            row.get("kind") == "pending_interpretation"
            and row.get("operation") != "withdraw"
            for row in result.get("proposals", [])
        )
        if not result.get("questions") and not has_interpretation:
            raise M1ValidationError(
                "模型要求继续追问，但没有返回可回答的问题或待确认解释。"
            )
    if action == "pause_with_unknowns" and continue_interview:
        raise M1ValidationError("暂停整理时不能同时声明继续追问。")


def _semantic_validate(result: dict[str, Any], payload: dict[str, Any]) -> None:
    for key in ("schema_version", "request_id", "task_id", "base_version"):
        _fail(result[key] != payload[key], f"模型回显字段不一致：{key}")

    if result["status"] == "input_error":
        _fail(result["error"] is None, "input_error必须包含错误说明。")
        for key in (
            "proposals",
            "conflicts",
            "review_item_ids",
            "gap_updates",
            "question_reopens",
            "gaps",
            "questions",
        ):
            _fail(bool(result.get(key, [])), f"input_error时{key}必须为空。")
        readiness = result["readiness"]
        _fail(
            readiness["goal_identified"]
            or readiness["deliverable_identified"]
            or readiness["blocking_gap_ids"],
            "input_error时readiness必须为未识别且无阻断ID。",
        )
        _fail(
            result["category"]["primary"] != "general" or bool(result["category"]["secondary"]),
            "input_error时类别必须回退为general。",
        )
        _fail(result["next_action"] != "pause_with_unknowns", "input_error时必须暂停。")
        return
    _fail(result["error"] is not None, "status=ok时error必须为null。")

    sources = {row["source_id"]: row for row in payload["sources"]}
    state_items = {row["item_id"] for row in payload["state"]["requirements"]}
    for item_id in result["review_item_ids"]:
        _fail(item_id not in state_items, f"待复核需求不存在：{item_id}")
    proposal_ids = [row["proposal_id"] for row in result["proposals"]]
    gap_ids = [row["gap_id"] for row in result["gaps"]]
    question_ids = [row["question_id"] for row in result["questions"]]
    conflict_ids = [row["conflict_id"] for row in result["conflicts"]]
    gap_update_ids = [row["update_id"] for row in result.get("gap_updates", [])]
    reopen_ids = [row["reopen_id"] for row in result.get("question_reopens", [])]
    for label, ids in (
        ("proposal", proposal_ids),
        ("gap", gap_ids),
        ("question", question_ids),
        ("conflict", conflict_ids),
        ("gap_update", gap_update_ids),
        ("question_reopen", reopen_ids),
    ):
        _fail(len(ids) != len(set(ids)), f"{label} ID在响应内重复。")

    selected = payload["state"]["selected_category"]
    if selected is not None:
        _fail(result["category"]["primary"] != selected, "模型静默改变了用户已选类别。")
    _fail(
        result["category"]["primary"] in result["category"]["secondary"],
        "secondary不能重复primary。",
    )
    allowed_fields = set(payload["category_config"]["common_fields"])
    for category in [result["category"]["primary"], *result["category"]["secondary"]]:
        allowed_fields.update(payload["category_config"]["category_fields"][category])

    def check_refs(record: dict[str, Any]) -> None:
        for ref in record.get("source_refs", []):
            source = sources.get(ref["source_id"])
            _fail(source is None or ref["quote"] not in source["text"], "来源引用不是对应文本的逐字片段。")
        for item_id in record.get("depends_on", []):
            _fail(item_id not in state_items, f"依赖引用了不存在的旧需求：{item_id}")

    user_source_ids = {key for key, value in sources.items() if value["role"] == "user"}
    for proposal in result["proposals"]:
        _fail(proposal["field"] not in allowed_fields, f"候选字段不在类别配置中：{proposal['field']}")
        check_refs(proposal)
        if proposal["operation"] == "new":
            _fail(proposal["target_item_id"] is not None, "new候选不能引用已有需求。")
        else:
            _fail(proposal["target_item_id"] not in state_items, "修改候选没有引用已有需求。")
        if proposal["kind"] in {"user_fact", "user_decision"}:
            _fail(
                not any(ref["source_id"] in user_source_ids for ref in proposal["source_refs"]),
                "用户事实或决定缺少用户来源。",
            )
    for gap in result["gaps"]:
        _fail(gap["field"] not in allowed_fields, f"缺口字段不在类别配置中：{gap['field']}")
        check_refs(gap)
    gaps = {row["gap_id"]: row for row in result["gaps"]}
    state_gaps = {row["gap_id"]: row for row in payload["state"]["gaps"]}
    pending_answers = {
        row.get("answer_id"): row
        for row in payload["state"]["question_history"]
        if row.get("answer_id") and row.get("assessment_status") == "pending"
    }
    updated_gap_ids: set[str] = set()
    updated_answer_ids: set[str] = set()
    for update in result.get("gap_updates", []):
        target_gap_id = update["target_gap_id"]
        answer_id = update["answer_id"]
        target_gap = state_gaps.get(target_gap_id)
        answer = pending_answers.get(answer_id)
        _fail(target_gap is None, f"缺口更新引用了不存在的缺口：{target_gap_id}")
        _fail(answer is None, f"缺口更新引用了不存在或已处理的回答：{answer_id}")
        allowed_gaps = set(answer.get("context_gap_ids", [])) | {answer.get("gap_id")}
        _fail(target_gap_id not in allowed_gaps, "缺口更新的回答与目标缺口不一致。")
        _fail(target_gap_id in answer.get("assessed_gap_ids", []), "这条回答已经评估过该缺口。")
        _fail(answer["state_version"] > payload["base_version"], "缺口更新引用了过期版本之外的回答。")
        ref = update["source_ref"]
        source = sources.get(ref["source_id"])
        _fail(
            source is None
            or source.get("role") != "user"
            or ref["source_id"] != answer["answer_source_id"]
            or ref["quote"] not in source.get("text", "")
            or ref["quote"] not in answer["answer_text"],
            "缺口更新没有引用对应回答的真实来源。",
        )
        _fail(target_gap_id in updated_gap_ids, "同一缺口不能在一轮中重复更新。")
        _fail(answer_id in updated_answer_ids and not answer.get("context_gap_ids"), "同一回答不能在一轮中重复使用。")
        updated_gap_ids.add(target_gap_id)
        updated_answer_ids.add(answer_id)
        remaining = update["remaining_description"]
        if update["action"] in {"partial", "unresolved"}:
            _fail(not remaining or not remaining.strip(), "部分或未解决的缺口更新必须说明剩余未知。")
        else:
            _fail(remaining is not None, "已解决或不再适用的缺口更新不能保留剩余未知。")

    reopened_gap_ids: set[str] = set()
    closed_gap_ids = {
        row["target_gap_id"]
        for row in result.get("gap_updates", [])
        if row["action"] in {"resolved", "not_applicable"}
    }
    source_positions = {row["source_id"]: index + 1 for index, row in enumerate(payload["sources"])}
    current_source_id = payload["current_source_id"]
    for reopen in result.get("question_reopens", []):
        gap_id = reopen["target_gap_id"]
        target_gap = state_gaps.get(gap_id)
        _fail(target_gap is None, f"问题重开引用了不存在的缺口：{gap_id}")
        histories = [
            row
            for row in payload["state"]["question_history"]
            if row.get("gap_id") == gap_id and row["disposition"] in {"skipped", "unsure"}
        ]
        _fail(not histories, "问题重开没有对应的跳过或不确定历史。")
        ref = reopen["source_ref"]
        source = sources.get(ref["source_id"])
        _fail(
            source is None
            or source.get("role") != "user"
            or ref["source_id"] != current_source_id
            or ref["quote"] not in source.get("text", ""),
            "问题重开必须引用本轮最新用户来源。",
        )
        _fail(
            source_positions.get(ref["source_id"], 0)
            <= max(row.get("recorded_source_count", 0) for row in histories),
            "问题重开来源没有晚于原跳过记录。",
        )
        _fail(
            not _reopen_evidence_matches(ref["quote"], target_gap, histories),
            "问题重开依据没有同时指明重新询问和对应范围。",
        )
        _fail(gap_id in reopened_gap_ids, "同一缺口不能在一轮中重复重开。")
        reopened_gap_ids.add(gap_id)

    _validate_interpretations(
        result, payload, closed_gap_ids=closed_gap_ids, reopened_gap_ids=reopened_gap_ids
    )

    skipped_or_unsure_histories = [
        row
        for row in payload["state"]["question_history"]
        if row["disposition"] in {"skipped", "unsure"}
    ]
    pending_answer_scopes = {
        (row["field"], row["scope"]): row.get("gap_id")
        for row in payload["state"]["question_history"]
        if row["disposition"] == "answered" and row.get("assessment_status") == "pending"
    }
    continued_answer_gap_ids = {
        row["target_gap_id"]
        for row in result.get("gap_updates", [])
        if row["action"] in {"partial", "unresolved"}
    }
    resolved_question_histories = [
        row
        for row in payload["state"]["question_history"]
        if row.get("disposition") == "answered"
        and row.get("assessment_status") == "applied"
        and row.get("gap_id") not in state_gaps
    ]
    source_count = len(payload["sources"])

    def repeats_resolved_question(question: dict[str, Any]) -> bool:
        for history in resolved_question_histories:
            if (question["field"], question["scope"]) != (history["field"], history["scope"]):
                continue
            if source_count > history.get("recorded_source_count", 0):
                continue
            old_text = " ".join(history.get("text", "").casefold().split())
            new_text = " ".join(question.get("text", "").casefold().split())
            if old_text == new_text:
                return True
            old_tokens = _semantic_tokens(old_text)
            new_tokens = _semantic_tokens(new_text)
            if old_tokens and new_tokens:
                overlap = len(old_tokens & new_tokens) / max(1, min(len(old_tokens), len(new_tokens)))
                if overlap >= 0.8:
                    return True
        return False

    for question in result["questions"]:
        _fail(question["field"] not in allowed_fields, f"问题字段不在类别配置中：{question['field']}")
        _fail(question["gap_id"] in closed_gap_ids, "已经建议关闭的缺口不能在同一轮继续提问。")
        skipped_histories = [
            row
            for row in skipped_or_unsure_histories
            if (row["field"], row["scope"]) == (question["field"], question["scope"])
            or row.get("gap_id") == question.get("gap_id")
        ]
        has_new_context = any(
            source_count > (
                int(row["recorded_source_count"])
                if row.get("recorded_source_count") is not None
                else source_count
            )
            for row in skipped_histories
        )
        _fail(
            bool(skipped_histories)
            and not has_new_context
            and question["gap_id"] not in reopened_gap_ids,
            "用户已跳过或表示不确定的问题不能在无新上下文时重复询问。",
        )
        pending_gap_id = pending_answer_scopes.get((question["field"], question["scope"]))
        _fail(
            pending_gap_id is not None
            and (
                question["gap_id"] != pending_gap_id
                or question["gap_id"] not in continued_answer_gap_ids
            ),
            "用户回答尚未完成评估，不能换用新缺口编号重复询问同一范围。",
        )
        _fail(
            repeats_resolved_question(question),
            "已经解决的问题不能在没有新用户依据时换编号或换措辞重复询问。",
        )
        check_refs(question)
        gap = gaps.get(question["gap_id"])
        _fail(
            gap is None or gap["field"] != question["field"] or gap["scope"] != question["scope"],
            "问题没有与本轮返回的缺口对齐。",
        )
    for gap_id in reopened_gap_ids:
        _fail(
            not any(question["gap_id"] == gap_id for question in result["questions"]),
            "问题重开建议没有返回对应缺口的问题。",
        )
    # These values are legacy UI hints carried in the stable input contract.
    # The model decides whether an unresolved direction still needs a question;
    # rejecting that decision here was the cause of the JGS dead end.  The JSON
    # Schema still bounds one response to three questions, while duplicate,
    # stale, unsupported, and unreferenced questions remain hard failures.

    judgment = result.get("model_judgment")
    if judgment is not None:
        known_gap_ids = set(state_gaps) | set(gaps)
        _fail(
            any(gap_id not in known_gap_ids for gap_id in judgment.get("critical_gap_ids", [])),
            "模型判断引用了当前状态中不存在的缺口。",
        )

    pending_proposal_ids = {row["proposal_id"] for row in payload["state"].get("pending_proposals", [])}
    available_proposal_ids = pending_proposal_ids | set(proposal_ids)
    for conflict in result["conflicts"]:
        _fail(any(item not in state_items for item in conflict["existing_item_ids"]), "冲突引用了不存在的旧需求。")
        _fail(any(pid not in available_proposal_ids for pid in conflict["proposal_ids"]), "冲突引用了不存在的候选草稿。")
    old_conflicts = payload["state"]["open_conflicts"]
    old_conflict_ids = {row["conflict_id"] for row in old_conflicts}
    _fail(not old_conflict_ids.issubset(set(conflict_ids)), "历史未解决冲突无依据消失。")
    returned_conflicts = {row["conflict_id"]: row for row in result["conflicts"]}
    for old_conflict in old_conflicts:
        protected_item_ids = set(old_conflict.get("item_ids", [])) & state_items
        returned_item_ids = set(returned_conflicts[old_conflict["conflict_id"]]["existing_item_ids"])
        _fail(
            not protected_item_ids.issubset(returned_item_ids),
            "历史未解决冲突遗漏或替换了仍有效的正式需求参与方。",
        )
        protected_proposal_ids = set(old_conflict.get("proposal_ids", [])) & pending_proposal_ids
        _fail(
            not protected_proposal_ids.issubset(returned_conflicts[old_conflict["conflict_id"]]["proposal_ids"]),
            "历史未解决冲突遗漏或替换了仍待处理的候选参与方。",
        )
    if result["conflicts"]:
        _fail(result["next_action"] != "resolve_conflict", "存在冲突时未优先进入冲突处理。")
        if all(row["change_intent"] == "explicit_change" for row in result["conflicts"]):
            _fail(bool(result["questions"]), "用户已经明确修改时不能重复追问同一选择。")

    blocking = {row["gap_id"] for row in result["gaps"] if row["importance"] == "blocking_direction"}
    _fail(set(result["readiness"]["blocking_gap_ids"]) != blocking, "readiness的阻断缺口列表不一致。")
    if result["next_action"] not in {"ask", "need_goal", "resolve_conflict"}:
        _fail(bool(result["questions"]), "当前下一步不允许携带问题。")
    if result["next_action"] == "ask":
        _fail(not result["questions"], "ask路径没有返回问题。")
    if result["next_action"] == "review_requirements":
        ready = result["readiness"]
        judgment = result.get("model_judgment")
        if judgment is not None and (
            judgment["continue_interview"]
            or judgment["answer_assessment"] != "sufficient"
            or judgment.get("critical_gap_ids")
        ):
            raise M1ValidationError(
                "模型判断与需求复核步骤不一致：仍有阻断缺口，回答不充分或仍建议继续追问。"
            )
        _fail(
            not ready["goal_identified"]
            or not ready["deliverable_identified"]
            or bool(blocking)
            or bool(result["conflicts"])
            or payload["control"]["context_coverage"] != "complete",
            "需求复核门槛未满足。",
        )


def _incremental_result(result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Expand only omitted state, without repairing explicit unsafe changes.

    The raw object has already passed the unchanged output Schema.  The full
    input snapshot remains available for provenance and the original semantic
    checks; it is not replaced by a model summary.
    """
    if result["status"] != "ok":
        return result
    effective = deepcopy(result)
    state = payload["state"]

    def requirement_key(row: dict[str, Any]) -> tuple[str, ...]:
        return tuple(" ".join(str(row[key]).split()).casefold() for key in (
            "field", "scope", "text", "kind", "strength"
        ))

    existing_keys = {requirement_key(row) for row in state["requirements"]}
    current_sources = {
        row["answer_source_id"]
        for row in state["question_history"]
        if row.get("disposition") == "answered"
        and row.get("assessment_status") == "pending"
        and row.get("answer_source_id")
    }
    if not current_sources and payload.get("current_source_id"):
        current_sources.add(payload["current_source_id"])
    result_missing = not any(
        row.get("field") == "deliverable"
        for row in [*state["requirements"], *state.get("pending_proposals", [])]
    )
    for proposal in effective["proposals"]:
        _fail(
            proposal["operation"] == "new" and requirement_key(proposal) in existing_keys,
            "增量响应重复新增了未变化的已有需求。",
        )
        if proposal["kind"] in {"user_fact", "user_decision", "pending_interpretation"}:
            # A missing result can be extracted from the original user task;
            # every source and quote still passes the usual semantic checks.
            result_backfill = (
                result_missing and proposal["operation"] == "new"
                and proposal["field"] == "deliverable"
                and proposal["kind"] in {"user_fact", "user_decision"}
                and bool(proposal["source_refs"])
            )
            _fail(
                not result_backfill and not any(ref["source_id"] in current_sources for ref in proposal["source_refs"]),
                "增量需求更新缺少本轮待评估回答或当前用户输入的来源。",
            )

    # Only explicit, validated updates may close gaps.  Invalid update evidence
    # still fails below, before any result can reach SessionState.
    closed_ids = {
        row["target_gap_id"] for row in effective["gap_updates"]
        if row["action"] in {"resolved", "not_applicable"}
    }
    returned_gap_ids = {row["gap_id"] for row in effective["gaps"]}
    effective["gaps"].extend(
        deepcopy(row) for row in state["gaps"]
        if row["gap_id"] not in returned_gap_ids and row["gap_id"] not in closed_ids
    )

    returned_conflict_ids = {row["conflict_id"] for row in effective["conflicts"]}
    for old in state["open_conflicts"]:
        if old["conflict_id"] not in returned_conflict_ids:
            effective["conflicts"].append({
                "conflict_id": old["conflict_id"],
                "existing_item_ids": list(old["item_ids"]),
                "proposal_ids": list(old.get("proposal_ids", [])),
                "description": old["description"],
                # The input snapshot does not carry a user resolution event.
                "change_intent": "unclear",
            })
    return effective


def parse_m1_response(
    raw: str,
    payload: dict[str, Any],
    output_schema: dict[str, Any],
    *,
    incremental: bool = False,
) -> dict[str, Any]:
    result = _strict_json_loads(raw)
    errors = sorted(Draft202012Validator(output_schema).iter_errors(result), key=lambda e: list(e.path))
    if errors:
        path = ".".join(str(part) for part in errors[0].path) or "$"
        raise M1ValidationError(f"M1输出不符合Schema（{path}）：{errors[0].message}")
    if incremental:
        result = _incremental_result(result, payload)
    if result.get("status") == "ok" and "model_judgment" not in result:
        if "model_judgment" in output_schema.get("properties", {}):
            result["model_judgment"] = _compat_model_judgment(result, payload)
    _validate_model_judgment_consistency(result)
    _semantic_validate(result, payload)
    return result


def apply_m1_response(session: SessionState, payload: dict[str, Any], result: dict[str, Any]) -> None:
    session.stage_m1_result(payload["request_id"], payload["base_version"], result)
