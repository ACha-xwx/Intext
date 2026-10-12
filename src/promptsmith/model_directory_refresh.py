"""Background startup directories; all profile and UI writes stay on the Tk thread."""
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import replace
import logging

from .api import ApiConfig, client_for_config
from .model_catalog import validate_model_provider
from .preferences import save_model_directory
from .task_scope import TaskScope


LOG = logging.getLogger(__name__)
PROTOCOLS = {"OpenAI Chat Completions": "openai_chat_completions",
             "OpenAI Responses": "openai_responses", "Anthropic Messages": "anthropic_messages"}


def directory_identity(connection, key):
    return tuple(connection.get(field, "").strip() for field in
                 ("provider", "protocol", "base_url", "model_provider")) + (key.strip(),)


class ModelDirectoryRefresh:
    def __init__(self, app):
        self.app = app
        self.executor = None
        self.pending = {}
        self.statuses = {}
        self.closed = False

    def _set_status(self, provider, text):
        if text:
            self.statuses[provider] = text
        else:
            self.statuses.pop(provider, None)
        if self.app.provider_var.get().strip() == provider:
            self.app.model_directory_status_var.set(text)

    def start(self):
        for provider, profile in tuple(self.app._provider_profiles.items()):
            if not profile.api_key.strip():
                continue
            try:
                validate_model_provider(profile.connection)
                config = ApiConfig(base_url=profile.connection.get("base_url", ""),
                    model=profile.connection.get("model") or "directory-only", api_key=profile.api_key,
                    provider=provider, protocol=PROTOCOLS[profile.connection["protocol"]],
                    model_provider=profile.connection.get("model_provider", ""),
                    timeout_seconds=profile.preferences["connection_timeout"])
            except (ValueError, KeyError):
                LOG.warning("Startup model directory skipped: provider=%s invalid saved configuration", provider, exc_info=True)
                self._set_status(provider, "无法自动获取模型列表，请核对接口配置后点击“获取模型”。")
                continue
            if self.executor is None:
                self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="model-directory")
            scope = TaskScope()
            self._set_status(provider, "正在自动获取模型列表，已有列表仍可使用。")
            LOG.info("Startup model directory scheduled: provider=%s cached_count=%s", provider, len(profile.model_ids))
            future = self.executor.submit(self._fetch, config, scope)
            self.pending[provider] = (scope, future)
            future.add_done_callback(lambda done, name=provider, saved=profile, owner=scope:
                                    self._queue_result(name, saved, owner, done))

    @staticmethod
    def _fetch(config, scope):
        with scope.activate():
            result = client_for_config(config).list_models()
            scope.check()
            return result

    def _queue_result(self, provider, profile, scope, future):
        try:
            outcome = (future.result(), None)
        except CancelledError:
            LOG.info("Startup model directory cancelled: provider=%s", provider)
            outcome = (None, None)
        except Exception as exc:
            LOG.exception("Startup model directory failed: provider=%s; cached directory retained", provider)
            outcome = (None, exc)
        self.app.completions.put((lambda value: self._complete(provider, profile, scope, value), outcome))

    def _complete(self, provider, saved, scope, outcome):
        pending = self.pending.get(provider)
        if self.closed or scope.cancelled or pending is None or pending[0] is not scope:
            LOG.debug("Startup model directory result discarded: provider=%s cancelled_or_superseded=True", provider)
            return
        self.pending.pop(provider)
        app = self.app
        active = app.provider_var.get().strip() == provider
        current = app._provider_profiles.get(provider)
        connection = app._public_model_connection() if active else current.connection if current else {}
        key = app.api_key_var.get() if active else current.api_key if current else ""
        if not current or directory_identity(connection, key) != directory_identity(saved.connection, saved.api_key):
            self._set_status(provider, "")
            LOG.debug("Startup model directory result discarded: provider=%s configuration_changed=True", provider)
            return
        result, error = outcome
        if error is not None:
            self._set_status(provider, app.runtime_log.redact(f"自动获取模型列表失败：{error}。已有列表保留，可点击“获取模型”重试。"))
            return
        ids = tuple(result.model_ids)
        app._provider_profiles[provider] = replace(current, model_ids=ids)
        if active:
            app.widgets["api_model_combo"].configure(values=ids)
        try:
            persisted = save_model_directory(app._preferences_path, saved.connection, saved.api_key, ids)
        except (OSError, ValueError):
            persisted = False
            LOG.exception("Startup model directory usable in memory but could not be saved: provider=%s", provider)
        text = f"已自动获取 {len(ids)} 个模型。" if ids else "供应商返回空模型列表，可手动填写模型 ID。"
        if not persisted:
            text += "列表暂未保存，可点击“获取模型”重试。"
        self._set_status(provider, text)
        LOG.info("Startup model directory ready: provider=%s count=%s latency_ms=%s persisted=%s",
                 provider, len(ids), result.latency_ms, persisted)

    def supersede(self, provider):
        pending = self.pending.pop(provider, None)
        self._set_status(provider, "")
        if pending:
            pending[0].cancel()
            pending[1].cancel()
            LOG.info("Startup model directory superseded: provider=%s", provider)

    def close(self, *, wait):
        if self.closed:
            return
        self.closed = True
        for provider in tuple(self.pending):
            self.supersede(provider)
        if self.executor:
            self.executor.shutdown(wait=wait, cancel_futures=True)
        LOG.debug("Startup model directory worker closed")
