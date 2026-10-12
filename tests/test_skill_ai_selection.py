import hashlib
import json
from pathlib import Path

import pytest

from promptsmith.local_skill_search import discover_local_skill_candidates
from promptsmith.skill_ai_selection import SkillAiSelectionError, select_skill_candidates_with_ai


class ScriptedClient:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def complete_json(self, prompt, payload, schema):
        self.calls.append((prompt, payload, schema))
        return type("Result", (), {"content": json.dumps(self.answers.pop(0), ensure_ascii=False)})()


def _skill(root: Path, name: str, description: str, body: str) -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8")
    return path


def test_discovery_offers_all_local_files_for_model_review(tmp_path):
    _skill(tmp_path, "teaching", "How to teach a lesson", "Make difficult ideas accessible.")
    _skill(tmp_path, "deploy", "Deploy websites", "Configure servers.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": ["step1"]}]

    result = discover_local_skill_candidates(works, context_text="给初学者讲解分部积分法", roots=[tmp_path])

    assert {row["name"] for row in result.candidates} == {"teaching", "deploy"}
    assert all(row["selection_allowed"] for row in result.candidates)
    assert result.scanned_files == 2


def test_model_reads_source_and_selects_indirectly_useful_skill(tmp_path):
    teaching = _skill(tmp_path, "teaching", "Design clear lessons", "Start with an intuitive example.\nAsk the learner to explain each step.")
    _skill(tmp_path, "deploy", "Deploy websites", "Configure servers.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": ["step1"]}]
    discovered = discover_local_skill_candidates(works, context_text="给初学者讲解分部积分法", roots=[tmp_path])
    selected_id = next(row["candidate_id"] for row in discovered.candidates if row["name"] == "teaching")
    client = ScriptedClient([
        {"matches": [{"candidate_id": selected_id, "key_work_id": "math", "reason": "可用直观例子和复述检查帮助初学者理解分部积分。"}]},
    ])

    selected = select_skill_candidates_with_ai(client, discovered.candidates, task_text="给初学者讲解分部积分法", key_works=works)

    assert [row["name"] for row in selected] == ["teaching"]
    assert selected[0]["match_reason"] == "可用直观例子和复述检查帮助初学者理解分部积分。"
    assert selected[0]["record_hash"] == next(row["record_hash"] for row in discovered.candidates if row["name"] == "teaching")
    assert len(client.calls) == 1
    reviewed = next(row for row in client.calls[0][1]["skills"] if row["candidate_id"] == selected_id)
    assert reviewed["source"] == teaching.read_bytes().decode("utf-8-sig")
    assert "间接" in client.calls[0][0]


def test_ai_selection_requires_agent_skills_not_general_methods(tmp_path):
    _skill(tmp_path, "teaching", "Agent teaching workflow", "Use examples and check understanding.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": ["step1"]}]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    candidate_id = discovered.candidates[0]["candidate_id"]
    client = ScriptedClient([
        {"matches": [{"candidate_id": candidate_id, "key_work_id": "math", "reason": "可指导 Agent 组织讲解。"}]},
    ])

    select_skill_candidates_with_ai(client, discovered.candidates, task_text="讲解分部积分法", key_works=works)

    for prompt, _payload, _schema in client.calls:
        assert "AI Agent" in prompt
        assert "SKILL.md" in prompt
        assert "普通网页" in prompt
        assert "方法文章" in prompt


def test_changed_source_is_rejected_before_model_call(tmp_path):
    path = _skill(tmp_path, "teaching", "Design lessons", "Make examples clear.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": []}]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    path.write_text(path.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    client = ScriptedClient([])

    with pytest.raises(SkillAiSelectionError, match="已变化"):
        select_skill_candidates_with_ai(client, discovered.candidates, task_text="讲解分部积分法", key_works=works)
    assert client.calls == []


def test_bad_model_response_is_visible_failure(tmp_path):
    _skill(tmp_path, "teaching", "Design lessons", "Make examples clear.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": []}]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    client = ScriptedClient([{"not_candidate_ids": []}])

    with pytest.raises(SkillAiSelectionError, match="格式"):
        select_skill_candidates_with_ai(client, discovered.candidates, task_text="讲解分部积分法", key_works=works)


def test_model_can_reject_all_skills(tmp_path):
    _skill(tmp_path, "deploy", "Deploy websites", "Configure servers.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": []}]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    client = ScriptedClient([{"matches": []}])

    assert select_skill_candidates_with_ai(client, discovered.candidates, task_text="讲解分部积分法", key_works=works) == []
    assert len(client.calls) == 1


