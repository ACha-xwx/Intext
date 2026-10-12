import json
from pathlib import Path
from types import SimpleNamespace

from promptsmith.local_skill_search import discover_local_skill_candidates
from promptsmith.skill_ai_selection import select_skill_candidates_with_ai
from promptsmith.local_skill_index import indexed_skill_metadata
import promptsmith.local_skill_search as local
import pytest
from promptsmith.skill_recommendation import shortlist_candidates
from promptsmith.skill_ai_selection import SkillAiSelectionError


class AcceptAllClient:
    def __init__(self):
        self.calls = []

    def complete_json(self, prompt, payload, schema):
        self.calls.append((prompt, payload))
        if "candidate_ids" in schema["properties"]:
            value = {"candidate_ids": [row["candidate_id"] for row in payload["skills"]]}
        else:
            value = {"matches": [{"candidate_id": row["candidate_id"], "key_work_id": "ui", "reason": "可指导界面设计。", "recommendation_score": .9} for row in payload["skills"]]}
        return SimpleNamespace(content=json.dumps(value, ensure_ascii=False))


def test_large_library_has_bounded_model_calls_and_no_duplicate_source(tmp_path):
    for n in range(55):
        path = tmp_path / f"ui-design-{n}" / "SKILL.md"
        path.parent.mkdir()
        path.write_text(f"---\nname: ui-design-{n}\ndescription: Design interface layouts\n---\n" + "UI design instructions.\n" * 1800 + str(n), encoding="utf-8")
    works = [{"key_work_id": "ui", "title": "UI design", "step_ids": []}]
    found = discover_local_skill_candidates(works, context_text="UI design", roots=[tmp_path])
    client = AcceptAllClient()
    rows = select_skill_candidates_with_ai(client, found.candidates, task_text="UI design", key_works=works)
    assert len(client.calls) <= 2
    assert len(rows) <= 8
    assert sum(len(prompt) + len(json.dumps(payload, ensure_ascii=False)) for prompt, payload in client.calls) <= 60000
    assert all("source" not in row.get("evidence", {}) for _, payload in client.calls for row in payload["skills"])
    assert all(0 <= row["recommendation_score"] <= 1 for row in rows)


def test_small_skill_set_skips_redundant_metadata_discovery(tmp_path):
    """A single already-indexed candidate only needs content review."""
    path = tmp_path / "SKILL.md"
    path.write_text("# UI design\nUse a compact layout.\n", encoding="utf-8")
    works = [{"key_work_id": "ui", "title": "UI design", "step_ids": []}]
    found = discover_local_skill_candidates(works, context_text="UI design", roots=[tmp_path])
    client = AcceptAllClient()

    rows = select_skill_candidates_with_ai(
        client, found.candidates, task_text="UI design", key_works=works,
        review_limit=1,
    )

    assert len(rows) == 1
    assert len(client.calls) == 1
    assert "Use a compact layout." in client.calls[0][1]["skills"][0]["source"]


