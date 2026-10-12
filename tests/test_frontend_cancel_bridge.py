"""Cancellation through the desktop action boundary, synthetic model only."""
from copy import deepcopy
from threading import Event

from promptsmith.web_workspace import WorkspaceController, view_stamp
from tests.test_ui_delivery_interactions import (
    delivery_app, _candidate, _set_binding, _DeliveryUiClient,
    _configure_delivery_client, _pump_until,
)


def test_busy_web_cancel_unlocks_preserves_state_and_discards_late_result(delivery_app, monkeypatch):
    app, window = delivery_app
    candidate, binding = _candidate()
    _set_binding(app, candidate, binding)
    client = _DeliveryUiClient()
    _configure_delivery_client(app, monkeypatch, client)
    app.widgets["skill_integrate_button"].invoke()
    _pump_until(window, lambda: not app.delivery_busy)
    previous = deepcopy(app.session.final_result)
    selected = deepcopy(app.session.skill_state)
    entered, release = Event(), Event()
    client.entered, client.release = entered, release
    app.widgets["skill_integrate_button"].invoke()
    try:
        assert entered.wait(3)
        controller = WorkspaceController(app)
        assert controller.snapshot()["buttons"]["cancel_request"]["enabled"]
        cancel = app._conversation_buttons["cancel_request"]
        parent = cancel.master
        while parent is not None and parent is not app._conversation_frames["skills"]:
            parent = parent.master
        assert parent is app._conversation_frames["skills"]
        controller.dispatch("button", {"key": "cancel_request"}, view_stamp(app))
        assert not controller.snapshot()["locked"]
        assert app.session.final_result == previous and app.session.skill_state == selected
    finally:
        release.set()
    _pump_until(window, lambda: app.completions.empty() and not app.delivery_busy)
    assert app.session.final_result == previous
    assert controller.snapshot()["buttons"]["integrate"]["enabled"]
    assert controller.snapshot()["buttons"]["direct_skills"]["enabled"]
