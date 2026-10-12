"""Retired desktop M5 entrypoints; historical session data stays readable."""
from tests.test_conversation_workspace import app, install_session
from tests.test_final_delivery import confirmed_plan_session
from promptsmith.storage import save_session, load_session


def test_example_preference_user_feature_is_removed(app):
    assert not hasattr(app, "start_m5_generation")
    assert not hasattr(app, "select_m5_disposition")
    assert not hasattr(app, "record_m5_feedback")
    assert not any(name.startswith("m5_") for name in app.widgets)
    assert "m5_max_chars" not in app.preference_vars


def test_old_example_data_can_reopen_without_restoring_feature(app, tmp_path):
    session=confirmed_plan_session()
    session.m5_examples=[{"task_id":session.task_id,"base_version":session.requirement_version,"example_id":"historical",
        "example":{"dimension":"风格","option_a":"历史A","option_b":"历史B","difference_summary":"历史比较"}}]
    path=save_session(session,tmp_path/"historical.json")
    loaded=load_session(path)
    install_session(app,loaded)
    assert app.session.m5_examples==session.m5_examples
    assert not any(name.startswith("m5_") for name in app.widgets)
    assert not app.dialogs
