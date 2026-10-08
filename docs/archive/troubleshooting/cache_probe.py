#!/usr/bin/env python3
"""缓存命中特征探针：判定 read=0 是「路由问题」还是「请求内容问题」。

关键设计：
  - 反复发送**字节完全相同**的请求。若命中模式是「时好时坏」→ 路由/账号问题；
    若「永远命中」→ 路由正常，问题在真实请求的内容差异。
  - 每条请求带唯一 metadata.user_id 标记，便于在网关日志里按 session_hash 定位，
    不会和真实流量混淆。
  - PREFIX_MULT 控制规模，可调到与真实请求同量级（约 26 万 token）。

只读环境变量，不读配置文件，不回显令牌。
"""


from __future__ import annotations

# Windows 控制台默认 GBK，中文会乱码；强制 UTF-8 输出。
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
if BASE.endswith("/v1"):
    BASE = BASE[:-3]
TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
if not TOKEN:
    raise SystemExit("缺少 ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY")

MODEL = os.environ.get("PROBE_MODEL", "claude-fable-5-1")
AUTH = os.environ.get("PROBE_AUTH", "bearer").lower()
ITER = int(os.environ.get("PROBE_ITERATIONS", "6"))
MULT = int(os.environ.get("PREFIX_MULT", "400"))
STREAM = os.environ.get("PROBE_STREAM", "1") == "1"
GAP = float(os.environ.get("PROBE_GAP_SECONDS", "3"))
RUN_ID = os.environ.get("PROBE_RUN_ID") or time.strftime("cacheprobe-%Y%m%dT%H%M%S")

PREFIX = "You are a careful assistant. Reply with the single word OK.\n" + (
    "The quick brown fox jumps over the lazy dog. " * MULT
)

OUT = Path(os.environ.get("PROBE_DIR", "cache_probe_out"))
OUT.mkdir(exist_ok=True)


def headers() -> dict:
    h = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if AUTH in ("bearer", "both"):
        h["authorization"] = f"Bearer {TOKEN}"
    if AUTH in ("x-api-key", "both"):
        h["x-api-key"] = TOKEN
    return h


def body(iteration: int) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 64,
        "system": [
            {"type": "text", "text": PREFIX, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [{"role": "user", "content": "OK"}],
        "metadata": {"user_id": f"{RUN_ID}:{iteration}"},
        "stream": STREAM,
    }


def post(payload: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        f"{BASE}/v1/messages",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers(),
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def usages(raw: str) -> list[dict]:
    """同步取 body.usage；流式遍历 message_start / message_delta，两处都收。"""
    out: list[dict] = []
    try:
        u = json.loads(raw).get("usage")
        if isinstance(u, dict):
            return [u]
    except json.JSONDecodeError:
        pass
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if p in ("", "[DONE]"):
            continue
        try:
            ev = json.loads(p)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "message_start":
            u = (ev.get("message") or {}).get("usage")
            if isinstance(u, dict):
                out.append(u)
        elif ev.get("type") == "message_delta" and isinstance(ev.get("usage"), dict):
            out.append(ev["usage"])
    return out


def pick(u_list: list[dict]) -> dict | None:
    """同一请求里多处 usage 取 read 最大的那条（最终账目）。"""
    best = None
    for u in u_list:
        if best is None or (u.get("cache_read_input_tokens") or 0) > (
            best.get("cache_read_input_tokens") or 0
        ):
            best = u
    return best


def main() -> int:
    print(f"run_id      = {RUN_ID}")
    print(f"model       = {MODEL}   base = {BASE}   auth = {AUTH}")
    print(f"stream      = {STREAM}  iterations = {ITER}  gap = {GAP}s")
    print(f"prefix      = {len(PREFIX.encode())} bytes (~{len(PREFIX.encode())//4} tokens)")
    print(f"落盘目录    = {OUT.resolve()}\n")

    rows = []
    for i in range(1, ITER + 1):
        status, raw = post(body(i))
        (OUT / f"{RUN_ID}_{i:02d}.raw.txt").write_text(raw, encoding="utf-8")
        u = pick(usages(raw)) if status == 200 else None
        row = {
            "iteration": i,
            "http": status,
            "input": (u or {}).get("input_tokens"),
            "read": (u or {}).get("cache_read_input_tokens"),
            "write": (u or {}).get("cache_creation_input_tokens"),
            "output": (u or {}).get("output_tokens"),
        }
        rows.append(row)
        print(
            f"[{i:02d}] http={status}  read={row['read']}  write={row['write']}  "
            f"input={row['input']}  out={row['output']}"
        )
        if status != 200:
            print("      body:", raw[:300])
        if i < ITER:
            time.sleep(GAP)

    (OUT / f"{RUN_ID}_summary.json").write_text(
        json.dumps({"run_id": RUN_ID, "model": MODEL, "rows": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    tail = [r for r in rows[1:] if r["http"] == 200]
    hits = [r for r in tail if (r["read"] or 0) > 0]
    print("\n===== 判定 =====")
    print(f"第 2..{ITER} 次中，命中 {len(hits)}/{len(tail)}")
    if not tail:
        verdict = "无有效样本，检查上面 http 状态码。"
    elif len(hits) == len(tail):
        verdict = (
            "字节完全相同的请求**每次都能命中** → 网关路由稳定，"
            "read=0 的原因在**真实请求的内容差异**。转到手册的『阶段 B：抓取真实请求体』。"
        )
    elif hits:
        verdict = (
            "命中**时有时无** → 高度指向**上游账号/缓存分片切换**（缓存不跨账号共享）。"
            "把本结果连同 run_id 交给 ccmax 管理员核实其内部账号池。"
        )
    else:
        verdict = (
            "字节完全相同的请求**一次都没命中** → 与之前两轮探针的结论矛盾，"
            "需检查本轮环境（base_url / 模型名 / 是否被改写）是否与之前一致。"
        )
    print(verdict)
    print(f"\n把 {RUN_ID}_summary.json 交回即可，原始响应在同目录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
