from copy import deepcopy

from tests.test_ui_delivery_interactions import delivery_app, _configure_delivery_client, _pump_until
from tests.test_m2 import valid_result
from tests.test_m2_workflow import Client
from tests.test_m2_unknown_recovery import unknown


def test_new_unknown_generates_plan_without_error_and_explains_defer(delivery_app, monkeypatch):
    app, window = delivery_app

    def response(payload):
        result = valid_result(payload)
        result["plan"]["unresolved_items"] = [unknown(source="r2")]
        return result

    _configure_delivery_client(app, monkeypatch, Client(response))
    app.widgets["generate_plan_button"].invoke()
    _pump_until(window, lambda: not app.busy)
    assert not app.test_dialogs
    assert app.session.plan["status"] == "draft"
    assert len(app.session.plan["content"]["unresolved_items"]) == 1
    assert "下游 AI" in app.status_var.get()
    assert app._primary_action().kind == "confirm_plan_generate"
    assert not app.session.questions_for_review(respect_interview_limit=False)
    app.toggle_plan_review()
    assert str(app._conversation_buttons["confirm_plan"]["state"]) == "normal"
    assert "设计稿格式尚未决定" in app.widgets["conversation_plan_reading"].get("1.0", "end-1c")
    # The separately confirmed settings remain intact after generating a plan.
    assert app._model_settings_confirmed()
    app.show_workspace(1)
    app.show_settings()
    assert app.notebook.index(app.notebook.select()) == 4
    app.return_from_settings()
    assert app.notebook.index(app.notebook.select()) == 1


def test_recoverable_model_reference_returns_plan_with_visible_unknown(delivery_app, monkeypatch):
    app, window = delivery_app
    app.session.plan["status"] = "stale"
    previous = deepcopy(app.session.plan)
    requirements = deepcopy(app.session.requirements)

    def response(payload):
        result = valid_result(payload)
        result["plan"]["steps"][0]["depends_on_step_ids"] = ["bad"]
        return result

    _configure_delivery_client(app, monkeypatch, Client(response))
    app.widgets["generate_plan_button"].invoke()
    _pump_until(window, lambda: not app.busy)
    assert app.session.requirements == requirements
    assert app.session.plan["status"] == "draft"
    assert not app.test_dialogs
    assert any("bad" in row["description"] for row in app.session.plan["content"]["unresolved_items"])
    assert "下游 AI" in app.status_var.get()
    assert not app.session.questions_for_review(respect_interview_limit=False)
