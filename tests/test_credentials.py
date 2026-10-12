import base64
import json
import sys

import pytest

from promptsmith.credentials import CredentialProtectionError, decrypt_api_key, encrypt_api_key
from promptsmith.preferences import defaults, load_settings, save_preferences, update_debug_preference


CONNECTION = {"provider": "fixture", "model_provider": "Google", "protocol": "OpenAI Chat Completions",
              "base_url": "https://example.invalid/v1", "model": "offline"}
WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="Requires current-user Windows DPAPI")


@WINDOWS
def test_native_dpapi_encrypts_and_authenticates_connection_and_ciphertext():
    key = "disposable-test-key-\u6d4b\u8bd5"
    first = encrypt_api_key(key, CONNECTION)
    second = encrypt_api_key(key, CONNECTION)
    assert first != second
    assert decrypt_api_key(first, CONNECTION) == key
    assert decrypt_api_key(first, {**CONNECTION, "model": "another-model"}) == key
    assert key not in json.dumps(first)
    assert key.encode() not in base64.b64decode(first["ciphertext"])
    for field, value in (("base_url", "https://other.invalid"), ("provider", "other"), ("protocol", "other")):
        with pytest.raises(CredentialProtectionError):
            decrypt_api_key(first, {**CONNECTION, field: value})
    raw = bytearray(base64.b64decode(first["ciphertext"]))
    raw[-1] ^= 1
    with pytest.raises(CredentialProtectionError):
        decrypt_api_key({**first, "ciphertext": base64.b64encode(raw).decode()}, CONNECTION)


@WINDOWS
def test_settings_restart_replace_clear_and_no_plaintext_files(tmp_path):
    path = tmp_path / "settings.json"
    values = {**defaults(), "font_size": 16, "debug_console_enabled": True}
    for key in ("first-disposable-key", "second-disposable-key"):
        save_preferences(path, values, CONNECTION, api_key=key)
        loaded = load_settings(path)
        assert loaded.preferences == values and loaded.connection == CONNECTION
        assert loaded.api_key == key and not loaded.warning
        assert key not in repr(loaded)
        for file in tmp_path.iterdir():
            assert key not in file.read_text(encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8"))['version'] == 2
    save_preferences(path, values, CONNECTION, api_key="")
    assert "credentials" not in json.loads(path.read_text(encoding="utf-8"))
    assert load_settings(path).api_key == ""


@WINDOWS
def test_decrypt_failure_retains_public_settings_and_sanitized_traceback(tmp_path, caplog):
    path = tmp_path / "settings.json"
    key = "disposable-secret-never-log"
    save_preferences(path, {**defaults(), "font_size": 15}, CONNECTION, api_key=key)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["connection"]["base_url"] = "https://different.invalid"
    path.write_text(json.dumps(data), encoding="utf-8")
    original = path.read_bytes()
    loaded = load_settings(path)
    assert loaded.preferences["font_size"] == 15 and loaded.connection == data["connection"]
    assert loaded.api_key == "" and "重新输入" in loaded.warning
    assert path.read_bytes() == original
    assert "Traceback" in caplog.text and "DPAPI" in caplog.text
    assert key not in caplog.text


@pytest.mark.parametrize("record", [None, "raw-secret", {}, {"version": 1, "scheme": "plaintext"},
    {"version": 1, "scheme": "windows-dpapi-current-user", "ciphertext": "%%%"},
    {"version": True, "scheme": "windows-dpapi-current-user", "ciphertext": "YWJj"}])
def test_malformed_ciphertext_never_enters_error_message(record):
    with pytest.raises(CredentialProtectionError) as error:
        decrypt_api_key(record, CONNECTION)
    assert "raw-secret" not in str(error.value)


def test_unsupported_system_cannot_downgrade_to_plaintext(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), CONNECTION)
    previous = path.read_bytes()
    monkeypatch.setattr("promptsmith.credentials.sys.platform", "unsupported")
    with pytest.raises(CredentialProtectionError, match="DPAPI"):
        save_preferences(path, {**defaults(), "font_size": 15}, CONNECTION, api_key="temporary-disposable-key")
    assert path.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


def test_malformed_credentials_keep_preferences_and_can_be_cleared(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"preferences": {"font_size": 16}, "connection": CONNECTION,
                                "credentials": "broken"}), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.preferences["font_size"] == 16 and loaded.api_key == ""
    assert "重新输入" in loaded.warning
    save_preferences(path, loaded.preferences, loaded.connection)
    assert not load_settings(path).warning


@WINDOWS
def test_debug_toggle_preserves_ciphertext_connection_and_saved_values(tmp_path):
    path = tmp_path / "settings.json"
    save_preferences(path, {**defaults(), "font_size": 16}, CONNECTION, api_key="disposable-debug-key")
    original = json.loads(path.read_text(encoding="utf-8"))
    update_debug_preference(path, True)
    current = json.loads(path.read_text(encoding="utf-8"))
    assert current["credentials"] == original["credentials"]
    assert current["connection"] == original["connection"]
    assert current["preferences"]["font_size"] == 16
    assert load_settings(path).api_key == "disposable-debug-key"
    assert load_settings(path).preferences["debug_console_enabled"]


@WINDOWS
def test_atomic_failure_preserves_encrypted_key(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), CONNECTION, api_key="disposable-original-key")
    previous = path.read_bytes()
    with monkeypatch.context() as failure:
        failure.setattr("promptsmith.preferences.os.replace", lambda *_: (_ for _ in ()).throw(PermissionError("fixture")))
        with pytest.raises(PermissionError):
            save_preferences(path, {**defaults(), "font_size": 15}, CONNECTION, api_key="disposable-replacement-key")
    assert path.read_bytes() == previous
    assert load_settings(path).api_key == "disposable-original-key"
    assert not list(tmp_path.glob("*.tmp"))


def test_debug_toggle_cannot_overwrite_broken_settings(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("broken", encoding="utf-8")
    previous = path.read_bytes()
    with pytest.raises(ValueError):
        update_debug_preference(path, True)
    assert path.read_bytes() == previous
