"""Approval persists only with its model settings and decryptable credential."""
import json
import sys

import pytest

from promptsmith.preferences import defaults, load_settings, save_preferences, update_debug_preference


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Uses actual current-user DPAPI")
CONNECTION = {"provider": "Fixture", "protocol": "OpenAI Chat Completions",
              "base_url": "https://example.invalid/v1", "model": "offline-model"}


def test_approval_roundtrip_uses_ciphertext_and_normalized_model_options(tmp_path):
    path = tmp_path / "settings.json"
    values = {**defaults(), "generation_timeout": "240", "max_tokens": "20000", "temperature": "0.4"}
    save_preferences(path, values, CONNECTION, api_key="disposable-confirmation-key", model_confirmed=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["model_confirmation"]) == {"version", "fingerprint"}
    assert "disposable-confirmation-key" not in path.read_text(encoding="utf-8")
    assert load_settings(path).model_confirmed
    assert not load_settings(path, restore_credentials=False).model_confirmed
    update_debug_preference(path, True)
    assert load_settings(path).model_confirmed
    assert json.loads(path.read_text(encoding="utf-8"))["model_confirmation"] == data["model_confirmation"]
    for _ in range(2):
        loaded = load_settings(path)
        save_preferences(path, {**loaded.preferences, "font_size": 15}, loaded.connection,
                         api_key=loaded.api_key, model_confirmed=loaded.model_confirmed)
        assert load_settings(path).model_confirmed
    save_preferences(path, loaded.preferences, loaded.connection, api_key=loaded.api_key)
    assert not load_settings(path).model_confirmed
    assert "model_confirmation" not in json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("change", ["model", "provider", "protocol", "base_url", "parameter", "invalid_parameter",
    "ciphertext", "key_replacement", "credentials_removed", "credentials_malformed", "confirmation_malformed",
    "confirmation_version", "confirmation_version_bool", "confirmation_fingerprint", "preferences_removed"])
def test_changed_or_broken_approval_never_blocks_loading_public_settings(tmp_path, change):
    path = tmp_path / "settings.json"
    save_preferences(path, {**defaults(), "generation_timeout": 250, "font_size": 16}, CONNECTION,
                     api_key="disposable-confirmation-key", model_confirmed=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    if change in CONNECTION:
        data["connection"][change] = "https://other.invalid" if change == "base_url" else "Changed"
    elif change in {"parameter", "invalid_parameter"}:
        data["preferences"]["generation_timeout"] = 300 if change == "parameter" else "nan"
    elif change == "ciphertext":
        data["credentials"]["api_key"]["ciphertext"] = "broken"
    elif change == "key_replacement":
        from promptsmith.credentials import encrypt_api_key
        data["credentials"]["api_key"] = encrypt_api_key("different-disposable-key", CONNECTION)
    elif change == "credentials_removed":
        data.pop("credentials")
    elif change == "credentials_malformed":
        data["credentials"] = "broken"
    elif change == "confirmation_malformed":
        data["model_confirmation"] = True
    elif change == "preferences_removed":
        data.pop("preferences")
    elif change in {"confirmation_version", "confirmation_version_bool"}:
        data["model_confirmation"]["version"] = 999 if change == "confirmation_version" else True
    else:
        data["model_confirmation"]["fingerprint"] = "broken"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_settings(path)
    assert not loaded.model_confirmed
    assert loaded.preferences["font_size"] == (12 if change == "preferences_removed" else 16)
    assert "确认" in loaded.warning


def test_confirmation_without_credential_is_not_persisted(tmp_path):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), CONNECTION, model_confirmed=True)
    assert not load_settings(path).model_confirmed
    assert "model_confirmation" not in json.loads(path.read_text(encoding="utf-8"))
