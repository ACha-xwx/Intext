from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from promptsmith.ui import PromptSmithApp


@pytest.fixture
def mousewheel_app(tk_root):
    root = tk.Toplevel(tk_root)
    root.withdraw()
    root.geometry("1120x780")
    app = PromptSmithApp(root)
    # Exercise routing on visible, test-owned controls in the current page.
    # The old requirements details page and its duplicate form were removed.
    app.session.set_task("检查对话区域的滚轮行为")
    app.widgets.get("task_text").insert("1.0",app.session.task_text)
    app.refresh()
    surface=ttk.Frame(app.widgets["requirements_page_content"])
    surface.grid(row=90,column=0,sticky="ew")
    surface.columnconfigure(0,weight=1)
    label=ttk.Label(surface,text="滚轮路由测试")
    label.grid(row=0,column=0,sticky="w")
    text=tk.Text(surface,height=3,width=1)
    text.grid(row=1,column=0,sticky="ew")
    tree=ttk.Treeview(surface,height=3,columns=("content","description","status"),show="headings")
    tree.grid(row=2,column=0,sticky="ew")
    entry=ttk.Entry(surface)
    entry.grid(row=3,column=0,sticky="ew")
    button=ttk.Button(surface,text="测试按钮")
    button.grid(row=4,column=0,sticky="w")
    combo=ttk.Combobox(surface,values=("选项一","选项二"),state="readonly")
    combo.current(0)
    combo.grid(row=5,column=0,sticky="w")
    reading=ttk.Frame(surface)
    reading.grid(row=6,column=0,sticky="ew")
    details=app._conversation_reading(reading,"测试只读正文",height=3)
    app.widgets.update(wheel_text=text,wheel_tree=tree,wheel_entry=entry,wheel_button=button,
                       wheel_combo=combo,wheel_details=details)
    ttk.Label(app.widgets["requirements_page_content"], text="\n" * 30).grid(row=99, column=0)
    app._register_page_wheel_routing()
    root.deiconify()
    root.update_idletasks()
    root.update()
    app._wheel_test_callback_errors = []
    root.report_callback_exception = lambda kind, value, _traceback: app._wheel_test_callback_errors.append(
        f"{kind.__name__}: {value}"
    )
    yield root, app
    app.shutdown(wait=True)
    root.destroy()


