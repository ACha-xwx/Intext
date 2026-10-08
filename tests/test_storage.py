from __future__ import annotations

import json

import pytest

from promptsmith.session import SessionState
from promptsmith.session import SessionStateError
from promptsmith.storage import load_session, save_session


def test_json_round_trip_preserves_state_and_excludes_secret(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("写一篇文章")
    session.runtime_api_key = "must-not-be-serialized"
    target = tmp_path / "session.json"

    save_session(session, target)
    raw = target.read_text(encoding="utf-8")
    loaded = load_session(target)

    assert loaded.task_id == session.task_id
    assert loaded.task_text == "写一篇文章"
    assert "must-not-be-serialized" not in raw
    assert "api_key" not in raw.lower()


def test_load_adds_defaults_for_older_session(tmp_path) -> None:
    target = tmp_path / "old.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "promptsmith.session.v0.1",
                "task_id": "task-old",
                "task_text": "旧文件",
                "requirements": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = load_session(target)

    assert loaded.task_id == "task-old"
    assert loaded.control["max_questions"] == 2
    assert loaded.pending_proposals == []
    assert loaded.plan["status"] == "not_started"


def test_save_is_valid_utf8_json(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("中文路径与内容")
    target = tmp_path / "中文会话.json"

    save_session(session, target)

    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["task_text"] == "中文路径与内容"


def test_long_text_round_trips_without_truncation(tmp_path) -> None:
    session = SessionState.new()
    session.set_task("长文本" * 20000)
    target = tmp_path / "long.json"

    save_session(session, target)

    assert load_session(target).task_text == session.task_text


def test_failed_replace_keeps_old_session_and_removes_partial_file(tmp_path, monkeypatch) -> None:
    import promptsmith.storage as storage_module

    target = tmp_path / "session.json"
    target.write_text("old session", encoding="utf-8")
    session = SessionState.new()
    session.set_task("new session")

    def fail_replace(_source, _target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(storage_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        save_session(session, target)

    assert target.read_text(encoding="utf-8") == "old session"
    assert not target.with_name(f".{target.name}.tmp").exists()


def test_unknown_future_session_schema_is_rejected(tmp_path) -> None:
    target = tmp_path / "future.json"
    target.write_text(
        json.dumps({"schema_version": "promptsmith.session.v999", "task_text": "未来格式"}),
        encoding="utf-8",
    )

    with pytest.raises(SessionStateError, match="不支持"):
        load_session(target)
