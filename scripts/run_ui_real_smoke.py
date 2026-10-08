from __future__ import annotations

import getpass
import json
import sys
import time
import tkinter as tk
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import promptsmith.ui as ui_module
from promptsmith.storage import save_session
from promptsmith.ui import PromptSmithApp


def pump(root: tk.Tk, app: PromptSmithApp, timeout: float = 100) -> None:
    deadline = time.time() + timeout
    while app.busy and time.time() < deadline:
        root.update()
        time.sleep(0.02)
    root.update()
    if app.busy:
        raise TimeoutError("UI background call did not finish in time.")


def main() -> int:
    api_key = getpass.getpass("DeepSeek API key (memory only, not stored): ")
    errors: list[str] = []
    ui_module.messagebox.showerror = lambda title, message, **kwargs: errors.append(f"{title}: {message}")
    ui_module.messagebox.showinfo = lambda *args, **kwargs: None
    ui_module.messagebox.askyesno = lambda *args, **kwargs: True
    root = tk.Tk()
    root.withdraw()
    evidence_root = ROOT / "verification" / "ui-smoke" / "runs"
    app = PromptSmithApp(root, evidence_root=evidence_root)
    try:
        app.api_base_var.set("https://api.deepseek.com")
        app.api_model_var.set("deepseek-chat")
        app.api_key_var.set(api_key)
        app.confirm_model_settings()
        app.widgets["task_text"].insert("1.0", "帮我做一个活动报名网站，不做付款。")

        app.start_analysis()
        pump(root, app)
        if errors or not app.session.pending_proposals or not app.session.pending_questions:
            raise RuntimeError(f"First turn did not reach candidates and questions: {errors}")
        first_request = app.session.api_runs[-1]["request_id"]
        app.accept_all_proposals()
        question_id = app.session.pending_questions[0]["question_id"]
        app.widgets["questions_tree"].selection_set(question_id)
        app.answer_var.set("先做课堂演示；只要活动信息和报名表单，不需要后台管理。")
        app.record_question("answered")

        app.start_analysis()
        pump(root, app)
        if errors or len(app.session.api_runs) < 2:
            raise RuntimeError(f"Second turn did not complete: {errors}")
        second_request = app.session.api_runs[-1]["request_id"]
        if app.session.pending_proposals:
            app.accept_all_proposals()

        confirmed = False
        if not app.session.open_conflicts and not any(
            gap.get("importance") == "blocking_direction" for gap in app.session.gaps
        ):
            app.session.confirm_requirements()
            confirmed = True

        output = ROOT / "verification" / "ui-smoke"
        output.mkdir(parents=True, exist_ok=True)
        session_path = save_session(app.session, output / "session.json")
        report = {
            "evidence_type": "real_model_ui_smoke",
            "protocol": "deepseek_chat_completions",
            "configured_model": "deepseek-chat",
            "prompt_version": app.assets.prompt_version,
            "contract_version": app.assets.contract_version,
            "turns": 2,
            "request_ids": [first_request, second_request],
            "requirements": len(app.session.requirements),
            "questions_recorded": len(app.session.question_history),
            "remaining_questions": len(app.session.pending_questions),
            "next_action": app.session.last_next_action,
            "confirmed": confirmed,
            "session_path": str(session_path),
            "errors": errors,
        }
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(json.dumps(report, ensure_ascii=False))
        return 0
    finally:
        api_key = ""
        app.executor.shutdown(wait=True, cancel_futures=True)
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
