import json
from dataclasses import FrozenInstanceError

import pytest

from promptsmith.api import ApiConfig, ApiResult, client_for_config
from promptsmith.preferences import defaults, load_preferences, save_preferences, validate_preferences


def test_preferences_roundtrip_omits_credentials_and_unknown_fields(tmp_path):
    path = tmp_path / "settings.json"
    values = {**defaults(), "generation_timeout": 240, "temperature": "0.3", "extra_skill_roots": "D:/skills\nE:/skills"}
    save_preferences(path, {**values, "api_key": "private"}, {"model": "example", "api_key": "private", "github_token": "private"})
    loaded, connection = load_preferences(path)
    assert loaded["generation_timeout"] == 240
    assert loaded["temperature"] == "0.3"
    assert loaded["extra_skill_roots"] == values["extra_skill_roots"]
    assert connection == {"model": "example"}
    assert "private" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("key,value", [("max_tokens", -1), ("temperature", "nan"), ("top_p", "inf"),
    ("generation_timeout", 0), ("display_limit", 1.5), ("excerpt_chars", True),
    ("debug_autoscroll", "true"), ("reasoning_effort", "wrong"), ("window_width", 100)])
def test_invalid_values_do_not_replace_existing_settings(tmp_path, key, value):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), {})
    previous = path.read_bytes()
    with pytest.raises(ValueError):
        save_preferences(path, {**defaults(), key: value}, {})
    assert path.read_bytes() == previous


def test_partial_corruption_preserves_valid_preferences(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"preferences": {"font_size": 16, "generation_timeout": "nan", "shortlist_limit": 2}}), encoding="utf-8")
    loaded, _ = load_preferences(path)
    assert loaded["font_size"] == 16
    assert loaded["generation_timeout"] == 120
    assert loaded["review_limit"] == 2
    path.write_text("broken", encoding="utf-8")
    assert load_preferences(path) == (defaults(), {})


def test_budget_relationship_and_secret_urls():
    with pytest.raises(ValueError, match="核验"):
        validate_preferences({**defaults(), "shortlist_limit": 3})
    with pytest.raises(ValueError):
        validate_preferences({**defaults(), "web_search_url": "https://example.com?token=secret&q={query}"})


@pytest.mark.parametrize("protocol,limit_key,reasoning_key", [
    ("openai_chat_completions", "max_tokens", "reasoning_effort"),
    ("openai_responses", "max_output_tokens", "reasoning"),
    ("anthropic_messages", "max_tokens", "output_config"),
])
def test_custom_parameters_reach_json_and_text_requests(protocol, limit_key, reasoning_key):
    config = ApiConfig(base_url="https://example.invalid", model="fixture", api_key="private",
                       protocol=protocol, max_tokens=1234, temperature=.3, reasoning_effort="high", timeout_seconds=240)
    client = client_for_config(config)
    bodies = []
    client._post = lambda body: (bodies.append(body) or ApiResult("{}", 0, None, None, None))
    client.complete_json("system", {}, {"type": "object"})
    client.complete_text("system", "user", max_output_tokens=65)
    assert bodies[0][limit_key] == 1234
    assert reasoning_key in bodies[0]
    assert all(body["temperature"] == .3 for body in bodies)
    assert bodies[1][limit_key] == 65
    assert config.timeout_seconds == 240
    with pytest.raises(FrozenInstanceError):
        config.timeout_seconds = 20


@pytest.mark.parametrize("protocol", ["openai_chat_completions", "openai_responses", "anthropic_messages"])
def test_omit_sampling_and_explicit_top_p(protocol):
    client = client_for_config(ApiConfig(base_url="https://example.invalid", model="fixture", api_key="key",
                                         protocol=protocol, temperature=None, top_p=.8, reasoning_effort="omit"))
    bodies = []
    client._post = lambda body: (bodies.append(body) or ApiResult("{}", 0, None, None, None))
    client.complete_json("system", {}, {"type": "object"})
    assert "temperature" not in bodies[0]
    assert bodies[0]["top_p"] == .8
    assert "reasoning" not in bodies[0] and "reasoning_effort" not in bodies[0]
    assert "effort" not in bodies[0].get("output_config", {})


def test_messages_rejects_incompatible_sampling_before_request():
    with pytest.raises(ValueError, match="temperature"):
        ApiConfig(base_url="https://example.invalid", model="fixture", api_key="key", protocol="anthropic_messages", temperature=1.2)
    with pytest.raises(ValueError, match="只设置"):
        ApiConfig(base_url="https://example.invalid", model="fixture", api_key="key", protocol="anthropic_messages", temperature=.3, top_p=.7)


def test_atomic_write_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    save_preferences(path, defaults(), {})
    previous = path.read_bytes()
    monkeypatch.setattr("promptsmith.preferences.os.replace", lambda *args: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(PermissionError):
        save_preferences(path, {**defaults(), "font_size": 15}, {})
    assert path.read_bytes() == previous
    assert not list(tmp_path.glob(".settings-*.tmp"))


def test_cache_ttl_reuse_and_disabled_mode(monkeypatch):
    import promptsmith.skill_network_discovery as discovery
    discovery.clear_network_skill_cache()
    from promptsmith.skill_search import SkillSearchResult
    result = SkillSearchResult(query="test", status="no_match", candidates=[], batch_id="cache-test", catalog_hash="fixture")
    monkeypatch.setattr(discovery.time, "monotonic", lambda: 100.)
    discovery._store_source_result("fixture", result)
    monkeypatch.setattr(discovery.time, "monotonic", lambda: 105.)
    assert discovery._cached_source_result("fixture", 10).batch_id == "cache-test"
    assert discovery._cached_source_result("fixture", 0) is None
    key = dict(source="github", works=[], task_text="", queries=[], search_url="https://skills.sh", web_search_url="https://test.invalid")
    assert discovery._source_cache_key(**key, verification_cap=2) != discovery._source_cache_key(**key, verification_cap=8)
