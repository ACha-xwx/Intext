"""Front-load questions; ask permission for each batch after the first five."""
from copy import deepcopy
import logging

ROUND_LIMIT = 5


def rounds_used(session):
    try:
        return max(0, int(session.control.get("interview_rounds_used", 0)))
    except (ValueError, TypeError, OverflowError):
        return 0


def round_limit(session):
    try:
        return max(ROUND_LIMIT, int(session.control.get("interview_round_limit", ROUND_LIMIT)))
    except (ValueError, TypeError, OverflowError):
        return ROUND_LIMIT


def close_question_batch(result, *, exhausted):
    """Keep facts and unknowns while preventing another automatic question round."""
    if not exhausted or result.get("status", "ok") != "ok":
        return result
    result = deepcopy(result)
    removed = {q["question_id"] for q in result.get("questions", [])}
    result["questions"] = []
    result["question_reopens"] = []
    for proposal in result.get("proposals", []):
        interpretation = proposal.get("interpretation_for") or {}
        if interpretation.get("question_id") in removed:
            interpretation["question_id"] = None
    has_conflicts = bool(result.get("conflicts"))
    if result.get("model_judgment"):
        result["model_judgment"]["continue_interview"] = has_conflicts
    # A limit is not evidence that the task is sufficiently specified.
    if has_conflicts:
        # Resolving contradictory requirements is an explicit user decision,
        # not permission to automatically start another question batch.
        result["next_action"] = "resolve_conflict"
    elif result.get("next_action") in {"ask", "need_goal", "resolve_conflict"}:
        result["next_action"] = "pause_with_unknowns"
    result["assistant_text"] = "本轮访谈已整理。仍有未知时，请选择再问一轮，或将这些内容保留到使用提示词时补充。"
    if removed:
        logging.getLogger(__name__).info("Interview round limit reached; new questions withheld=%s; unknowns retained", len(removed))
    return result
