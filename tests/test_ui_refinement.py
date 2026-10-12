"""Actual Tk interaction acceptance for the ten UI changes; no model calls."""
from copy import deepcopy
import json
import math
import time
import tkinter as tk
import tkinter.font as tkfont

import pytest

from promptsmith.composer import THEMES
from promptsmith.response_ui import ResponseTrace
from promptsmith.typography import UI_SCALE
from promptsmith.m1 import M1Assets, build_m1_input, parse_m1_response
from tkinter import ttk
from tests.test_conversation_workspace import app, install_session
from tests.test_response_workspace import questions
from tests.test_final_delivery import confirmed_plan_session


def pump(app, seconds=.45):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        app.root.update()
        time.sleep(.004)


def show(app,width=1440,height=810):
    app.root.minsize(640,380)
    app.root.geometry(f"{width}x{height}+20+20")
    app.root.deiconify()
    app.root.lift()
    pump(app,.08)


def test_font_scale_and_native_baseline_placeholder(app):
    show(app)
    composer=app.widgets["conversation_composer"]
    composer.entry.focus_force()
    composer.refresh()
    pump(app,.05)
    for source in (9,10,11,12,17,"body","title","heading"):
        baseline={"body":12,"title":17,"heading":11}.get(source,source)
        assert app.typography.font(source).actual("size")==round(baseline*UI_SCALE)
    line=composer.entry.dlineinfo("1.0")
    assert line is not None
    assert composer.placeholder.winfo_rooty()==composer.entry.winfo_rooty()+line[1]
    assert composer.placeholder.winfo_height()==line[3]
    assert composer.placeholder.cget("cursor")==composer.entry.cget("cursor")=="xterm"
    assert tkfont.Font(app.root,font=composer.placeholder.cget("font")).actual()==tkfont.Font(app.root,font=composer.entry.cget("font")).actual()
    composer.entry.insert("1.0","English 中文 123")
    pump(app,.03)
    assert not composer.placeholder.winfo_manager()


def test_compact_answer_controls_keep_drafts_and_have_no_options(app):
    show(app)
    app.widgets["task_text"].insert("1.0","重做UI")
    app._sync_input()
    qs=questions()
    qs[0]["options"]=["HISTORICAL_OPTION"]
    app.session.pending_questions=qs
    app.refresh()
    pump(app,.03)
    answer=app._question_inputs["q1"]
    send=app._conversation_buttons["submit:q1"]
    skip=app._conversation_buttons["skip"]
    assert int(answer.cget("height"))==2
    assert answer.master.winfo_height()==tkfont.Font(app.root,font=answer.cget("font")).metrics("linespace")*2+20
    assert abs(send.winfo_rooty()+send.winfo_height()/2-(skip.winfo_rooty()+skip.winfo_height()/2))<=2
    assert send.arrow and send.cget("state")=="disabled"
    assert not any(key.startswith("option:") or key=="unsure" for key in app._conversation_buttons)
    assert "HISTORICAL_OPTION" not in " ".join(w.cget("text") for w in app._conversation_labels)
    assert skip.find_all() and any(skip.type(i)=="line" for i in skip.find_all())
    answer.insert("1.0","留存草稿")
    app.root.update()
    assert send.cget("state")=="normal"
    app.preferences["composer_theme"]="dark"
    app.refresh()
    assert app._question_inputs["q1"].get("1.0","end-1c")=="留存草稿"


