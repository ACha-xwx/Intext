from __future__ import annotations

import time
import tkinter as tk
import json
from io import BytesIO
from threading import Event
from types import SimpleNamespace

import pytest

import promptsmith.ui as ui_module
from promptsmith.skill_catalog import CatalogMatch, SkillCatalogError
from promptsmith.finalization import build_final_draft
from promptsmith.local_skill_search import LocalSkillSearchResult, discover_local_skill_candidates
from promptsmith.skill_search import SkillSearchResult, search_online_skills
from promptsmith.ui import PromptSmithApp
from test_final_delivery import confirmed_plan_session


def _pump_until(window: tk.Misc, predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window.update()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Skill search callback did not complete within timeout.")


@pytest.fixture
def skill_app(tk_root, tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPTSMITH_SKILL_SEARCH_URL", raising=False)
    window = tk.Toplevel(tk_root)
    window.withdraw()
    app = PromptSmithApp(window, session=confirmed_plan_session(), evidence_root=tmp_path)
    app.api_key_var.set("offline-test-key")
    app.confirm_model_settings()
    monkeypatch.setattr(app, "_client", lambda _config: object())

    def catalog_discovery(works, **kwargs):
        catalog = ui_module.SkillCatalog.load(app._catalog_path, source_root=ui_module.resource_root())
        match = catalog.match(works, context_text=kwargs.get("context_text"))
        return LocalSkillSearchResult(
            status=match.status, candidates=match.candidates,
            catalog_hash=catalog.snapshot_hash, scanned_count=len(match.candidates),
            errors=[], batch_id="legacy-catalog-test",
        )

    monkeypatch.setattr(ui_module, "discover_local_skill_candidates", catalog_discovery)
    monkeypatch.setattr(ui_module, "select_skill_candidates_with_ai", lambda client, rows, **kwargs: rows)
    monkeypatch.setattr(
        ui_module,
        "search_network_skill_candidates",
        lambda works, **kwargs: ui_module.search_online_skills(
            works, context_text=kwargs["task_text"], token=kwargs.get("token"),
            timeout_seconds=kwargs.get("timeout_seconds", 45.0),
            opener=kwargs.get("opener"), search_url=kwargs["search_url"],
        ),
    )
    yield app, window
    app.shutdown(wait=True)
    window.destroy()


def _local_candidate(candidate_id: str = "local-candidate") -> dict:
    return {
        "candidate_id": candidate_id,
        "skill_id": "local-skill",
        "key_work_id": "k0",
        "record_hash": "a" * 64,
        "record_snapshot": {
            "skill_id": "local-skill",
            "name": "local Skill",
            "origin": "local",
            "verification": {"verification_status": "verified"},
        },
        "step_ids": ["s0"],
        "capability_ids": ["local-capability"],
        "usage_mode": "method_adaptation",
        "method_adaptation_allowed": True,
        "adaptation_prerequisite_ids": [],
        "limitations": [],
        "compatibility": "compatible",
        "selection_allowed": True,
        "origin": "local",
        "source_kind": "local",
            "name": "local Skill",
            "description": "local candidate",
    }


def _remote_candidate(candidate_id: str = "remote-candidate") -> dict:
    return {
        "candidate_id": candidate_id,
        "skill_id": "github:example/remote-skill:SKILL.md",
        "key_work_id": "k0",
        "record_hash": "b" * 64,
        "record_snapshot": {
            "skill_id": "github:example/remote-skill:SKILL.md",
            "name": "remote Skill",
            "origin": "remote",
            "source_url": "https://github.com/example/remote-skill",
            "verification": {"verification_status": "network_unverified"},
        },
        "step_ids": [],
        "capability_ids": ["remote-capability"],
        "usage_mode": "method_adaptation",
        "method_adaptation_allowed": True,
        "adaptation_prerequisite_ids": ["remote-source-review"],
        "limitations": ["Remote candidate is not installed or executed."],
        "compatibility": "compatible",
        "selection_allowed": True,
        "origin": "remote",
        "source_kind": "github",
        "name": "remote Skill",
        "description": "remote candidate",
        "source_url": "https://github.com/example/remote-skill",
    }


class _FakeCatalog:
    catalog_id = "local"
    catalog_version = "v-test"
    snapshot_hash = "c" * 64

    def __init__(self, result: CatalogMatch):
        self.result = result
        self.entered: Event | None = None
        self.release: Event | None = None

    def match(self, *_args, **_kwargs):
        if self.entered:
            self.entered.set()
        if self.release:
            self.release.wait(timeout=3)
        return self.result

    def assess_bindings(self, _bindings):
        return {"status": "current", "reasons": []}


def _set_local_loader(monkeypatch, fake: _FakeCatalog) -> None:
    monkeypatch.setattr(ui_module.SkillCatalog, "load", lambda *args, **kwargs: fake)


def _search_state(app: PromptSmithApp) -> dict:
    return app.session.skill_state["search_state"]


def _network_button(app: PromptSmithApp):
    for name in ("skill_network_button", "skill_online_button", "skill_web_button"):
        if name in app.widgets:
            return app.widgets[name]
    raise AssertionError("Skill page did not register a network search button.")


def test_skill_candidates_are_visible_and_selectable_in_real_window(skill_app):
    app, window = skill_app
    candidate = _local_candidate()
    app.session.set_skill_state(
        status="candidates_ready",
        basis=app._delivery_basis(),
        candidate_batch={
            "batch_id": "visible-candidates",
            "catalog_hash": "a" * 64,
            "result": {"candidates": [candidate]},
        },
        bindings=[],
    )
    app.refresh()
    window.deiconify()
    app.notebook.select(2)
    window.update()

    tree = app.widgets["skill_candidates_tree"]
    assert tree.get_children() == (candidate["candidate_id"],)
    assert tree.winfo_ismapped()
    assert tree.winfo_height() >= 100
    assert tuple(tree["columns"]) == ("status", "skill", "source", "score", "reason", "work")
    assert tree.heading("score")["text"] == "推荐系数"
    assert tree.heading("skill")["text"] == "Agent Skill"
    assert tree.item(candidate["candidate_id"], "values")[:5] == (
        "可选", "local Skill", "内置目录", "0.00", "local candidate"
    )

    tree.selection_set(candidate["candidate_id"])
    app.select_skill_candidates()
    assert [row["skill_id"] for row in app.session.skill_state["bindings"]] == ["local-skill"]


def test_recommendations_are_sorted_and_more_candidates_can_be_expanded(skill_app):
    app, window = skill_app
    candidates = []
    for index in range(10):
        row = _local_candidate(f"ranked-{index}")
        row["name"] = f"候选 {index}"
        row["recommendation_score"] = index / 10
        candidates.append(row)
    app.session.set_skill_state(status="candidates_ready", basis=app._delivery_basis(),
                                candidate_batch={"batch_id": "ranked", "catalog_hash": "a" * 64,
                                                 "result": {"candidates": candidates}}, bindings=[])
    app.refresh()
    tree = app.widgets["skill_candidates_tree"]
    assert tree.get_children() == tuple(f"ranked-{i}" for i in range(9, 3, -1))
    assert tree.item("ranked-9", "values")[3] == "0.90"
    inline_tree = app.widgets["conversation_skill_candidates_tree"]
    assert inline_tree.exists("ranked-9")
    assert not inline_tree.exists("ranked-0")
    app.widgets["conversation_skill_show_all"].invoke()
    assert app.show_all_skills_var.get()
    assert len(tree.get_children()) == 10
    assert app.widgets["conversation_skill_candidates_tree"].exists("ranked-0")
    app.widgets["conversation_skill_show_all"].invoke()
    assert len(tree.get_children()) == 6


def test_skill_toolbar_shows_only_search_and_selection_actions(skill_app):
    app, window = skill_app
    window.deiconify()
    app.notebook.select(2)
    window.update()

    for name in ("skill_find_button", "skill_online_button", "skill_select_button",
                 "skill_cancel_button", "skill_skip_button"):
        assert app.widgets[name].winfo_ismapped(), name
    assert app.widgets["skill_search_url_entry"].winfo_ismapped()
    assert "可选" in app.widgets["skill_search_url_label"].cget("text")
    assert app.skill_search_url_var.get() == app.preferences["skill_search_url"]
    for name in ("skill_analyze_button", "skill_integrate_button"):
        assert not app.widgets[name].winfo_ismapped(), name


def test_local_skill_search_reports_running_then_completion_and_enables_network(
    skill_app, monkeypatch
):
    app, window = skill_app
    entered = Event()
    release = Event()
    fake = _FakeCatalog(CatalogMatch("ok", [_local_candidate()], []))
    fake.entered = entered
    fake.release = release
    _set_local_loader(monkeypatch, fake)

    network_button = _network_button(app)
    assert str(network_button.cget("state")) == "disabled"

    app.find_skills()
    assert "\u6b63\u5728\u67e5\u627e\u672c\u5730 Skill" in app.skill_status_var.get()
    assert _search_state(app)["status"] == "local_running"
    assert str(network_button.cget("state")) == "disabled"
    assert entered.wait(timeout=1)

    release.set()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")
    assert "\u672c\u5730" in app.skill_status_var.get() and "1" in app.skill_status_var.get()
    assert str(network_button.cget("state")) == "normal"
    assert app._candidate_rows()[0]["origin"] == "local"


def test_local_search_keeps_catalog_candidates_when_model_is_not_configured(
    skill_app, monkeypatch
):
    app, window = skill_app
    app.api_key_var.set("")
    app.session.plan["content"]["key_work"][0].update({
        "title": "为活动报名软件系统整理需求规格和用户故事",
        "goal": "将已确认的软件需求整理为可验证的规格文档",
    })
    monkeypatch.setattr(
        ui_module,
        "discover_local_skill_candidates",
        lambda _works, **_kwargs: LocalSkillSearchResult(
            status="empty", candidates=[], catalog_hash="", scanned_count=0, errors=[]
        ),
    )

    app.find_skills()
    _pump_until(window, lambda: not app._skill_search_busy)

    candidate = next(row for row in app._candidate_rows() if row["skill_id"] == "to-spec")
    assert candidate["ai_review_status"] == "unavailable"
    assert "模型" in app.skill_status_var.get()
    assert app.session.skill_state["search_state"]["status"] == "local_done"


def test_network_search_is_explicit_merges_candidates_and_renders_source(
    skill_app, monkeypatch
):
    app, window = skill_app
    local = _FakeCatalog(CatalogMatch("ok", [_local_candidate()], []))
    _set_local_loader(monkeypatch, local)
    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")

    remote = _remote_candidate()
    called = []

    def fake_network(*args, **kwargs):
        called.append((args, kwargs))
        return SkillSearchResult(
            query="skill python",
            status="ok",
            candidates=[remote],
            batch_id="network-batch",
            catalog_hash="d" * 64,
        )

    monkeypatch.setattr(ui_module, "search_online_skills", fake_network)
    button = _network_button(app)
    button.invoke()
    assert "\u8054\u7f51\u641c\u7d22" in app.skill_status_var.get()
    assert _search_state(app)["status"] == "network_running"

    _pump_until(window, lambda: _search_state(app)["status"] == "network_done")
    assert called
    rows = app._candidate_rows()
    assert {row["origin"] for row in rows} == {"local", "remote"}
    assert "\u8054\u7f51\u641c\u7d22\u5b8c\u6210" in app.skill_status_var.get()
    assert "source" in tuple(app.widgets["skill_candidates_tree"]["columns"])
    assert any("github.com" in value for value in app.widgets["skill_candidates_tree"].item("remote-candidate", "values"))

    app.widgets["skill_candidates_tree"].selection_set("local-candidate", "remote-candidate")
    app.select_skill_candidates()
    bindings = app.session.skill_state["bindings"]
    assert {row["record_snapshot"]["origin"] for row in bindings} == {"local", "remote"}
    remote_binding = next(row for row in bindings if row["origin"] == "remote")
    assert remote_binding["step_ids"] == []
    assert remote_binding["precondition_assessments"][0]["source"] == "remote_source_review"
    local_binding = next(row for row in bindings if row["origin"] == "local")
    assert local_binding["step_ids"] == ["s0"]


def test_network_search_preserves_bindings_selected_from_local_results(skill_app, monkeypatch):
    app, window = skill_app
    local = _FakeCatalog(CatalogMatch("ok", [_local_candidate()], []))
    _set_local_loader(monkeypatch, local)
    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")

    app.widgets["skill_candidates_tree"].selection_set("local-candidate")
    app.select_skill_candidates()
    assert [row["skill_id"] for row in app.session.skill_state["bindings"]] == ["local-skill"]

    monkeypatch.setattr(
        ui_module,
        "search_online_skills",
        lambda *_args, **_kwargs: SkillSearchResult(
            query="skill",
            status="ok",
            candidates=[_remote_candidate()],
            batch_id="network-binding-preservation",
            catalog_hash="d" * 64,
        ),
    )
    _network_button(app).invoke()
    _pump_until(window, lambda: _search_state(app)["status"] == "network_done")

    assert [row["skill_id"] for row in app.session.skill_state["bindings"]] == ["local-skill"]


def test_verified_online_candidate_can_be_selected_and_used_in_final_draft(skill_app, monkeypatch):
    app, window = skill_app
    _set_local_loader(monkeypatch, _FakeCatalog(CatalogMatch("no_match", [], [])))
    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")

    source_url = "https://skills.example.test/python-teaching/SKILL.md"
    source = (
        b"---\nname: python-teaching\n"
        b"description: Teaching Python lessons for beginners.\n---\n"
        b"Plan lessons and exercises.\n"
    )

    def fetch(request, timeout):
        assert timeout > 0
        url = request.full_url
        if url.startswith("https://skills.sh/api/search?"):
            return BytesIO(json.dumps({"skills": [{"url": source_url}]}).encode("utf-8"))
        if url.startswith("https://api.github.com/search/repositories?"):
            return BytesIO(b'{"items": []}')
        if url == source_url:
            return BytesIO(source)
        raise AssertionError(url)

    monkeypatch.setattr(
        ui_module,
        "search_online_skills",
        lambda works, **kwargs: search_online_skills(works, **{**kwargs, "opener": fetch}),
    )
    app.search_online_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "network_done")

    candidate = next(row for row in app._candidate_rows() if row["origin"] == "remote")
    app.widgets["skill_candidates_tree"].selection_set(candidate["candidate_id"])
    app.select_skill_candidates()
    binding = app.session.skill_state["bindings"][0]
    assert binding["precondition_assessments"][0]["prerequisite_id"] == "remote-source-review"
    assert binding["record_snapshot"]["adaptation_prerequisites"][0]["prerequisite_id"] == "remote-source-review"

    draft = build_final_draft(app.session, selected_contributions=[{
        "binding_id": binding["binding_id"],
        "origin_binding_ids": [binding["binding_id"]],
        "step_id": binding["step_ids"][0],
        "method_actions": ["按学习目标安排课程。"],
        "planned_inputs": ["已确认的学习目标"],
        "expected_outputs": ["课程计划"],
        "checkpoints": ["逐项核对学习目标"],
        "prerequisite_ids": ["remote-source-review"],
        "fallback_actions": ["来源尚未核对时沿用原方案。"],
    }])
    assert draft["status"] == "draft"
    assert draft["content"]["skill_contributions"][0]["provenance"]["source_read"] is True


def test_network_request_keeps_request_id_separate_from_github_token(skill_app, monkeypatch):
    app, _window = skill_app
    local = _FakeCatalog(CatalogMatch("ok", [_local_candidate()], []))
    _set_local_loader(monkeypatch, local)
    app.find_skills()
    # Avoid waiting for the worker: the request object is the contract under test.
    for _ in range(100):
        app.root.update()
        if _search_state(app)["status"] == "local_done":
            break
        time.sleep(0.01)

    app.skill_search_token = "github-secret"
    submitted = {}

    def capture_submit(operation, success, error):
        submitted["operation"] = operation
        submitted["success"] = success
        submitted["error"] = error

    monkeypatch.setattr(app, "_submit", capture_submit)
    app.search_online_skills()

    request = app._skill_search_request
    assert request is not None
    assert request["request_id"] != "github-secret"
    assert request["github_token"] == "github-secret"
    assert request["request_id"]
    assert request["timeout_seconds"] == 45.0


def test_local_search_failure_keeps_old_candidates_and_can_retry(skill_app, monkeypatch):
    app, window = skill_app
    old = _local_candidate("old-candidate")
    app.session.set_skill_state(
        status="candidates_ready",
        basis=app._delivery_basis(),
        candidate_batch={"batch_id": "old", "catalog_hash": "e" * 64, "result": {"candidates": [old]}},
        bindings=[],
    )
    app.refresh()
    monkeypatch.setattr(
        ui_module.SkillCatalog,
        "load",
        lambda *args, **kwargs: (_ for _ in ()).throw(SkillCatalogError("catalog unavailable")),
    )

    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "error")
    assert app._candidate_rows() == [old]
    assert "\u5931\u8d25" in app.skill_status_var.get()
    assert "\u91cd\u8bd5" in app.skill_status_var.get()
    assert str(app.widgets["skill_find_button"].cget("state")) == "normal"


