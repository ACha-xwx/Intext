"""Custom-provider rename regression cases; run after this repair batch."""
from copy import deepcopy
import json
import sys

import pytest

from promptsmith.preferences import defaults, load_settings, save_preferences, rename_provider_profile
from promptsmith.web_workspace import WorkspaceController
from tests.test_conversation_workspace import app
from tests.test_custom_provider_profiles import custom_connection

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")


def saved_profiles(tmp_path):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), dict(provider="DeepSeek", protocol="OpenAI Chat Completions",
        base_url="https://api.deepseek.com", model="deepseek-chat"), api_key="disposable-deepseek-key", model_ids=("deepseek-chat",))
    save_preferences(path, defaults(), custom_connection("OpenAI"), api_key="disposable-rename-key",
                     model_confirmed=True, model_ids=("private-alias", "gpt-6.1-sol"))
    return path


def test_rename_preserves_encrypted_key_configuration_directory_and_confirmation(tmp_path):
    path = saved_profiles(tmp_path)
    before = json.loads(path.read_text(encoding="utf-8"))
    profile = rename_provider_profile(path, "麻豆科技", "比赛中转")
    loaded = load_settings(path)
    after = json.loads(path.read_text(encoding="utf-8"))
    assert "麻豆科技" not in loaded.model_profiles
    assert loaded.connection == dict(custom_connection("OpenAI"), provider="比赛中转")
    assert loaded.api_key == profile.api_key == "disposable-rename-key"
    assert loaded.model_ids == ("private-alias", "gpt-6.1-sol")
    assert loaded.model_confirmed and profile.model_confirmed
    assert before["model_profiles"]["DeepSeek"] == after["model_profiles"]["DeepSeek"]
    assert before["credentials"] != after["credentials"]
    assert "disposable-" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["", " ", "DeepSeek", "deepseek"])
def test_invalid_or_conflicting_name_leaves_settings_unchanged(tmp_path, name):
    path = saved_profiles(tmp_path)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        rename_provider_profile(path, "麻豆科技", name)
    assert path.read_bytes() == before


def test_disk_or_encryption_failure_preserves_original_name_and_ciphertext(tmp_path, monkeypatch):
    import promptsmith.preferences as preferences
    from promptsmith.credentials import CredentialProtectionError
    path = saved_profiles(tmp_path)
    before = path.read_bytes()
    def fail_encrypt(*_):
        raise CredentialProtectionError("模拟 DPAPI 失败")
    with monkeypatch.context() as context:
        context.setattr(preferences, "encrypt_api_key", fail_encrypt)
        with pytest.raises(OSError):
            rename_provider_profile(path, "麻豆科技", "新名称")
    assert path.read_bytes() == before
    def fail_write(*_):
        raise OSError("模拟写盘失败")
    monkeypatch.setattr(preferences, "_write_document", fail_write)
    with pytest.raises(OSError):
        rename_provider_profile(path, "麻豆科技", "新名称")
    assert path.read_bytes() == before


def test_new_ciphertext_restore_failure_does_not_replace_original_settings(tmp_path, monkeypatch):
    import promptsmith.preferences as preferences
    from promptsmith.credentials import CredentialProtectionError
    path = saved_profiles(tmp_path)
    before = path.read_bytes()
    decrypt = preferences.decrypt_api_key
    calls = 0
    def fail_new_credential(*args):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise CredentialProtectionError("模拟新密文恢复失败")
        return decrypt(*args)
    monkeypatch.setattr(preferences, "decrypt_api_key", fail_new_credential)
    with pytest.raises(OSError, match="原供应商已保留"):
        rename_provider_profile(path, "麻豆科技", "新名称")
    assert path.read_bytes() == before


