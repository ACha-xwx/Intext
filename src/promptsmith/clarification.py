"""Read-only front-stage questions; planning unknowns go to the downstream AI."""
from copy import deepcopy
import hashlib
import json
import re
import unicodedata


def answered_question_clarification(question, history):
    """Return a focused clarification only for a repeated, answered question.

    Same scope alone is insufficient: new details must remain askable. Match
    ordered decision text, allowing alternatives to swap positions, without
    losing the association of conditions, numbers and negations.
    """
    def wording(text):
        return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())

    def decision_words(text):
        # A small set of interrogative forms and synonymous editing verbs.
        # Keep nouns, negation, quantities and conditions: new content wins.
        for prefix in ("这次改版的范围是", "本次改版的范围是", "请问"):
            text = text.removeprefix(prefix)
        text = re.sub(r"也(?=可以|允许|调整|修改)", "", text)
        text = re.sub(r"可不可以|能不能|是否|可否|能否|允许|可以|[吗呢]$", "", text)
        return text.replace("修改", "调整")

    new = wording(question.get("text", ""))
    answers = [row for row in reversed(history)
               if row.get("disposition") == "answered" and row.get("answer_text", "").strip()
               and (row.get("gap_id") == question.get("gap_id") or
                    (row.get("field"), row.get("scope")) == (question.get("field"), question.get("scope")))]
    for row in answers:
        old = wording(row.get("text", ""))
        repeated = bool(new and old == new)
        old_decision, new_decision = decision_words(old), decision_words(new)
        if not repeated and "还是" not in old and "还是" not in new:
            # Moving "adjust" before/after the same object is a paraphrase;
            # an added object/condition, or a different action, is not.
            if old_decision.count("调整") == new_decision.count("调整") == 1:
                repeated = old_decision.replace("调整", "") == new_decision.replace("调整", "")
        if not repeated and old_decision.count("还是") == new_decision.count("还是") == 1:
            old_choices = old_decision.split("还是")
            new_choices = new_decision.split("还是")
            # The old precondition can be omitted from a shorter restatement,
            # but a newly specified condition must remain significant.
            condition = re.match(r"在.+?的前提下", old_choices[0])
            if condition and condition[0] not in new_decision and not new_decision.startswith("在"):
                old_choices[0] = old_choices[0][condition.end():]
            def choice_text(text):
                # "Only appearance" already excludes changing layout. This
                # one redundant suffix is optional; all other words, including
                # negations, conditions and quantities, must remain identical.
                if text.startswith("只改"):
                    text = text.removesuffix("保持现有布局不动")
                return text
            repeated = sorted(map(choice_text, old_choices)) == sorted(map(choice_text, new_choices))
        if repeated:
            # Display a short reference; complete answers remain in history and
            # source evidence. An interrogative answer is not an affirmative.
            same_gap = next((item for item in answers if item.get("gap_id") == question.get("gap_id")), row)
            answer = same_gap["answer_text"].strip()
            excerpt = answer[:240] + ("…" if len(answer) > 240 else "")
            return (f"关于{question.get('scope') or '这项要求'}，你上一条回答“{excerpt}”中的具体决定还不明确。"
                    "请直接说明你希望如何处理这一点。")
    return None


def skipped_gap_ids(session):
    """Latest explicit decisions win; reopening is a user's opt-in."""
    latest = {row.get("gap_id"): row.get("disposition") for row in session.question_history
              if row.get("gap_id") and not row.get("superseded_by_answer_id")}
    skipped = {key for key, decision in latest.items() if decision == "skipped"}
    skipped.update(row["gap_id"] for row in session.gaps
                   if row.get("origin") == "user_skipped" and row.get("gap_id") not in latest)
    return skipped - {row.get("gap_id") for row in session.pending_questions
                      if row.get("user_requested_reopen")}


