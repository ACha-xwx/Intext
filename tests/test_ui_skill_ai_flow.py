import json
import time
import tkinter as tk
from types import SimpleNamespace

import promptsmith.ui as ui_module
from promptsmith.local_skill_search import discover_local_skill_candidates
from promptsmith.skill_search import SkillSearchResult
from promptsmith.ui import PromptSmithApp
from test_final_delivery import confirmed_plan_session


class Client:
    def complete_json(self, prompt, payload, schema):
        if schema.get("required") == ["candidate_ids"]:
            answer = {"candidate_ids": [row["candidate_id"] for row in payload["skills"]]}
        else:
            answer = {"matches": [
                {"candidate_id": row["candidate_id"], "key_work_id": "k0", "reason": "适合为初学者安排循序渐进的讲解。"}
                for row in payload["skills"]
            ]}
        return SimpleNamespace(content=json.dumps(answer, ensure_ascii=False))


def _pump(window, condition):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        window.update()
        if condition():
            return
        time.sleep(.01)
    raise AssertionError("Skill search did not finish")


def test_network_source_summary_shows_attempted_web_engines():
    summary = PromptSmithApp._network_source_summary({
        "open_web": {"status": "ok", "verified_count": 1, "search_engines": ["Bing", "DuckDuckGo"]},
    })

    assert "Bing" in summary
    assert "DuckDuckGo" in summary


def test_local_then_optional_network_candidates_are_visible_and_selectable(tk_root, tmp_path, monkeypatch):
    skill = tmp_path / "teaching" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: teaching\ndescription: Explain math clearly.\n---\nUse examples.\n", encoding="utf-8")
    monkeypatch.setattr(ui_module, "discover_local_skill_candidates", lambda works, **kw: discover_local_skill_candidates(works, roots=[tmp_path], **kw))
    window = tk.Toplevel(tk_root)
    app = PromptSmithApp(window, session=confirmed_plan_session(), evidence_root=tmp_path)
    try:
        app.api_key_var.set("offline-test-key")
        app.confirm_model_settings()
        monkeypatch.setattr(app, "_client", lambda config: Client())
        window.deiconify()
        app.notebook.select(2)
        app.find_skills()
        _pump(window, lambda: app.session.skill_state.get("search_state", {}).get("status") == "local_done")

        tree = app.widgets["skill_candidates_tree"]
        local = app._candidate_rows()[0]
        assert tree.winfo_ismapped() and tree.winfo_height() >= 100
        assert app.widgets["skill_search_url_entry"].winfo_ismapped()
        assert "可选" in app.widgets["skill_search_url_label"].cget("text")
        assert tree.get_children() == (local["candidate_id"],)
        assert "适合为初学者" in tree.item(local["candidate_id"], "values")[2]
        assert str(app.widgets["skill_online_button"].cget("state")) == "normal"

        remote = dict(local)
        remote.update({
            "candidate_id": "remote-1", "skill_id": "https://example.test/teaching/SKILL.md",
            "name": "remote teaching", "origin": "remote", "source_kind": "web",
            "source_url": "https://example.test/teaching/SKILL.md",
            "match_reason": "提供另一种直观讲解方式。",
        })
        remote["record_snapshot"] = dict(local["record_snapshot"], origin="remote", source_url=remote["source_url"])
        monkeypatch.setattr(ui_module, "search_network_skill_candidates", lambda *args, **kw: SkillSearchResult(
            "teaching", "ok", [remote], "web", "a" * 64,
            diagnostics={"errors": ["开放网页：DuckDuckGo 返回了验证页面"]},
        ))
        app.search_online_skills()
        _pump(window, lambda: app.session.skill_state.get("search_state", {}).get("status") == "network_done")

        assert {row["origin"] for row in app._candidate_rows()} == {"local_file", "remote"}
        assert "部分来源不可用" in app.skill_status_var.get()
        assert "example.test" in tree.item("remote-1", "values")[1]
        tree.selection_set(local["candidate_id"], "remote-1")
        app.select_skill_candidates()
        assert len(app.session.skill_state["bindings"]) == 2
    finally:
        app.shutdown(wait=True)
        window.destroy()
