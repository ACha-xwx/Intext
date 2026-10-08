from __future__ import annotations

import sys
from pathlib import Path

from scripts.verify_exe_chain import verify_program


ROOT = Path(__file__).resolve().parents[1]


def test_source_release_chain_uses_http_and_persists_final_artifacts(tmp_path) -> None:
    result = verify_program(
        [sys.executable, str(ROOT / "run_promptsmith.py")],
        evidence_dir=tmp_path,
        timeout_seconds=30,
    )

    assert result["exit_code"] == 0
    assert result["http_purposes"] == ["m1", "m2"]
    assert result["task_input_only_before_click"]
    assert result["task_input_label"] == "开始整理"
    assert result["primary_button_started_m1"]
    assert result["requirements_confirmed"]
    assert result["plan_confirmed"]
    assert result["skill_status"] == "skipped"
    assert result["final_status"] == "confirmed"
    assert result["m5_entry_reachable"]
    assert result["m5_validation_failure_recoverable"]
    assert result["trial_entry_reachable"]
    assert result["trial_validation_failure_recoverable"]
    assert result["reopened_consistent"]
    assert result["markdown_contains_final_prompt"]
    assert (tmp_path / "session.json").exists()
    assert (tmp_path / "final.md").exists()
