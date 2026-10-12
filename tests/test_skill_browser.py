"""Offline coverage for cumulative search and the shared Skill comparison table."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from promptsmith.skill_browser import table_rows, visible_rows
from promptsmith.skill_search import merge_candidates, SkillSearchResult
from promptsmith.storage import save_session, load_session
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from tests.test_ui_skill_search import _local_candidate, _remote_candidate


def candidate(name, origin="local_file", score=.2):
    row = _remote_candidate(name) if origin == "remote" else _local_candidate(name)
    row.update(skill_id=name, name=name, origin=origin, recommendation_score=score,
               key_work_id="k1", step_ids=["s1"])
    row["record_snapshot"].update(skill_id=name, name=name, origin=origin)
    return row


def binding(row, identifier="binding-local"):
    saved = deepcopy(row)
    saved.pop("candidate_id")
    saved["binding_id"] = identifier
    return saved


def test_high_scoring_network_results_do_not_hide_local_source_or_selected_item():
    rows = [candidate("local", score=.1)] + [candidate(f"remote-{i}", "remote", .9) for i in range(9)]
    picked = candidate("picked", score=.01)
    rows.append(picked)
    before = deepcopy(rows)
    shown = visible_rows(table_rows(rows, [binding(picked)]), limit=6)
    assert {row["candidate_id"] for row in shown} >= {"local", "picked"}
    assert any(row["origin"] == "remote" for row in shown)
    assert rows == before


@pytest.mark.parametrize("source,expected", [("本地", {"local"}), ("联网", {"remote"}),
    ("内置", {"built-in"}), ("已选", {"local"}), ("全部来源", {"local", "remote", "built-in"})])
def test_filters_are_projections_not_business_edits(source, expected):
    rows = [candidate("local"), candidate("remote", "remote"), candidate("built-in", "local")]
    before = deepcopy(rows)
    assert {r["skill_id"] for r in visible_rows(table_rows(rows, [binding(rows[0])]), source=source)} == expected
    assert rows == before


def test_saved_binding_without_candidate_remains_visible_and_cancellable():
    saved = binding(candidate("old"))
    rows = table_rows([], [saved])
    assert rows[0]["_binding_only"]
    assert rows[0]["_binding_ids"] == [saved["binding_id"]]
    assert not rows[0]["selection_allowed"]
    assert visible_rows(rows, source="已选") == rows


def test_repeated_search_refreshes_duplicate_and_preserves_other_source():
    local, remote = candidate("local"), candidate("remote", "remote")
    first = merge_candidates([local], [remote], catalog_hash="first")
    refreshed = deepcopy(remote)
    refreshed.update(candidate_id="remote-new", recommendation_score=.95)
    second = merge_candidates(first["result"]["candidates"], [refreshed], catalog_hash="second")
    assert len(second["result"]["candidates"]) == 2
    assert {r["candidate_id"] for r in second["result"]["candidates"]} == {"local", "remote-new"}
    assert merge_candidates(second["result"]["candidates"], [], catalog_hash="empty")["result"]["candidates"] == second["result"]["candidates"]


@pytest.fixture
def browser_app(app, monkeypatch):
    install_session(app, confirmed_plan_session())
    monkeypatch.setattr(app, "_refresh_selected_catalog", lambda: True)
    return app


def set_rows(app, rows, bindings=None):
    app.session.set_skill_state(status="selected" if bindings else "candidates_ready", basis=app._delivery_basis(),
        candidate_batch={"catalog_hash": "a" * 64, "result": {"candidates": rows}}, bindings=bindings or [])
    app.refresh()


def request(app, kind):
    result = {"kind": kind, "basis": deepcopy(app._delivery_basis()), "session_token": app._session_instance_token}
    app._skill_search_busy = True
    app._skill_search_request = result
    return result


def network(app, rows):
    app._network_skill_search_ok(request(app, "network"), SkillSearchResult(
        query="fixture", status="ok" if rows else "no_match", candidates=rows,
        batch_id="remote", catalog_hash="b" * 64))


def test_searches_accumulate_in_both_directions_and_keep_selection(browser_app):
    app = browser_app
    local = candidate("local")
    set_rows(app, [local], [binding(local)])
    remote = candidate("remote", "remote", .9)
    network(app, [remote])
    assert app.session.skill_state["status"] == "selected"
    second_local = candidate("second-local")
    files = SimpleNamespace(scanned_files=2, to_dict=lambda: {
        "catalog_hash": "c" * 64, "result": {"candidates": [second_local]}})
    app._local_skill_search_ok(request(app, "local"),
        (files, [second_local], [], [second_local], "completed", None, None))
    assert {r["skill_id"] for r in app._candidate_rows()} == {"local", "remote", "second-local"}
    assert app.session.skill_state["status"] == "selected"
    assert app.session.skill_state["bindings"][0]["binding_id"] == "binding-local"
    assert str(app._conversation_buttons["integrate"].cget("state")) == "normal"
    network(app, [])
    assert len(app._candidate_rows()) == 3


def test_inline_table_bulk_selection_details_filters_and_cancel(browser_app):
    app = browser_app
    local, remote = candidate("local"), candidate("remote", "remote", .9)
    local["match_reason"] = "核对布局和元素样式"
    set_rows(app, [local, remote])
    before = deepcopy(app.session.to_dict())
    app.skill_source_filter_var.set("本地")
    app._skill_browser_filter_changed()
    assert app.widgets["conversation_skill_candidates_tree"].get_children() == ("local",)
    assert app.session.to_dict() == before
    app.skill_source_filter_var.set("全部来源")
    app._skill_browser_filter_changed()
    tree = app.widgets["conversation_skill_candidates_tree"]
    tree.selection_set("local")
    app.root.update()
    assert "核对布局" in app.widgets["conversation_skill_details_text"].get("1.0", "end")
    tree.selection_set("local", "remote")
    app.root.update()
    app._conversation_buttons["select_skills"].invoke()
    assert len(app.session.skill_state["bindings"]) == 2
    assert set(app.widgets["conversation_skill_candidates_tree"].selection()) == {"local", "remote"}
    app._conversation_buttons["cancel_skills"].invoke()
    assert not app.session.skill_state["bindings"]


def test_low_rank_selected_rows_and_binding_only_rows_survive_save_reopen(browser_app, tmp_path):
    app = browser_app
    rows = [candidate(f"row-{i}", score=i / 10) for i in range(10)]
    bindings = [binding(rows[0]), binding(candidate("binding-only"), "other")]
    set_rows(app, rows, bindings)
    path = save_session(app.session, tmp_path / "skills.json")
    install_session(app, load_session(path))
    tree = app.widgets["conversation_skill_candidates_tree"]
    assert tree.exists("row-0") and tree.exists("selected:other")
    tree.selection_set("selected:other")
    app.root.update()
    assert str(app._conversation_buttons["select_skills"].cget("state")) == "disabled"
    app._conversation_buttons["cancel_skills"].invoke()
    assert len(app.session.skill_state["bindings"]) == 1


def test_stale_search_callback_cannot_merge_into_new_conversation(browser_app):
    app = browser_app
    set_rows(app, [candidate("local")])
    pending = request(app, "network")
    app.new_session()
    before = deepcopy(app.session.to_dict())
    app._network_skill_search_ok(pending, SkillSearchResult(query="fixture", status="ok",
        candidates=[candidate("late", "remote")], batch_id="late", catalog_hash="d" * 64))
    assert app.session.to_dict() == before
    assert app.skill_source_filter_var.get() == "全部来源"


@pytest.mark.parametrize("prefix", ["skill", "conversation_skill"])
def test_select_button_marks_selected_disables_and_cancel_restores(browser_app, prefix):
    app = browser_app
    set_rows(app, [candidate("local")])
    select_key = "skill_select_button" if prefix == "skill" else prefix + "_select_skills"
    cancel_key = "skill_cancel_button" if prefix == "skill" else prefix + "_cancel_skills"
    app.widgets[prefix + "_candidates_tree"].selection_set("local")
    app.root.update()
    assert str(app.widgets[select_key].cget("state")) == "normal"
    assert app.widgets[select_key].cget("text") == "选用此 Skill"
    app.widgets[select_key].invoke()
    app.root.update()
    assert len(app.session.skill_state["bindings"]) == 1
    assert str(app.widgets[select_key].cget("state")) == "disabled"
    assert app.widgets[select_key].cget("text") == "已选中该 Skill"
    before = deepcopy(app.session.to_dict())
    app.widgets[select_key].invoke()
    assert app.session.to_dict() == before
    app.widgets[cancel_key].invoke()
    app.root.update()
    assert not app.session.skill_state["bindings"]
    assert str(app.widgets[select_key].cget("state")) == "normal"
    assert app.widgets[select_key].cget("text") == "选用此 Skill"


def test_duplicate_selection_preserves_delivery_and_records_debug(browser_app, caplog):
    from tests.test_ui_delivery_interactions import _candidate

    app = browser_app
    valid_candidate, _ = _candidate(candidate_id="local")
    set_rows(app, [valid_candidate])
    app.select_skill_candidates(["local"])
    app.generate_no_skill_final()
    assert app.session.final_result["canonical_body"]
    before = deepcopy(app.session.to_dict())
    with caplog.at_level("DEBUG", logger="promptsmith.ui"):
        app.select_skill_candidates(["local"])
    assert app.session.to_dict() == before
    assert "Duplicate Skill selection ignored" in caplog.text


@pytest.mark.parametrize("prefix", ["skill", "conversation_skill"])
def test_selected_buttons_survive_reopen_refresh_and_mixed_selection(browser_app, tmp_path, prefix):
    app = browser_app
    local, remote = candidate("local"), candidate("remote", "remote", .9)
    set_rows(app, [local, remote], [binding(local)])
    saved = save_session(app.session, tmp_path / "selected.json")
    install_session(app, load_session(saved))
    select_key = "skill_select_button" if prefix == "skill" else prefix + "_select_skills"
    app.widgets[prefix + "_candidates_tree"].selection_set("local")
    app.root.update()
    app.refresh()
    app.root.update()
    assert str(app.widgets[select_key].cget("state")) == "disabled"
    assert app.widgets[select_key].cget("text") == "已选中该 Skill"
    app.widgets[prefix + "_candidates_tree"].selection_set("local", "remote")
    app.root.update()
    assert str(app.widgets[select_key].cget("state")) == "normal"
    app.widgets[select_key].invoke()
    app.root.update()
    assert len(app.session.skill_state["bindings"]) == 2
    assert str(app.widgets[select_key].cget("state")) == "disabled"
    assert app.widgets[select_key].cget("text") == "所选 Skill 均已选中"


def test_changed_source_snapshot_blocks_duplicate_but_other_work_is_selectable(browser_app):
    app = browser_app
    original = candidate("local")
    changed = deepcopy(original)
    changed["record_hash"] = "e" * 64
    changed["record_snapshot"]["record_hash"] = "e" * 64
    other_work = deepcopy(changed)
    other_work.update(candidate_id="other-work", key_work_id="k2")
    projected = table_rows([changed, other_work], [binding(original)])
    assert next(row for row in projected if row["candidate_id"] == "other-work")["_already_selected"] is False
    set_rows(app, [changed], [binding(original)])
    tree = app.widgets["conversation_skill_candidates_tree"]
    tree.selection_set("local")
    app.root.update()
    assert str(app._conversation_buttons["select_skills"].cget("state")) == "disabled"
    assert app._conversation_buttons["select_skills"].cget("text") == "已选中该 Skill"
    assert "其他来源或版本" in app.widgets["conversation_skill_details_text"].get("1.0", "end")
    tree.selection_set("selected:binding-local")
    app.root.update()
    app._conversation_buttons["cancel_skills"].invoke()
    app.root.update()
    app.widgets["conversation_skill_candidates_tree"].selection_set("local")
    app.root.update()
    assert str(app._conversation_buttons["select_skills"].cget("state")) == "normal"
