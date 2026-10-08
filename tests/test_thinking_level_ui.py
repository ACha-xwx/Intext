from __future__ import annotations

import tkinter as tk

import pytest

from promptsmith.m1 import build_m1_input
from promptsmith.ui import PromptSmithApp


@pytest.fixture
def app(tk_root, tmp_path):
    root = tk.Toplevel(tk_root)
    root.withdraw()
    application = PromptSmithApp(root, evidence_root=tmp_path / "calls")
    yield application
    application.shutdown(wait=True)
    root.destroy()


def test_thinking_level_choice_is_plainly_selectable_and_reaches_m1(app) -> None:
    combo = app.widgets["thinking_level_combo"]
    labels = tuple(combo.cget("values"))
    assert labels == (
        "快速：先把基本任务说清",
        "标准：补齐常见关键信息",
        "深入：系统梳理复杂任务",
    )

    combo.set("深入：系统梳理复杂任务")
    combo.event_generate("<<ComboboxSelected>>")
    app.root.update_idletasks()

    assert app.session.control["thinking_level"] == "deep"
    assert "深入整理" in app.status_var.get()
    payload = build_m1_input(app.session, "thinking-level-test")
    assert payload["control"]["thinking_level"] == "deep"
    assert payload["control"]["thinking_policy"] == "coverage_based"


def test_thinking_level_defaults_to_standard_for_new_session(app) -> None:
    assert app.session.control["thinking_level"] == "standard"
    assert app.thinking_level_var.get() == "standard"
    assert app.thinking_level_display_var.get() == "标准：补齐常见关键信息"