def test_index_reuses_headers_and_updates_added_changed_deleted_files(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    root.mkdir()
    source = root / "SKILL.md"
    source.write_text("---\nname: spacing\ndescription: UI spacing\n---\nSet a spacing scale.", encoding="utf-8")
    cache = tmp_path / "index"
    calls = []
    reader = local._read_skill
    monkeypatch.setattr(local, "_read_skill", lambda path: (calls.append(path), reader(path))[1])
    first, errors, stats = indexed_skill_metadata([root], cache_dir=cache)
    assert not errors and stats["metadata_reads"] == 1
    again, errors, stats = indexed_skill_metadata([root], cache_dir=cache)
    assert first == again and stats["cache_hits"] == 1 and len(calls) == 1
    source.write_text(source.read_text(encoding="utf-8") + "New layout rule.", encoding="utf-8")
    added = root / "new"
    added.mkdir()
    (added / "SKILL.md").write_text("# Typography\nFonts and sizes.", encoding="utf-8")
    rows, errors, stats = indexed_skill_metadata([root], cache_dir=cache)
    assert stats["metadata_reads"] == 2 and rows[0]["digest"] != first[0]["digest"]
    source.unlink()
    rows, errors, stats = indexed_skill_metadata([root], cache_dir=cache)
    assert len(rows) == 1 and stats["removed_files"] == 1 and stats["metadata_reads"] == 0


def test_corrupt_or_readonly_index_does_not_disable_search(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    (root / "SKILL.md").write_text("# Layout\nUI design.", encoding="utf-8")
    cache = tmp_path / "cache"
    indexed_skill_metadata([root], cache_dir=cache)
    next(cache.glob("*.json")).write_text("broken", encoding="utf-8")
    rows, errors, stats = indexed_skill_metadata([root], cache_dir=cache)
    assert len(rows) == 1 and stats["metadata_reads"] == 1
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    rows, errors, stats = indexed_skill_metadata([root], cache_dir=blocked)
    assert len(rows) == 1 and errors


def test_deleted_candidate_does_not_discard_remaining_indexed_results(tmp_path, monkeypatch):
    for name in ("gone", "kept"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "SKILL.md").write_text(f"# {name}\nUI design.", encoding="utf-8")
    indexed_skill_metadata([tmp_path])
    reader = local._read_skill

    def remove_after_read(path):
        value = reader(path)
        if path.parent.name == "gone":
            path.unlink()
        return value

    monkeypatch.setattr(local, "_read_skill", remove_after_read)
    result = discover_local_skill_candidates([{"key_work_id": "ui", "title": "UI design"}], roots=[tmp_path])
    assert len(result.candidates) == 1 and result.candidates[0]["name"] == "kept"
    assert result.errors


def test_long_skills_are_labelled_excerpts_and_scores_are_capped(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("# UI design\n" + "Layout and fonts.\n" * 500, encoding="utf-8")
    works = [{"key_work_id": "ui", "title": "UI design"}]
    found = discover_local_skill_candidates(works, roots=[tmp_path])
    client = AcceptAllClient()
    rows = select_skill_candidates_with_ai(client, found.candidates, task_text="UI design", key_works=works)
    assert rows[0]["evidence_level"] == "skill_excerpt"
    assert rows[0]["recommendation_score"] <= .85
    assert "节选" in rows[0]["ai_evidence_note"]
    assert "未阅读全文" in "".join(rows[0]["evidence_limitations"])


def test_name_metadata_ranking_keeps_requested_ui_facets_and_penalizes_music():
    names = ["theming-system", "typography-scale", "spacing-system", "visual-hierarchy", "music-composition", "deployment"]
    rows = [{"candidate_id": str(index), "skill_id": name, "name": name,
             "description": "Design helpful software workflows.", "key_work_id": "ui"} for index, name in enumerate(names)]
    picked = shortlist_candidates(rows, task_text="Tkinter 界面配色、字体、留白和层级设计", key_works=[{"key_work_id": "ui"}], limit=4)
    assert {row["name"] for row in picked} == set(names[:4])


def test_broad_design_skills_do_not_crowd_out_named_task_facets():
    names = ["theming-system", "typography-scale", "spacing-system", "visual-hierarchy", "redesign-existing-projects"]
    rows = [{"candidate_id": name, "name": name, "description": "Design.", "key_work_id": "ui"} for name in names]
    rows += [{"candidate_id": f"general-{n}", "name": f"ui-design-{n}",
              "description": "UI interface design refactor layout typography color visual workflow.", "key_work_id": "ui"} for n in range(20)]
    picked = shortlist_candidates(rows, task_text="Tkinter 界面配色、字体、留白、层级设计和重构",
                                  key_works=[{"key_work_id": "ui"}])
    assert set(names) <= {row["name"] for row in picked}
    assert len(picked) == 12


def test_excessive_task_budget_does_not_send_model_request(tmp_path):
    (tmp_path / "SKILL.md").write_text("# UI\nDesign layouts.", encoding="utf-8")
    works = [{"key_work_id": "ui", "title": "UI"}]
    found = discover_local_skill_candidates(works, roots=[tmp_path])
    client = AcceptAllClient()
    with pytest.raises(SkillAiSelectionError, match="预算"):
        select_skill_candidates_with_ai(client, found.candidates, task_text="long task " * 3000, key_works=works)
    assert not client.calls


def test_invalid_recommendation_score_is_rejected(tmp_path):
    (tmp_path / "SKILL.md").write_text("# UI\nDesign layouts.", encoding="utf-8")
    works = [{"key_work_id": "ui", "title": "UI"}]
    found = discover_local_skill_candidates(works, roots=[tmp_path])

    class BadScore( AcceptAllClient):
        def complete_json(self, prompt, payload, schema):
            result = super().complete_json(prompt, payload, schema)
            data = json.loads(result.content)
            for row in data.get("matches", []):
                row["recommendation_score"] = 1.2
            result.content = json.dumps(data)
            return result

    with pytest.raises(SkillAiSelectionError, match="推荐系数"):
        select_skill_candidates_with_ai(BadScore(), found.candidates, task_text="UI", key_works=works)


def test_custom_search_scales_excerpt_and_total_input_budget(tmp_path):
    for index in range(12):
        directory = tmp_path / f"ui-{index}"
        directory.mkdir()
        (directory / "SKILL.md").write_text(f"# UI {index}\n" + "UI instructions.\n"*900, encoding="utf-8")
    works = [{"key_work_id": "ui", "title": "UI design"}]
    found = discover_local_skill_candidates(works, context_text="UI design", roots=[tmp_path], max_candidates=10)
    assert len({row["local_snapshot_path"] for row in found.candidates}) <= 10
    client = AcceptAllClient()
    diagnostics = {}
    selected = select_skill_candidates_with_ai(client, found.candidates, task_text="UI design", key_works=works,
        shortlist_limit=6, review_limit=4, input_budget_chars=8000, excerpt_chars=500, diagnostics=diagnostics)
    assert len(client.calls) == 2
    assert len(client.calls[0][1]["skills"]) <= 6
    assert 0 < len(selected) <= 4
    assert all(len(row["source"]) <= 500 for row in client.calls[1][1]["skills"])
    cost = sum(len(prompt)+len(json.dumps(payload, ensure_ascii=False)) for prompt, payload in client.calls)
    assert cost <= 8000
    assert diagnostics["input_budget_chars"] == 8000
