from __future__ import annotations

import json
import sys
import tkinter as tk
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promptsmith.ui import PromptSmithApp


M1_WIDGETS = (
    "task_text",
    "analyze_button",
    "requirements_tree",
    "proposals_tree",
    "questions_tree",
    "details_text",
)
M2_WIDGETS = (
    "plan_goal_text",
    "generate_plan_button",
    "plan_steps_tree",
    "plan_overview_text",
    "plan_key_work_tree",
    "confirm_plan_button",
)


def inspect(base: tk.Tk, scale: float, label: str) -> dict:
    base.tk.call("tk", "scaling", scale)
    window = tk.Toplevel(base)
    app = PromptSmithApp(window)
    window.geometry("1120x780+20+20")
    window.update_idletasks()
    window.update()
    result = {
        "label": label,
        "tk_scaling": float(base.tk.call("tk", "scaling")),
        "window": {"width": window.winfo_width(), "height": window.winfo_height()},
        "tabs": [],
        "checks": [],
    }
    try:
        for tab_index, names in ((0, M1_WIDGETS), (1, M2_WIDGETS)):
            app.notebook.select(tab_index)
            window.update_idletasks()
            window.update()
            page_canvas = app.widgets[
                "requirements_page_canvas" if tab_index == 0 else "plan_page_canvas"
            ]
            root_x, root_y = window.winfo_rootx(), window.winfo_rooty()
            root_right = root_x + window.winfo_width()
            root_bottom = root_y + window.winfo_height()
            rows = []
            for name in names:
                widget = app.widgets[name]
                x, y = widget.winfo_rootx(), widget.winfo_rooty()
                width, height = widget.winfo_width(), widget.winfo_height()
                visible = bool(widget.winfo_ismapped())
                inside = (
                    visible
                    and x >= root_x
                    and y >= root_y
                    and x + width <= root_right
                    and y + height <= root_bottom
                    and width > 20
                    and height > 10
                )
                reachable_after_scroll = inside
                scroll_position = tuple(float(value) for value in page_canvas.yview())
                if not inside:
                    page_canvas.yview_moveto(1.0)
                    window.update_idletasks()
                    window.update()
                    x, y = widget.winfo_rootx(), widget.winfo_rooty()
                    width, height = widget.winfo_width(), widget.winfo_height()
                    reachable_after_scroll = (
                        bool(widget.winfo_ismapped())
                        and x >= root_x
                        and y >= root_y
                        and x + width <= root_right
                        and y + height <= root_bottom
                        and width > 20
                        and height > 10
                    )
                    scroll_position = tuple(float(value) for value in page_canvas.yview())
                    page_canvas.yview_moveto(0.0)
                    window.update_idletasks()
                    window.update()
                rows.append(
                    {
                        "widget": name,
                        "x": x - root_x,
                        "y": y - root_y,
                        "width": width,
                        "height": height,
                        "mapped": visible,
                        "inside_window_initially": inside,
                        "reachable_after_page_scroll": reachable_after_scroll,
                        "page_scroll_position_checked": scroll_position,
                    }
                )
                result["checks"].append(reachable_after_scroll)
            result["tabs"].append({"tab_index": tab_index, "widgets": rows})
    finally:
        app.shutdown(wait=True)
        window.destroy()
    result["passed"] = all(result["checks"])
    return result


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_ui_layout.py OUTPUT_JSON")
    output = Path(sys.argv[1]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    current_scale = float(root.tk.call("tk", "scaling"))
    try:
        results = [
            inspect(root, current_scale, "current_system_tk_scaling"),
            inspect(root, 120 / 72, "simulated_125_percent"),
            inspect(root, 144 / 72, "simulated_150_percent"),
        ]
    finally:
        root.destroy()
    report = {
        "evidence_type": "local_layout_geometry_check",
        "date": date.today().isoformat(),
        "window_requested": "1120x780",
        "results": results,
        "passed": all(row["passed"] for row in results),
        "limitations": [
            "125% 和 150% 使用 Tk scaling 模拟字体和控件缩放，不等同于修改 Windows 系统 DPI 后的人工截图验收。",
            "当前会话的 Windows 界面捕获能力不可用，因此未生成截图。",
        ],
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
