"""Per-search HTTP compatibility, safe GitHub credentials and access fallback."""
from __future__ import annotations

from collections import OrderedDict
import logging
from threading import Lock
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .task_scope import check_cancelled

_LOG = logging.getLogger(__name__)
_WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 PromptSmith/0.1"
_CACHE_BYTES = 12_000_000


def github_api_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == "api.github.com"
                and parsed.port in {None, 443} and not parsed.username and not parsed.password)
    except ValueError:
        return False


def diagnostic_target(url: str) -> str:
    """Never include URL credentials, query values or fragments in diagnostics."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or "unknown"
        if ":" in host:
            host = "[" + host + "]"
        if parsed.port is not None:
            host += ":" + str(parsed.port)
        return urlunsplit((parsed.scheme, host, parsed.path[:240], "", ""))
    except ValueError:
        return "invalid-url"


def request_headers(url: str) -> dict[str, str]:
    headers = {"User-Agent": _WEB_UA}
    parsed = urlsplit(url)
    if github_api_url(url):
        headers.update(Accept="application/vnd.github+json", **{"X-GitHub-Api-Version": "2022-11-28"})
    elif parsed.hostname == "raw.githubusercontent.com" or parsed.path.lower().endswith(".md"):
        headers["Accept"] = "text/plain, text/markdown, */*;q=0.8"
    elif parsed.path == "/api" or "/api/" in parsed.path:
        headers["Accept"] = "application/json, */*;q=0.8"
    else:
        headers.update(Accept="text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
                       **{"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    return headers


class SkillRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            for name in ("Authorization", "Cookie", "Proxy-authorization"):
                redirected.remove_header(name)
            for name, value in request_headers(newurl).items():
                redirected.add_header(name, value)
            authorization = req.get_header("Authorization")
            if authorization and github_api_url(req.full_url) and github_api_url(newurl):
                redirected.add_unredirected_header("Authorization", authorization)
        return redirected


def http_access_error(url: str, status: int, headers=None, body: bytes = b""):
    from .skill_search import SkillSearchError
    headers = headers or {}
    remaining = headers.get("X-RateLimit-Remaining", "")
    text = body[:4096].decode("utf-8", errors="replace").casefold()
    rate_limited = status == 429 or (status == 403 and (
        str(remaining) == "0" or "rate limit" in text or "secondary rate" in text or "abuse detection" in text))
    if rate_limited:
        reason, hint = "rate_limit", "来源请求额度或频率受限，本轮暂停该入口并继续其他来源；可稍后重试。"
    elif status == 401:
        reason = "authentication"
        hint = ("GitHub 凭据无效或缺少权限；请检查 GitHub 凭据后重试，其他来源仍可使用。" if github_api_url(url)
                else "该来源需要授权，本轮继续使用其他来源；已有结果仍可选用。")
    elif status == 403 and any(marker in text for marker in ("cf-chl", "cloudflare", "captcha", "verify you are human")):
        reason, hint = "blocked", "来源要求人工验证，本轮暂停自动访问并继续其他来源。"
    elif status == 403:
        reason, hint = "forbidden", "来源拒绝自动访问或权限不足，本轮跳过该入口并继续其他来源。"
    elif status >= 500:
        reason, hint = "upstream_unavailable", "来源服务暂不可用，本轮跳过并继续其他来源；可稍后重试。"
    else:
        reason, hint = "http", "该来源读取失败，继续使用其他可用结果。"
    target = diagnostic_target(url)
    error = SkillSearchError("http", f"{target}（HTTP {status}）：{hint}", status)
    error.access_reason = reason
    error.target = target
    retry_after = str(headers.get("Retry-After", ""))
    error.retry_after = retry_after if retry_after.isdigit() and len(retry_after) <= 8 else ""
    error.rate_limit_remaining = str(remaining) if str(remaining).isdigit() else ""
    reset = str(headers.get("X-RateLimit-Reset", ""))
    error.rate_limit_reset = reset if reset.isdigit() else ""
    resource = str(headers.get("X-RateLimit-Resource", ""))
    path = urlsplit(url).path or "/"
    if reason in {"rate_limit", "authentication", "upstream_unavailable", "blocked"}:
        error.pause_prefix = "/search/" if github_api_url(url) and resource == "search" else (
            "/repos/" if github_api_url(url) and resource == "core" else "/")
    elif status == 403 and github_api_url(url) and path.startswith("/repos/"):
        error.pause_prefix = "/".join(path.split("/")[:4])
    else:
        # A single private file's 403 must not suppress an unrelated public file.
        error.pause_prefix = path
    return error


class SkillHttpSession:
    """A bounded, thread-safe cache and access pause lasting one user search."""
    def __init__(self, opener=None, token: str | None = None):
        self._opener = opener
        self._token = token.strip() if isinstance(token, str) else ""
        if self._token and (not self._token.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in self._token)):
            _LOG.warning("GitHub credential omitted: invalid HTTP header characters; continuing anonymously")
            self._token = ""
        self._default_opener = build_opener(SkillRedirectHandler())
        self._lock = Lock()
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._paused = {}
        self._requests = self._cache_hits = self._skipped = 0

    def _transport(self, request, timeout):
        if isinstance(request, str):
            request = Request(request, headers=request_headers(request), method="GET")
        if self._token and github_api_url(request.full_url):
            request.add_unredirected_header("Authorization", "Bearer " + self._token)
        open_fn = self._opener or self._default_opener.open
        try:
            return open_fn(request, timeout=timeout)
        except TypeError:
            return open_fn(request.full_url, timeout)

    def read(self, url: str, timeout: float, reader):
        check_cancelled()
        parsed = urlsplit(url)
        origin = (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        with self._lock:
            if url in self._cache:
                self._cache_hits += 1
                _LOG.debug("Skill HTTP cache reused: target=%s bytes=%d", diagnostic_target(url), len(self._cache[url]))
                return self._cache[url]
            for (blocked_origin, prefix), original in self._paused.items():
                path = parsed.path or "/"
                if origin == blocked_origin and (prefix == "/" or path == prefix or path.startswith(prefix.rstrip("/") + "/")):
                    from .skill_search import SkillSearchError
                    self._skipped += 1
                    error = SkillSearchError("http", f"{diagnostic_target(url)}：本轮该入口已暂停，继续使用其他来源。", original.status_code)
                    error.access_reason = getattr(original, "access_reason", "forbidden")
                    error.request_skipped = True
                    _LOG.debug("Skill HTTP access skipped: target=%s reason=%s", diagnostic_target(url), error.access_reason)
                    raise error
            self._requests += 1
        try:
            raw = reader(self._transport, url, timeout)
            check_cancelled()
        except Exception as exc:
            status = getattr(exc, "status_code", None) or 0
            if status in {401, 403, 429} or 500 <= status < 600:
                error = exc if hasattr(exc, "pause_prefix") else http_access_error(url, exc.status_code)
                with self._lock:
                    self._paused[(origin, error.pause_prefix)] = error
                _LOG.info("Skill HTTP endpoint paused for current search: target=%s reason=%s", diagnostic_target(url), error.access_reason)
            raise
        with self._lock:
            if url not in self._cache:
                self._cache[url] = raw
                self._cache_bytes += len(raw)
                while self._cache_bytes > _CACHE_BYTES or len(self._cache) > 64:
                    _, removed = self._cache.popitem(last=False)
                    self._cache_bytes -= len(removed)
        return raw

    def diagnostics(self):
        with self._lock:
            return {"requests": self._requests, "cache_hits": self._cache_hits, "skipped_requests": self._skipped,
                    "github_authenticated": bool(self._token), "access_issues": [
                        {"target": error.target, "reason": error.access_reason, "status_code": error.status_code,
                         "retry_after": error.retry_after, "rate_limit_remaining": error.rate_limit_remaining,
                         "rate_limit_reset": error.rate_limit_reset} for error in self._paused.values()]}
