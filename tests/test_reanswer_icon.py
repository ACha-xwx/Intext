"""History answer action placement, target and guarded interaction."""
from copy import deepcopy

import pytest

from promptsmith.interaction_ui import GlassButton
from tests.test_conversation_workspace import app
from tests.test_response_workspace import questions
from tests.test_ui_refinement import show, pump


@pytest.mark.parametrize("theme,width",[("light",1440),("dark",720)])
def test_loop_action_is_next_to_answer_and_reopens_its_question(app,theme,width):
    show(app,width=width,height=810)
    app.widgets["task_text"].insert("1.0","改进软件界面")
    app._sync_input()
    app.session.pending_questions=questions()
    app.session.record_question("q2","answered","这是一个比赛项目，将放到GitHub开源")
    app.preferences["composer_theme"]=theme
    app.refresh()
    pump(app,.05)
    answer=app.session.question_history[-1]
    button=app._conversation_buttons["question:"+answer["answer_id"]]
    bubble=app._conversation_frames["answer:"+answer["answer_id"]].master
    assert isinstance(button,GlassButton)
    assert button.icon_name=="loop" and button._icon_image is not None
    assert int(button.cget("width"))==int(button.cget("height"))
    assert button.winfo_rootx()+button.winfo_width()<bubble.winfo_rootx()
    assert abs(button.winfo_rooty()+button.winfo_height()/2-(bubble.winfo_rooty()+bubble.winfo_height()/2))<=2
    assert bubble.winfo_rootx()+bubble.winfo_width()<=app.root.winfo_rootx()+app.root.winfo_width()
    assert button.master is not app._conversation_frames["question:"+answer["answer_id"]]
    button._show_tip()
    assert button._tip.winfo_exists()
    button._hide_tip()
    before=deepcopy(app.session.to_dict())
    button.invoke()
    assert app._answer_target_id=="q2"
    assert "第2个问题" in app.question_context_var.get()
    assert app.session.to_dict()==before


def test_reanswer_glass_action_is_disabled_when_busy(app):
    app.widgets["task_text"].insert("1.0","目标")
    app._sync_input()
    app.session.pending_questions=questions()
    app.session.record_question("q1","answered","回答")
    app.busy=True
    app.refresh()
    answer=app.session.question_history[-1]
    button=app._conversation_buttons["question:"+answer["answer_id"]]
    assert button.cget("state")=="disabled"
    button.invoke()
    assert app._answer_target_id is None