def without_skipped_unknowns(session, rows):
    """Exclude skipped items by provenance or exact wording, never guess an answer."""
    skipped = skipped_gap_ids(session)
    latest = {row.get("gap_id"): row.get("disposition") for row in session.question_history
              if row.get("gap_id") and not row.get("superseded_by_answer_id")}
    opted_in = {key for key, choice in latest.items() if choice != "skipped"}
    opted_in.update(row.get("gap_id") for row in session.pending_questions if row.get("user_requested_reopen"))
    latest_questions = {row.get("question_id"): row for row in session.question_history}
    reopened = {row.get("question_id") for row in session.pending_questions if row.get("user_requested_reopen")}
    for history in latest_questions.values():
        if history.get("disposition") == "skipped" and history.get("plan_unknown") and history.get("question_id") not in reopened:
            skipped.add(history["plan_unknown"].get("unresolved_id"))
    skipped.discard(None)
    descriptions = {re.sub(r"\s+", "", row.get("description", ""))
                    for row in session.gaps if row.get("gap_id") in skipped}
    descriptions.update(re.sub(r"\s+", "", row["plan_unknown"].get("description", ""))
                        for row in latest_questions.values() if row.get("disposition") == "skipped"
                        and row.get("plan_unknown") and row.get("question_id") not in reopened)
    descriptions.discard("")
    result = []
    for row in rows:
        ids = {row.get(key) for key in ("gap_id", "source_gap_id", "unresolved_id", "unknown_id")}
        wording = {re.sub(r"\s+", "", str(row.get(key) or ""))
                   for key in ("description", "source_description")}
        if (ids & skipped or (row.get("origin") == "user_skipped" and not ids & opted_in)
                or wording & descriptions
                or any(text.startswith("用户已选择先做草稿，这项含义仍未确定：" + description)
                       for text in wording for description in descriptions)):
            continue
        result.append(deepcopy(row))
    return result


def plan_unknown_description(gap):
    if gap.get("importance") == "blocking_direction":
        return ("用户已选择先做草稿，这项含义仍未确定：" + gap["description"]
                + "。只整理不依赖该信息的结构与步骤；相关具体内容等用户补充后完善，不得猜测填满。")
    return gap["description"]


def review_key(session, scope, row):
    fields = ("gap_id", "field", "scope", "description", "importance") if scope == "requirements" else (
        "source_gap_id", "description", "impact", "continuable_work", "confirm_by", "related_requirement_ids")
    basis = {"task_id": session.task_id, "task_text": session.task_text,
             "category": session.selected_category, "scope": scope,
             "item": {key: row.get(key) for key in fields}}
    if scope == "plan":
        basis["requirements"] = [{key: r.get(key) for key in ("item_id", "field", "text", "scope", "strength")}
                                 for r in session.requirements]
        basis["goal"] = (session.plan.get("content") or {}).get("goal")
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def review_candidates(session, *, include_plan=True):
    """Project requirement reviews without restarting the interview from a plan.

    include_plan remains a compatibility argument for existing callers.
    A current sufficient assessment ends ordinary follow-ups, but never
    resolves or confirms unknowns or bypasses a blocking direction gap.
    """
    deferred = {r.get("clarification_key") for r in session.question_history
                if r.get("disposition") in {"skipped", "unsure"}}
    waiting = {r.get("clarification_key") for r in session.question_history
               if r.get("disposition") == "answered" and r.get("assessment_status") == "pending"}
    rows = []
    existing_gaps = {q.get("gap_id") for q in session.pending_questions if q.get("gap_id")}
    authorization = session.current_draft_authorization()
    judgment = session.last_model_judgment or {}
    readiness = session.last_readiness or {}
    sufficient = (session.analysis_basis_version == session.requirement_version
                  and session.last_next_action == "review_requirements"
                  and judgment.get("answer_assessment") == "sufficient"
                  and judgment.get("continue_interview") is False
                  and not judgment.get("critical_gap_ids")
                  and readiness.get("goal_identified") and readiness.get("deliverable_identified")
                  and not readiness.get("blocking_gap_ids") and not session.open_conflicts)
    for gap in session.active_gaps():
        key = review_key(session, "requirements", gap)
        reviewed = any(r.get("gap_id") == gap.get("gap_id") and r.get("clarification_key") for r in session.question_history)
        legacy_deferred = gap.get("origin") in {"user_skipped", "user_unsure"} and not reviewed
        if ((sufficient and gap.get("importance") == "can_defer")
                or gap.get("gap_id") in existing_gaps or key in deferred
                or legacy_deferred
                or (authorization and gap.get("importance") == "blocking_direction")
                or (key in waiting and session.analysis_basis_version != session.requirement_version)):
            continue
        question = {"question_id": "review-" + key, "gap_id": gap["gap_id"],
                     "field": gap["field"], "scope": gap["scope"],
                     "text": f"请补充：{gap['description']}\n你希望如何安排这项内容？",
                     "options": [], "reason": "需要用户回答或明确暂缓", "depends_on": deepcopy(gap.get("depends_on", [])),
                     "clarification_key": key, "clarification_scope": "requirements"}
        clarification = answered_question_clarification({**question, "text": gap["description"]}, session.question_history)
        if clarification:
            question["text"] = clarification
        rows.append(question)
    return rows
