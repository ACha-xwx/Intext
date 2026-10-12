"""Desktop settings with public preferences and separately protected credentials."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from .credentials import CredentialProtectionError, decrypt_api_key, encrypt_api_key


@dataclass(frozen=True)
class Preference:
    category: str
    label: str
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()


FIELDS = {
    "generation_timeout": Preference("模型", "生成 timeout（秒）", 120., 1, 1800),
    "connection_timeout": Preference("模型", "连接 / 模型列表 timeout（秒）", 15., 1, 300),
    "max_tokens": Preference("模型", "max_tokens（0 = 自动）", 0, 0, 262144),
    "temperature": Preference("模型", "temperature（auto / 留空 / 数值）", "auto"),
    "top_p": Preference("模型", "top_p（留空 = 不发送）", ""),
    "reasoning_effort": Preference("模型", "思考强度", "high", choices=("auto", "omit", "low", "medium", "high", "max")),
    "search_model_timeout": Preference("Skill 搜索", "筛选模型 timeout（秒）", 45., 1, 1800),
    "search_timeout": Preference("Skill 搜索", "每个联网来源 timeout（秒）", 45., 1, 300),
    "local_candidates": Preference("Skill 搜索", "本地正文粗查上限", 24, 1, 100),
    "shortlist_limit": Preference("Skill 搜索", "名称 / 描述初筛上限", 12, 1, 40),
    "review_limit": Preference("Skill 搜索", "AI 内容核验上限", 8, 1, 20),
    "display_limit": Preference("Skill 搜索", "默认展示推荐数量", 6, 1, 20),
    "network_candidates": Preference("Skill 搜索", "每个联网来源收集上限", 8, 1, 24),
    "network_cache_seconds": Preference("Skill 搜索", "联网来源缓存秒数（0 = 不复用）", 900, 0, 86400),
    "input_budget": Preference("Skill 搜索", "AI 筛选累计输入字符上限", 60000, 8000, 200000),
    "excerpt_chars": Preference("Skill 搜索", "每项 Skill 正文节选字符上限", 4000, 500, 12000),
    "extra_skill_roots": Preference("Skill 搜索", "额外本地 Skill 目录（每行一个）", ""),
    "skill_search_url": Preference("Skill 搜索", "Skill 索引地址", "https://skills.sh"),
    "web_search_url": Preference("Skill 搜索", "网页检索地址（含 {query}）", "https://www.bing.com/search?format=rss&q={query}"),
    "window_width": Preference("界面", "启动窗口宽度（保持 16:9）", 1440, 960, 2560),
    "font_size": Preference("界面", "字号基准（pt，显示为125%）", 12, 9, 18),
    "composer_theme": Preference("界面", "输入区与模型菜单主题", "light", choices=("light", "dark")),
    "default_thinking": Preference("会话与导出", "新会话思考深度", "standard", choices=("quick", "standard", "deep")),
    "default_tone": Preference("会话与导出", "默认交付语气", "neutral", choices=("neutral", "polite")),
    "session_directory": Preference("会话与导出", "会话保存目录（留空 = 默认）", ""),
    "export_directory": Preference("会话与导出", "Markdown 导出目录（留空 = 默认）", ""),
    "debug_level": Preference("诊断", "控制台默认显示级别", "全部", choices=("全部", "INFO 及以上", "WARN 及以上", "ERROR 及以上", "CRITICAL")),
    "debug_autoscroll": Preference("诊断", "控制台自动滚动", True),
    "debug_history": Preference("诊断", "控制台缓存条数", 1500, 100, 20000),
    "debug_lines": Preference("诊断", "控制台显示行数上限", 6000, 500, 50000),
    "debug_console_enabled": Preference("诊断", "开启 Debug 控制台", False),
}
RETIRED_FONT_FIELDS = ("chinese_font", "latin_font", "split_fonts")
CONNECTION_FIELDS = {"provider", "protocol", "base_url", "model"}
MAX_SETTINGS_BYTES = 131072


@dataclass
class LoadedSettings:
    preferences: dict[str, Any]
    connection: dict[str, str]
    api_key: str = field(default="", repr=False)
    warning: str = ""
    has_debug_preference: bool = False
    model_confirmed: bool = False


def defaults() -> dict[str, Any]:
    return {key: spec.default for key, spec in FIELDS.items()}


def normalize_value(key: str, value: Any) -> Any:
    spec = FIELDS[key]
    try:
        if isinstance(spec.default, bool):
            if not isinstance(value, bool):
                raise ValueError
        elif isinstance(spec.default, (int, float)):
            if isinstance(value, bool):
                raise ValueError
            number = float(value)
            if not math.isfinite(number) or not spec.minimum <= number <= spec.maximum:
                raise ValueError
            if isinstance(spec.default, int):
                if not number.is_integer():
                    raise ValueError
                value = int(number)
            else:
                value = number
        else:
            if not isinstance(value, str) or len(value) > 16384:
                raise ValueError
            value = value.strip()
            if spec.choices and value not in spec.choices:
                raise ValueError
            if key in {"temperature", "top_p"} and value and not (key == "temperature" and value == "auto"):
                number = float(value)
                if not math.isfinite(number) or not 0 <= number <= (2 if key == "temperature" else 1):
                    raise ValueError
            if key in {"skill_search_url", "web_search_url"}:
                validate_public_url(value)
                if key == "web_search_url" and "{query}" not in value:
                    raise ValueError
        return value
    except (TypeError, ValueError, OverflowError) as exc:
        bounds = f"，范围 {spec.minimum:g}–{spec.maximum:g}" if spec.minimum is not None else ""
        raise ValueError(f"{spec.label}的值无效{bounds}。") from exc


def validate_public_url(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("地址必须为不含账号密码的 HTTP(S) URL。")
    if any(key in value.casefold() for key in ("api_key=", "apikey=", "token=", "secret=", "password=")):
        raise ValueError("地址中不能包含凭据。")


def validate_preferences(values: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: normalize_value(key, values.get(key, spec.default)) for key, spec in FIELDS.items()}
    if result["review_limit"] > result["shortlist_limit"]:
        raise ValueError("AI 内容核验上限不能大于名称 / 描述初筛上限。")
    return result


def _read_document(path: Path) -> dict:
    if path.stat().st_size > MAX_SETTINGS_BYTES:
        raise ValueError("Settings file is too large")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Settings must be an object")
    return document


def _load_public(document: dict) -> tuple[dict[str, Any], dict[str, str]]:
    result, connection = defaults(), {}
    values = document.get("preferences", {})
    if not isinstance(values, dict):
        raise ValueError("Invalid preferences")
    if "trial_tokens" in values:
        logging.getLogger(__name__).debug("Ignored retired prompt execution preference")
    retired = [key for key in RETIRED_FONT_FIELDS if key in values]
    if retired:
        logging.getLogger(__name__).debug("Ignored retired custom font preferences: fields=%s; using Tk platform defaults", retired)
    for key in FIELDS:
        if key in values:
            try:
                result[key] = normalize_value(key, values[key])
            except ValueError:
                logging.getLogger(__name__).warning("Invalid preference %s; using default", key, exc_info=True)
    if result["review_limit"] > result["shortlist_limit"]:
        result["review_limit"] = min(8, result["shortlist_limit"])
    raw = document.get("connection", {})
    if isinstance(raw, dict):
        connection = {k: v for k, v in raw.items() if k in CONNECTION_FIELDS and isinstance(v, str) and len(v) < 4096}
        if connection.get("base_url"):
            try:
                validate_public_url(connection["base_url"])
            except ValueError:
                logging.getLogger(__name__).warning("Saved connection URL is invalid; ignoring connection", exc_info=True)
                connection = {}
    return result, connection


def load_settings(path: Path, *, restore_credentials: bool = True) -> LoadedSettings:
    try:
        document = _read_document(path)
        preferences, connection = _load_public(document)
    except FileNotFoundError:
        return LoadedSettings(defaults(), {})
    except (OSError, ValueError):
        logging.getLogger(__name__).warning("Cannot load desktop preferences; using defaults", exc_info=True)
        return LoadedSettings(defaults(), {}, warning="设置文件无法读取，已使用默认值。请在设置页重新保存。")
    loaded = LoadedSettings(preferences, connection,
                            has_debug_preference="debug_console_enabled" in document.get("preferences", {}))
    if restore_credentials and "credentials" in document:
        try:
            credentials = document["credentials"]
            if not isinstance(credentials, dict):
                raise CredentialProtectionError("已保存的凭据结构无效。")
            if "api_key" in credentials:
                loaded.api_key = decrypt_api_key(credentials["api_key"], connection)
                logging.getLogger(__name__).info("Saved API Key restored with current-user DPAPI")
        except CredentialProtectionError:
            logging.getLogger(__name__).warning("Cannot restore saved API Key; public settings retained", exc_info=True)
            loaded.warning = "API Key 无法解密，请在模型设置中重新输入并确认。其它设置已恢复。"
    confirmation = document.get("model_confirmation")
    if restore_credentials and confirmation is not None:
        try:
            fingerprint = _model_confirmation_fingerprint(document.get("preferences", {}), connection,
                                                           document.get("credentials", {}).get("api_key"))
            loaded.model_confirmed = (bool(loaded.api_key.strip()) and isinstance(confirmation, dict)
                                      and type(confirmation.get("version")) is int
                                      and confirmation["version"] == 1
                                      and confirmation.get("fingerprint") == fingerprint)
        except (ValueError, TypeError, AttributeError):
            logging.getLogger(__name__).warning("Cannot read saved model confirmation; reconfirm in settings", exc_info=True)
        if not loaded.model_confirmed:
            logging.getLogger(__name__).info("Saved model confirmation not restored: settings changed or credential unavailable")
            if not loaded.warning:
                loaded.warning = "已保存的模型确认与当前配置不符，请在设置页核对后点击“确认”。"
    elif restore_credentials:
        logging.getLogger(__name__).debug("No saved model confirmation; explicit confirmation required")
    # Check the saved confirmation against its original parameters first.
    # Migrate only pre-picker defaults; preserve explicitly saved newer choices.
    if document.get("composer_defaults") != 1 and preferences["reasoning_effort"] in {"auto", "omit"}:
        preferences["reasoning_effort"] = "high"
        logging.getLogger(__name__).info("Legacy thinking default migrated to High; confirmed interface retained=%s", loaded.model_confirmed)
    return loaded


def load_preferences(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    loaded = load_settings(path, restore_credentials=False)
    return loaded.preferences, loaded.connection


def _model_confirmation_fingerprint(values: Mapping[str, Any], connection: Mapping[str, str], credential: object) -> str:
    """Bind approval to public model options and encrypted credentials, never the plaintext key."""
    basis = {"connection": {key: connection.get(key, "").strip() for key in CONNECTION_FIELDS},
             "parameters": {key: normalize_value(key, values.get(key, spec.default))
                            for key, spec in FIELDS.items() if spec.category == "模型"},
             "credential": credential}
    content = json.dumps(basis, sort_keys=True, ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(b"PromptSmith.model_confirmation.v1\0" + content).hexdigest()


def save_preferences(path: Path, values: Mapping[str, Any], connection: Mapping[str, str], *, api_key: str = "",
                     model_confirmed: bool = False) -> None:
    values = validate_preferences(values)
    public = {k: v.strip() for k, v in connection.items() if k in CONNECTION_FIELDS and isinstance(v, str)}
    if public.get("base_url"):
        validate_public_url(public["base_url"])
    document = {"version": 2, "composer_defaults": 1, "preferences": values, "connection": public}
    if api_key.strip():
        document["credentials"] = {"api_key": encrypt_api_key(api_key.strip(), public)}
        if model_confirmed:
            document["model_confirmation"] = {"version": 1, "fingerprint": _model_confirmation_fingerprint(
                values, public, document["credentials"]["api_key"])}
    _write_document(path, document)
    logging.getLogger(__name__).debug("Settings written atomically; encrypted API Key present=%s", bool(api_key.strip()))
    logging.getLogger(__name__).info("Model confirmation saved with settings: confirmed=%s", "model_confirmation" in document)


def update_debug_preference(path: Path, enabled: bool) -> None:
    """Persist just the window toggle without reading a credential or UI draft."""
    if not isinstance(enabled, bool):
        raise ValueError("Debug console preference must be boolean")
    try:
        document = _read_document(path)
    except FileNotFoundError:
        document = {"version": 2, "preferences": defaults(), "connection": {}}
    values = document.setdefault("preferences", {})
    if not isinstance(values, dict):
        raise ValueError("Invalid saved preferences; save settings to repair the file")
    values["debug_console_enabled"] = enabled
    for key in ("trial_tokens", *RETIRED_FONT_FIELDS):
        values.pop(key, None)
    document["version"] = 2
    _write_document(path, document)


def _write_document(path: Path, document: dict) -> None:
    content = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(content.encode("utf-8")) > MAX_SETTINGS_BYTES:
        raise ValueError("设置文件过大，请缩短目录或其它文本设置后重试。")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".settings-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