def send_wheel(root: tk.Tk, widget: tk.Misc, delta: int, *, shift: bool = False) -> None:
    root_x = widget.winfo_rootx() + max(2, widget.winfo_width() // 2)
    root_y = widget.winfo_rooty() + max(2, widget.winfo_height() // 2)
    local_x = root_x - widget.winfo_rootx()
    local_y = root_y - widget.winfo_rooty()
    sequence = "<Shift-MouseWheel>" if shift else "<MouseWheel>"
    widget.event_generate(sequence, x=local_x, y=local_y, rootx=root_x, rooty=root_y, delta=delta)
    root.update_idletasks()
    root.update()


def add_lines(widget: tk.Text, count: int = 120) -> None:
    widget.insert("end", "\n".join(f"line {index}" for index in range(count)))


def first_label(root: tk.Misc) -> ttk.Label:
    for child in root.winfo_children():
        if isinstance(child, ttk.Label):
            return child
        nested = first_label(child)
        if nested is not None:
            return nested
    return None


def test_page_wheel_works_over_label_empty_text_tree_and_entry(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    task = app.widgets["wheel_text"]
    tree = app.widgets["wheel_tree"]
    label = first_label(app.widgets["requirements_page_content"])
    entry = app.widgets["wheel_entry"]
    button = app.widgets["wheel_button"]

    for target in (label, task, tree, entry, button, canvas):
        canvas.yview_moveto(0.0)
        root.update()
        if target is not canvas:
            app._reveal_guided(target)
            root.update()
        before = tuple(canvas.yview())
        send_wheel(root, target, -120)
        assert tuple(canvas.yview()) != before, target

    canvas.yview_moveto(1.0)
    root.update()
    before = tuple(canvas.yview())
    send_wheel(root, canvas, -120)
    assert tuple(canvas.yview()) == before
    send_wheel(root, canvas, 120)
    assert tuple(canvas.yview()) != before


def test_long_text_and_tree_scroll_inside_then_page_takes_next_event(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    text = app.widgets["wheel_text"]
    tree = app.widgets["wheel_tree"]
    add_lines(text)

    canvas.yview_moveto(0.0)
    text.yview_moveto(0.0)
    root.update()
    app._reveal_guided(text)
    root.update()
    page_before = tuple(canvas.yview())
    inner_before = tuple(text.yview())
    send_wheel(root, text, -120)
    assert tuple(text.yview()) != inner_before
    assert tuple(canvas.yview()) == page_before
    event_position = tuple(text.yview())
    text.yview_moveto(0.0)
    text.yview_scroll(3, "units")
    assert tuple(text.yview()) == event_position

    text.yview_moveto(1.0)
    canvas.yview_moveto(0.0)
    root.update()
    app._reveal_guided(text)
    root.update()
    page_before = tuple(canvas.yview())
    send_wheel(root, text, -120)
    assert tuple(canvas.yview()) != page_before
    assert app._wheel_test_callback_errors == []

    text.delete("1.0", "end")
    for index in range(100):
        tree.insert("", "end", iid=f"wheel_{index}", values=("内容", f"第 {index} 行", "草稿"))
    tree.yview_moveto(0.0)
    canvas.yview_moveto(0.0)
    root.update()
    app._reveal_guided(tree)
    root.update()
    inner_before = tuple(tree.yview())
    page_before = tuple(canvas.yview())
    send_wheel(root, tree, -120)
    assert tuple(tree.yview()) != inner_before
    assert tuple(canvas.yview()) == page_before
    event_position = tuple(tree.yview())
    tree.yview_moveto(0.0)
    tree.yview_scroll(3, "units")
    assert tuple(tree.yview()) == event_position

    tree.yview_moveto(1.0)
    canvas.yview_moveto(0.0)
    root.update()
    app._reveal_guided(tree)
    root.update()
    page_before = tuple(canvas.yview())
    send_wheel(root, tree, -120)
    assert tuple(canvas.yview()) != page_before


def test_readonly_details_uses_inner_scroll_and_then_page_at_boundary(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    details = app.widgets["wheel_details"]
    details.configure(state="normal")
    add_lines(details)
    details.configure(state="disabled")
    details.yview_moveto(0.0)
    canvas.yview_moveto(1.0)
    root.update()
    app._reveal_guided(details)
    root.update()
    page_before = tuple(canvas.yview())
    inner_before = tuple(details.yview())

    send_wheel(root, details, -120)

    assert tuple(details.yview()) != inner_before
    assert tuple(canvas.yview()) == page_before
    details.yview_moveto(0.0)
    root.update()
    page_before = tuple(canvas.yview())
    send_wheel(root, details, 120)
    assert tuple(canvas.yview()) != page_before


def test_plan_page_scrolls_independently_when_content_overflows(mousewheel_app) -> None:
    root, app = mousewheel_app
    requirements = app.widgets["requirements_page_canvas"]
    plan = app.widgets["plan_page_canvas"]
    goal = app.widgets["plan_reading_text"]
    overflow = ttk.Label(app.widgets["plan_page_content"], text=("plan overflow\n" * 120), wraplength=600)
    overflow.grid(row=99, column=0, sticky="w")
    app.notebook.select(1)
    root.update()
    plan.yview_moveto(0.0)
    root.update()
    requirements_before = tuple(requirements.yview())
    plan_before = tuple(plan.yview())

    send_wheel(root, goal, -120)

    assert tuple(plan.yview()) != plan_before
    assert plan.yview()[0] > plan_before[0]
    assert tuple(requirements.yview()) == requirements_before


def test_plan_page_without_overflow_stays_stable(mousewheel_app) -> None:
    root, app = mousewheel_app
    # Global 125% typography makes this form taller. Use an actual viewport
    # large enough for the non-overflow case instead of assuming the old size.
    root.geometry("1440x1100+20+20")
    plan = app.widgets["plan_page_canvas"]
    app.notebook.select(1)
    root.update()
    before = tuple(plan.yview())
    assert before == (0.0, 1.0)

    send_wheel(root, app.widgets["plan_goal_text"], -120)

    assert tuple(plan.yview()) == before


def test_open_dialog_wheel_isolated_from_main_page(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    dialog = tk.Toplevel(root)
    text = tk.Text(dialog, height=4)
    text.pack(fill="both", expand=True)
    add_lines(text)
    dialog.geometry("500x300+300+250")
    dialog.update()
    dialog.grab_set()
    text.yview_moveto(0.0)
    canvas.yview_moveto(0.0)
    root.update()
    inner_before = tuple(text.yview())
    page_before = tuple(canvas.yview())

    send_wheel(root, text, -120)

    assert tuple(text.yview()) != inner_before
    assert tuple(canvas.yview()) == page_before
    dialog.destroy()
    app._reveal_guided(app.widgets["wheel_text"])
    root.update()
    page_before = tuple(canvas.yview())
    send_wheel(root, app.widgets["wheel_text"], -120)
    assert tuple(canvas.yview()) != page_before


def test_menu_is_outside_page_wheel_routing(mousewheel_app) -> None:
    root, app = mousewheel_app
    menu = tk.Menu(root, tearoff=False)
    menu.add_command(label="Menu item")
    try:
        assert app._wheel_bindtag not in menu.bindtags()
    finally:
        menu.destroy()


def test_fractional_delta_and_target_changes_do_not_leak_or_double_scroll(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    task = app.widgets["wheel_text"]
    label = first_label(app.widgets["requirements_page_content"])
    canvas.yview_moveto(0.0)
    root.update()
    before = tuple(canvas.yview())

    send_wheel(root, task, -60)
    assert tuple(canvas.yview()) == before
    send_wheel(root, label, -60)
    assert tuple(canvas.yview()) == before
    send_wheel(root, label, -120)
    assert tuple(canvas.yview()) != before

    canvas.yview_moveto(0.0)
    root.update()
    before = tuple(canvas.yview())
    send_wheel(root, canvas, -60)
    send_wheel(root, canvas, 60)
    assert tuple(canvas.yview()) == before
    send_wheel(root, canvas, -60)
    assert tuple(canvas.yview()) == before
    send_wheel(root, canvas, -60)
    assert tuple(canvas.yview()) != before

    canvas.yview_moveto(0.0)
    root.update()
    before = tuple(canvas.yview())
    send_wheel(root, canvas, 0)
    assert tuple(canvas.yview()) == before
    send_wheel(root, canvas, 1200)
    assert tuple(canvas.yview()) == before
    send_wheel(root, canvas, -1200)
    assert tuple(canvas.yview()) != before


def test_combobox_wheel_does_not_change_value_or_route_shift_to_vertical(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    combo = app.widgets["wheel_combo"]
    original = combo.get()
    canvas.yview_moveto(0.0)
    root.update()
    before = tuple(canvas.yview())

    send_wheel(root, combo, -120)
    assert combo.get() == original
    assert tuple(canvas.yview()) != before

    canvas.yview_moveto(0.0)
    root.update()
    before = tuple(canvas.yview())
    send_wheel(root, combo, -120, shift=True)
    assert combo.get() == original
    assert tuple(canvas.yview()) == before


def test_shift_wheel_keeps_horizontal_scroll_on_long_text(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    text = app.widgets["wheel_text"]
    text.configure(wrap="none")
    text.insert("1.0", "x" * 1000)
    text.xview_moveto(0.0)
    canvas.yview_moveto(0.0)
    root.update()
    app._reveal_guided(text)
    root.update()
    inner_before = tuple(text.xview())
    page_before = tuple(canvas.yview())

    send_wheel(root, text, -120, shift=True)

    assert tuple(text.xview()) != inner_before
    assert tuple(canvas.yview()) == page_before


def test_expanded_combobox_list_wheel_does_not_scroll_background(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    combo = app.widgets["wheel_combo"]
    combo.configure(values=tuple(f"category {index}" for index in range(40)))
    app._reveal_guided(combo)
    combo.tk.call("ttk::combobox::Post", combo._w)
    root.update()
    grab_path = root.tk.call("grab", "current", root._w)
    assert grab_path and str(grab_path) != str(root)
    popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo._w)
    listbox_path = f"{popdown}.f.l"
    assert int(root.tk.call("winfo", "ismapped", listbox_path))
    assert app._wheel_bindtag not in root.tk.splitlist(root.tk.call("bindtags", listbox_path))
    canvas.yview_moveto(0.0)
    root.update()
    page_before = tuple(canvas.yview())
    inner_before = tuple(map(float, root.tk.splitlist(root.tk.call(listbox_path, "yview"))))
    listbox_x = int(root.tk.call("winfo", "rootx", listbox_path)) + 5
    listbox_y = int(root.tk.call("winfo", "rooty", listbox_path)) + 5

    root.tk.call(
        "event",
        "generate",
        listbox_path,
        "<MouseWheel>",
        "-delta",
        -120,
        "-x",
        5,
        "-y",
        5,
        "-rootx",
        listbox_x,
        "-rooty",
        listbox_y,
    )
    root.update()

    assert tuple(canvas.yview()) == page_before
    assert tuple(map(float, root.tk.splitlist(root.tk.call(listbox_path, "yview")))) != inner_before

    canvas.yview_moveto(0.0)
    root.update()
    page_before = tuple(canvas.yview())
    combo.event_generate(
        "<MouseWheel>",
        x=5,
        y=5,
        rootx=listbox_x,
        rooty=listbox_y,
        delta=-120,
    )
    root.update()
    assert tuple(canvas.yview()) == page_before
    combo.tk.call("ttk::combobox::Unpost", combo._w)
    root.update()


def test_refresh_reuses_bindings_and_scroll_does_not_mutate_business_state(mousewheel_app) -> None:
    root, app = mousewheel_app
    canvas = app.widgets["requirements_page_canvas"]
    task = app.widgets["wheel_text"]
    task.insert("1.0", "unchanged task")
    state_before = (
        app.session.to_dict(),
        app.session.requirement_version,
        app.session.confirmed_requirements_version,
        task.get("1.0", "end-1c"),
        app.api_base_var.get(),
        app.category_var.get(),
    )
    for _ in range(4):
        app.refresh()
    canvas.yview_moveto(0.0)
    root.update()
    before = tuple(canvas.yview())
    send_wheel(root, task, -120)
    after = tuple(canvas.yview())
    assert after != before
    event_position = tuple(canvas.yview())
    canvas.yview_moveto(0.0)
    canvas.yview_scroll(1, "units")
    assert tuple(canvas.yview()) == event_position
    state_after = (
        app.session.to_dict(),
        app.session.requirement_version,
        app.session.confirmed_requirements_version,
        task.get("1.0", "end-1c"),
        app.api_base_var.get(),
        app.category_var.get(),
    )
    assert state_after == state_before
    assert app._wheel_test_callback_errors == []


def test_unique_wheel_binding_is_removed_on_shutdown(mousewheel_app) -> None:
    root, app = mousewheel_app
    tag = app._wheel_bindtag
    assert root.tk.call("bind", tag, "<MouseWheel>")
    app.shutdown(wait=True)
    assert root.tk.call("bind", tag, "<MouseWheel>") == ""