def test_model_can_bind_skill_to_best_key_work(tmp_path):
    _skill(tmp_path, "teaching", "Design lessons", "Explain concepts with examples.")
    works = [
        {"key_work_id": "draft", "title": "Design lessons draft", "step_ids": ["draft-step"]},
        {"key_work_id": "teach", "title": "讲解分部积分法", "step_ids": ["teach-step"]},
    ]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    source = discovered.candidates[0]
    client = ScriptedClient([
        {"matches": [{"candidate_id": source["candidate_id"], "key_work_id": "teach", "reason": "提供授课方法。"}]},
    ])

    result = select_skill_candidates_with_ai(client, discovered.candidates, task_text="讲解分部积分法", key_works=works)

    assert result[0]["key_work_id"] == "teach"
    assert result[0]["step_ids"] == ["teach-step"]
    assert result[0]["candidate_id"] != source["candidate_id"]
    assert result[0]["record_hash"] == source["record_hash"]


def test_remote_source_text_must_match_verified_hash():
    source = b"---\nname: useful\n---\n# Useful"
    remote = {
        "candidate_id": "remote-1", "skill_id": "remote-useful", "name": "useful",
        "description": "Useful lessons", "key_work_id": "math", "step_ids": [],
        "origin": "remote", "content_sha256": hashlib.sha256(source).hexdigest(),
        "record_snapshot": {"source_text": source.decode()},
    }
    client = ScriptedClient([{"matches": [{"candidate_id": "remote-1", "key_work_id": "math", "reason": "Useful."}]}])

    rows = select_skill_candidates_with_ai(client, [remote], task_text="Teach math", key_works=[{"key_work_id": "math", "title": "Teach math"}])

    assert rows[0]["candidate_id"] == "remote-1"
    remote["record_snapshot"]["source_text"] = "changed"
    with pytest.raises(SkillAiSelectionError, match="核验"):
        select_skill_candidates_with_ai(client, [remote], task_text="Teach math", key_works=[{"key_work_id": "math", "title": "Teach math"}])


def test_model_relevance_scores_order_selected_skills(tmp_path):
    _skill(tmp_path, "teaching", "Design lessons", "Explain concepts with examples.")
    _skill(tmp_path, "writing", "Write simply", "Use familiar words.")
    works = [{"key_work_id": "math", "title": "讲解分部积分法", "step_ids": []}]
    discovered = discover_local_skill_candidates(works, roots=[tmp_path])
    ids = [row["candidate_id"] for row in discovered.candidates]
    client = ScriptedClient([
        {"matches": [
            {"candidate_id": ids[0], "key_work_id": "math", "reason": "适合。", "relevance_score": 2},
            {"candidate_id": ids[1], "key_work_id": "math", "reason": "更适合。", "relevance_score": 5},
        ]},
    ])

    selected = select_skill_candidates_with_ai(client, discovered.candidates, task_text="讲解分部积分法", key_works=works)

    assert [row["candidate_id"] for row in selected] == [ids[1], ids[0]]


def test_model_can_review_builtin_catalog_candidate_from_summary_evidence():
    from promptsmith.skill_catalog import SkillCatalog, _default_catalog_path

    works = [{
        "key_work_id": "software-spec",
        "title": "为活动报名软件整理需求规格和用户故事",
        "goal": "将已确认的软件需求整理为可验证的规格文档",
        "step_ids": ["spec-step"],
    }]
    catalog = SkillCatalog.load(_default_catalog_path())
    candidates = catalog.match(works).candidates
    candidate = next(row for row in candidates if row["skill_id"] == "to-spec")
    client = ScriptedClient([
        {"matches": [{
            "candidate_id": candidate["candidate_id"],
            "key_work_id": "software-spec",
            "reason": "该目录摘要描述了把讨论内容整理为规格文档的方法。",
        }]},
    ])

    selected = select_skill_candidates_with_ai(
        client, candidates, task_text="为活动报名软件整理需求规格", key_works=works
    )

    assert [row["skill_id"] for row in selected] == ["to-spec"]
    evidence = next(row["evidence"] for row in client.calls[0][1]["skills"]
                    if row["candidate_id"] == candidate["candidate_id"])
    assert evidence["evidence_level"] == "metadata"
    assert "本地 Skill 目录摘要" in evidence["evidence_basis"]
    assert "完整 Skill 内容未包含在目录快照中" in evidence["limitations"][0]