def test_thinking_animation_is_reversible_and_wheel_is_owned(app):
    show(app)
    record={"id":"animation","status":"working","reasoning":"思考内容\n"*180,"activities":[]}
    trace=ResponseTrace(app.widgets["conversation_timeline"],record)
    trace.grid(row=0,column=0,sticky="ew")
    assert not trace.opened
    pump(app,.1)  # Resolve initial clipped geometry before starting the animation.
    trace.toggle()  # The user explicitly opens the default-folded reasoning.
    trace.writer.finish()
    pump(app,.8)
    expanded=trace.channel.winfo_height()
    assert expanded>100
    heights=[]
    trace.channel.bind("<Configure>",lambda e:heights.append(e.height),add="+")
    trace.toggle()
    pump(app,.05)
    assert any(1<height<expanded for height in heights)
    assert len(set(heights))>2
    trace.toggle()  # Reverse while animation is running.
    pump(app)
    assert trace.channel.winfo_height()>=expanded-2
    trace.toggle_thought()
    pump(app)
    assert trace.thought_frame.winfo_height()==1
    assert abs(trace.thinking_button.angle)<.001
    trace.toggle_thought()
    pump(app)
    assert abs(trace.thinking_button.angle-math.pi/2)<.001
    outer=app.widgets["requirements_page_canvas"]
    before=outer.yview()
    trace.thought.yview_moveto(0)
    trace.thought.event_generate("<MouseWheel>",delta=-120)
    app.root.update()
    assert trace.thought.yview()[0]>0
    assert outer.yview()==before
    assert not hasattr(trace,"copy")
    trace.close()
    trace.destroy()


@pytest.mark.parametrize("kind",["summary"])
def test_top_panel_is_read_only_bounded_and_closes_on_new_session(app,kind):
    show(app)
    install_session(app,confirmed_plan_session())
    before=deepcopy(app.session.to_dict())
    app._toggle_workspace_popover(kind)
    panel=app._workspace_popover
    pump(app)
    assert panel.window.winfo_ismapped()
    assert panel.window.winfo_width()<app.root.winfo_width()
    assert app.session.to_dict()==before
    assert "requirements" in app._conversation_frames
    assert "conversation_details" not in app.widgets
    if kind=="requirements":
        assert len(app.widgets["conversation_requirements_tree"].get_children())==len(app.session.requirements)
    app.new_session()
    pump(app,.05)
    assert app._workspace_popover is None
    assert not panel.window.winfo_exists()


def test_glass_menu_animation_selection_and_dismissal(app):
    show(app)
    composer=app.widgets["conversation_composer"]
    button=composer.depth_button
    button._hover(True)
    pump(app,.07)
    assert 0<button.amount<1
    pump(app,.22)
    assert button.amount==1
    before=deepcopy(app.session.to_dict())
    composer.toggle_choices("depth")
    menu=composer.choice_menu
    pump(app,.015)
    assert 0<float(menu.window.attributes("-alpha"))<=1
    assert menu.tween.job is not None or menu.window.winfo_width()==menu.width
    pump(app)
    assert app.session.to_dict()==before
    menu.rows["deep"].event_generate("<Button-1>")
    pump(app)
    assert app.thinking_level_var.get()=="deep"
    assert app.session.control["thinking_level"]=="deep"
    composer.toggle_choices("category")
    menu=composer.choice_menu
    pump(app)
    app.root.event_generate("<Configure>")
    pump(app,.02)
    assert composer.choice_menu is menu and menu.window.winfo_exists()
    label=next(label for label in app.category_by_label if label!="自动判断")
    menu.rows[label].event_generate("<Button-1>")
    pump(app)
    assert app.category_var.get()==label
    assert app.session.selected_category==app.category_by_label[label]
    assert composer.choice_menu is None
    assert composer.depth_button.winfo_rootx()<composer.category_button.winfo_rootx()<composer.send_button.winfo_rootx()
    composer.toggle_choices("depth")
    pump(app)
    app.root.geometry("1400x790")
    pump(app,.02)
    assert composer.choice_menu is None


def test_removed_old_user_features_and_file_save_retained(app):
    assert not any(name in app.widgets for name in ("save_button","category_combo","thinking_level_combo","conversation_details","m5_generate_button","advanced_requirements_panel"))
    assert not hasattr(app,"start_m5_generation")
    assert "m5_max_chars" not in app.preference_vars
    menu=app.root.nametowidget(app.root.tk.call(str(app.root),"cget","-menu"))
    index=next(i for i in range(menu.index("end")+1) if menu.type(i)=="cascade" and menu.entrycget(i,"label")=="文件")
    file_menu=app.root.nametowidget(menu.entrycget(index,"menu"))
    labels=[file_menu.entrycget(i,"label") for i in range(file_menu.index("end")+1) if file_menu.type(i)!="separator"]
    assert any("保存" in label for label in labels)