def test_network_failure_preserves_local_candidates_and_allows_network_retry(
    skill_app, monkeypatch
):
    app, window = skill_app
    local = _FakeCatalog(CatalogMatch("ok", [_local_candidate()], []))
    _set_local_loader(monkeypatch, local)
    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")
    button = _network_button(app)
    calls = 0

    def network_search(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary network error")
        return SkillSearchResult(
            query="skill python",
            status="ok",
            candidates=[_remote_candidate()],
            batch_id="network-retry-batch",
            catalog_hash="d" * 64,
        )

    monkeypatch.setattr(ui_module, "search_online_skills", network_search)
    button.invoke()
    _pump_until(window, lambda: _search_state(app)["status"] == "error")
    assert [row["origin"] for row in app._candidate_rows()] == ["local"]
    assert "\u5931\u8d25" in app.skill_status_var.get()
    assert str(button.cget("state")) == "normal"

    button.invoke()
    _pump_until(window, lambda: _search_state(app)["status"] == "network_done")
    assert calls == 2
    assert {row["origin"] for row in app._candidate_rows()} == {"local", "remote"}


def test_network_zero_candidates_with_source_error_is_not_reported_as_no_match(skill_app, monkeypatch):
    app, window = skill_app
    _set_local_loader(monkeypatch, _FakeCatalog(CatalogMatch("ok", [_local_candidate()], [])))
    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")
    monkeypatch.setattr(
        ui_module,
        "search_online_skills",
        lambda *_args, **_kwargs: SkillSearchResult(
            query="testing", status="no_match", candidates=[], batch_id="network-failed",
            catalog_hash="d" * 64,
            error={"kind": "network", "message": "Skill 来源访问超时"},
        ),
    )

    _network_button(app).invoke()
    _pump_until(window, lambda: _search_state(app)["status"] == "error")

    assert [row["origin"] for row in app._candidate_rows()] == ["local"]
    assert "Skill 来源访问超时" in app.skill_status_var.get()
    assert str(_network_button(app).cget("state")) == "normal"


def test_late_local_result_is_discarded_when_plan_basis_changes(skill_app, monkeypatch):
    app, window = skill_app
    old = _local_candidate("old-candidate")
    app.session.set_skill_state(
        status="candidates_ready",
        basis=app._delivery_basis(),
        candidate_batch={"batch_id": "old", "catalog_hash": "e" * 64, "result": {"candidates": [old]}},
        bindings=[],
    )
    app.refresh()
    entered = Event()
    release = Event()
    fake = _FakeCatalog(CatalogMatch("ok", [_local_candidate("late-candidate")], []))
    fake.entered = entered
    fake.release = release
    _set_local_loader(monkeypatch, fake)

    app.find_skills()
    assert entered.wait(timeout=1)
    app.session.plan["plan_version"] += 1
    release.set()
    _pump_until(window, lambda: _search_state(app)["status"] != "local_running")

    assert [row["candidate_id"] for row in app._candidate_rows()] == ["old-candidate"]
    assert "\u8fdf\u5230" in app.skill_status_var.get() or "\u53d8\u5316" in app.skill_status_var.get()


def test_local_search_uses_skill_files_and_selected_source_is_rechecked(skill_app, monkeypatch, tmp_path):
    app, window = skill_app
    skill_dir = tmp_path / "skills" / "python-tutor"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: python-tutor\ndescription: Plan Python lessons for beginners.\n---\n"
        "# Python tutor\nCreate a beginner Python learning plan with exercises.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        ui_module,
        "discover_local_skill_candidates",
        lambda works, **kwargs: discover_local_skill_candidates(
            works, roots=[tmp_path / "skills"], **kwargs
        ),
    )

    app.find_skills()
    _pump_until(window, lambda: _search_state(app)["status"] == "local_done")
    rows = [row for row in app._candidate_rows() if row.get("origin") == "local_file"]
    assert rows
    assert rows[0]["source_path"] == str(skill_file.resolve())
    assert str(app.widgets["skill_find_button"].cget("state")) == "normal"

    app.widgets["skill_candidates_tree"].selection_set(rows[0]["candidate_id"])
    app.select_skill_candidates()
    assert app.session.skill_state["status"] == "selected"
    assert app._skill_basis_is_current()

    skill_file.write_text(skill_file.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8")
    assert not app._skill_basis_is_current()
    assert app.session.skill_state["status"] == "stale"
