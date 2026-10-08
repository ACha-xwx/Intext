#!/usr/bin/env python3
"""透传代理：把真实 Claude Code 请求体原样落盘，供后续 diff。

用法：
    1. 启动：python tmp/capture_proxy.py
    2. 把客户端指向它：export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
    3. 正常用几轮（至少 2-3 轮，让前缀有机会命中）
    4. 停止，运行 tmp/diff_bodies.py

上游地址从 UPSTREAM 环境变量取，默认 https://api.changqiu.top。
只落请求体，不落令牌；Authorization 头只记录“是否存在”。
"""

# Windows 控制台默认 GBK，中文会乱码；强制 UTF-8 输出。
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import http.client
import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UPSTREAM = os.environ.get("UPSTREAM", "https://api.changqiu.top").rstrip("/")
PORT = int(os.environ.get("PROXY_PORT", "8787"))
OUT = Path(os.environ.get("CAPTURE_DIR", "cache_capture"))
OUT.mkdir(exist_ok=True)

LOCK = threading.Lock()
COUNTER = {"n": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        # 落盘请求体（仅 /v1/messages 之类有 JSON 的 POST）
        if body and self.command == "POST":
            with LOCK:
                COUNTER["n"] += 1
                n = COUNTER["n"]
            stamp = time.strftime("%Y%m%dT%H%M%S")
            (OUT / f"{n:03d}_{stamp}_{self.path.strip('/').replace('/', '_')}.body.json").write_bytes(body)

        parsed = urllib.parse.urlsplit(UPSTREAM)
        conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(parsed.netloc, timeout=600)

        headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        target = (parsed.path.rstrip("/") + self.path) if parsed.path else self.path
        conn.request(self.command, target, body=body, headers=headers)

        resp = conn.getresponse()
        self.send_response(resp.status)
        passthrough_skip = {"transfer-encoding", "connection", "content-length"}
        for k, v in resp.getheaders():
            if k.lower() not in passthrough_skip:
                self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        # 逐块透传，避免破坏流式体验
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        conn.close()

    do_POST = _forward
    do_GET = _forward

    def log_message(self, fmt, *args):  # 保持安静，只打到 stderr 会干扰
        pass


def main() -> None:
    print(f"代理监听 http://127.0.0.1:{PORT}  ->  上游 {UPSTREAM}")
    print(f"请求体落盘到 {OUT.resolve()}")
    print("把客户端 ANTHROPIC_BASE_URL 指到 http://127.0.0.1:%d 即可。" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