def test_ready_requirements_points_to_explicit_review_panel(app):
    session=confirmed_plan_session()
    session.confirmed_requirements_version=None
    install_session(app,session)
    assert "对话中的需求" in app.conversation_hint_var.get()
    assert session.confirmed_requirements_version is None


def test_dark_workspace_tables_do_not_use_vista_white_fields(app):
    style=ttk.Style(app.root)
    original=style.layout("Treeview")
    native_theme=style.theme_use()
    app.preferences["composer_theme"]="dark"
    app.refresh()
    assert style.theme_use()==native_theme
    assert style.layout("Treeview")==original
    assert style.layout("Workspace.Treeview")[0][0]=="Workspace.Treeview.field"
    assert style.lookup("Workspace.Treeview","fieldbackground")==THEMES["dark"].bg
    assert style.layout("Workspace.Treeview.Heading")[0][0]=="Workspace.Treeheading.cell"


def test_current_question_contract_accepts_omitted_options_and_keeps_history(tmp_path):
    from tests.test_m1_source_quotes import _prepared
    _session,workflow,payload,result=_prepared(tmp_path)
    result["questions"]=[{"question_id":"q-free","gap_id":"g-free","field":"audience","scope":"当前任务",
                          "text":"这个软件由谁使用？","reason":"明确受众","depends_on":[]}]
    result["gaps"]=[{"gap_id":"g-free","field":"audience","scope":"当前任务","description":"受众未明确",
                    "importance":"blocking_direction","origin":"missing","source_refs":[],"depends_on":[]}]
    result["proposals"]=[]
    result["readiness"]["blocking_gap_ids"]=["g-free"]
    result["next_action"]="ask"
    schema=workflow.assets.output_schema
    assert "options" not in schema["properties"]["questions"]["items"]["required"]
    parsed=parse_m1_response(json.dumps(result,ensure_ascii=False),payload,schema)
    assert parsed["questions"][0]["options"]==[]


@pytest.mark.parametrize("width,height",[(1440,810),(960,640),(720,500)])
def test_centered_content_and_composer_controls_fit(app,width,height):
    show(app,width,height)
    canvas=app.widgets["requirements_page_canvas"]
    content=app.widgets["requirements_page_content"]
    composer=app.widgets["conversation_composer"]
    assert content.winfo_width()<=1060
    assert abs(content.winfo_rootx()+content.winfo_width()/2-(canvas.winfo_rootx()+canvas.winfo_width()/2))<=2
    assert abs(composer.winfo_rootx()+composer.winfo_width()/2-(canvas.winfo_rootx()+canvas.winfo_width()/2))<=8
    for button in (composer.depth_button,composer.category_button,composer.send_button):
        assert button.winfo_rootx()+button.winfo_width()<app.root.winfo_rootx()+app.root.winfo_width()
    assert not app.callback_errors


def test_composer_layers_do_not_overlap_after_font_change(app):
    show(app)
    composer=app.widgets["conversation_composer"]
    for size in (16,9,18,12):
        app.preference_vars["font_size"].set(str(size))
        assert app.save_settings()
        pump(app,.04)
        assert composer.entry.winfo_rooty()+composer.entry.winfo_height()<composer.toolbar.winfo_rooty()
        assert composer.toolbar.winfo_rooty()+composer.toolbar.winfo_height()<composer.winfo_rooty()+composer.winfo_height()
        assert composer.placeholder.winfo_rooty()+composer.placeholder.winfo_height()<=composer.entry.winfo_rooty()+composer.entry.winfo_height()
        assert composer.placeholder.winfo_ismapped()
        assert composer.body.winfo_children()[-1] is composer.placeholder
        assert len([child for child in composer.toolbar.winfo_children() if child.text=="任务类型"])==1
