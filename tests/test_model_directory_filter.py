"""Unavailable internal models never become callable UI choices."""
import pytest

from promptsmith.api import ApiConfig, client_for_config
from promptsmith.web_workspace import WorkspaceController
from tests.test_api import Handler, server
from tests.test_conversation_workspace import app


@pytest.mark.parametrize("protocol", ["openai_chat_completions", "openai_responses", "anthropic_messages"])
def test_returned_internal_model_is_filtered_at_directory_boundary(server, protocol):
    Handler.response = {"data": [{"id": "codex-auto-review"}, {"id": "gpt-6.1-sol"}, {"id": "private-alias"}]}
    result = client_for_config(ApiConfig(base_url=server, model="private-alias", api_key="disposable-filter-key", protocol=protocol)).list_models()
    assert result.model_ids == ["gpt-6.1-sol", "private-alias"]


def test_old_cached_internal_model_is_excluded_from_both_model_menus(app):
    app.widgets["api_model_combo"].configure(values=("codex-auto-review", "gpt-6.1-sol"))
    view = WorkspaceController(app)
    assert view.settings_snapshot()["available_models"] == ["gpt-6.1-sol"]
    assert [m["id"] for m in view.snapshot()["models"]] == ["gpt-6.1-sol"]