def test_inactive_profile_rename_keeps_active_service_and_other_profiles(tmp_path):
    path = saved_profiles(tmp_path)
    connection = dict(provider="DeepSeek", protocol="OpenAI Chat Completions", base_url="https://api.deepseek.com", model="deepseek-chat")
    save_preferences(path, defaults(), connection, api_key="disposable-deepseek-key", model_ids=("deepseek-chat",))
    before = json.loads(path.read_text(encoding="utf-8"))
    rename_provider_profile(path, "麻豆科技", "比赛中转")
    loaded = load_settings(path)
    after = json.loads(path.read_text(encoding="utf-8"))
    assert loaded.connection == connection and loaded.api_key == "disposable-deepseek-key"
    for field in ("connection", "credentials", "model_directory", "preferences"):
        assert after[field] == before[field]
    assert loaded.model_profiles["比赛中转"].model_confirmed
    assert loaded.model_profiles["比赛中转"].model_ids == ("private-alias", "gpt-6.1-sol")


def test_invalid_saved_confirmation_is_not_approved_by_rename(tmp_path):
    path = saved_profiles(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["model_confirmation"]["fingerprint"] = "stale-confirmation"
    path.write_text(json.dumps(document), encoding="utf-8")
    renamed = rename_provider_profile(path, "麻豆科技", "新名称")
    assert renamed.api_key == "disposable-rename-key"
    assert not renamed.model_confirmed and not load_settings(path).model_confirmed


def test_controller_rename_updates_picker_and_next_save_cannot_restore_old_name(app):
    view = WorkspaceController(app)
    snap = view.settings_snapshot()
    view.settings_action("settings_confirm", dict(revision=snap["revision"], connection=custom_connection("OpenAI"),
        values=snap["values"], key_action="replace", key="disposable-rename-key"))
    app.widgets["api_model_combo"].configure(values=("private-alias",))
    app.save_settings()
    before = view.settings_snapshot()
    result = view.settings_action("settings_rename_provider", {"revision": before["revision"], "target": "麻豆科技", "name": "GPT中转"})
    assert result["settings"]["connection"]["provider"] == "GPT中转"
    assert app.api_key_var.get() == "disposable-rename-key"
    assert app.widgets["api_model_combo"].cget("values") == ("private-alias",)
    assert "麻豆科技" not in app._provider_profiles
    assert view.snapshot()["models"][0]["service_provider"] == "GPT中转"
    app.save_settings()
    assert "麻豆科技" not in load_settings(app._preferences_path).model_profiles
    assert "disposable-" not in json.dumps(result)


def test_stale_rename_request_cannot_change_another_service(app):
    view = WorkspaceController(app)
    before = deepcopy(app._provider_profiles)
    with pytest.raises(ValueError):
        view.settings_action("settings_rename_provider", {"revision": "stale", "target": "旧供应商", "name": "新名称"})
    assert app._provider_profiles == before


def test_rename_and_toolbar_debug_projection_is_short_but_errors_are_complete(tmp_path):
    import logging
    from promptsmith.runtime_log import RuntimeLog
    from promptsmith.web_debug import DebugApi, WebDebugConsole
    from promptsmith.web_workspace import DesktopApi
    logs = RuntimeLog(tmp_path / "logs")
    messages = ["Custom provider renamed; credential preserved=True models=2",
                "Browser skill table toolbar rendered: source=本地 rows=3 show_all=false"]
    for message in messages:
        logs.record("promptsmith.web_workspace", logging.INFO, message)
    logs.record("promptsmith.preferences", logging.ERROR, "Custom provider rename failed; original profile retained\n原因：模拟 DPAPI 失败")
    entries = DebugApi(WebDebugConsole(logs, DesktopApi())).snapshot()["entries"]
    assert [row["message"] for row in entries[:2]] == ["服务已重命名，保留 2 个模型和加密密钥", "Skill 表格：本地，3 项，推荐"]
    assert all(message in entry["text"] for message, entry in zip(messages, entries))
    assert "原因：模拟 DPAPI 失败" in entries[-1]["message"]
    assert not logs.directory.exists()
