#!/usr/bin/env python3
"""对比相邻两轮真实请求体，找出导致缓存未命中的那个变化字节。

用法：python tmp/diff_bodies.py [capture_dir]
默认读 cache_capture/ 下由 capture_proxy.py 落盘的 *.body.json。
"""

# Windows 控制台默认 GBK，中文会乱码；强制 UTF-8 输出。
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import json
import sys
from pathlib import Path


def first_diff(a: str, b: str) -> tuple[int, str, str]:
    """返回第一个不同字符的位置和两侧上下文。"""
    limit = min(len(a), len(b))
    for i in range(limit):
        if a[i] != b[i]:
            lo = max(0, i - 160)
            return i, a[lo:i + 160], b[lo:i + 160]
    if len(a) != len(b):
        return limit, a[max(0, limit - 160):], b[max(0, limit - 160):]
    return -1, "", ""


def summarize(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "cache_capture")
    files = sorted(root.glob("*.body.json"))
    if len(files) < 2:
        print(f"{root} 下不足 2 个请求体（找到 {len(files)} 个）。先跑 capture_proxy.py 并正常用几轮。")
        return 1

    print(f"共 {len(files)} 个请求体\n")

    # 逐对比较：报告公共前缀长度与首个差异点
    for prev_path, cur_path in zip(files, files[1:]):
        prev_raw = prev_path.read_text(encoding="utf-8")
        cur_raw = cur_path.read_text(encoding="utf-8")
        prev = summarize(prev_path)
        cur = summarize(cur_path)
        if prev is None or cur is None:
            print(f"{prev_path.name} -> {cur_path.name}: 无法解析，跳过")
            continue

        # 顶层键对比
        keys_changed = set(prev) ^ set(cur)
        # 逐字段序列化后比较（保证键序一致再比）
        canon_prev = json.dumps(prev, ensure_ascii=False, sort_keys=True)
        canon_cur = json.dumps(cur, ensure_ascii=False, sort_keys=True)
        pos, lo, hi = first_diff(canon_prev, canon_cur)

        print(f"=== {prev_path.name}")
        print(f" -> {cur_path.name}")
        print(f"    公共前缀 {pos if pos >= 0 else len(canon_cur)} 字符 / 总计 {len(canon_cur)}")
        if keys_changed:
            print(f"    顶层键变化: {sorted(keys_changed)}")
        if pos >= 0:
            print(f"    >>> 首个差异位置 {pos}:")
            print(f"        prev: ...{lo}...")
            print(f"        cur : ...{hi}...")

        # 定位到具体字段：逐个顶层键比较
        for key in sorted(set(prev) & set(cur)):
            if json.dumps(prev[key], ensure_ascii=False, sort_keys=True) != json.dumps(cur[key], ensure_ascii=False, sort_keys=True):
                p = json.dumps(prev[key], ensure_ascii=False, sort_keys=True)
                c = json.dumps(cur[key], ensure_ascii=False, sort_keys=True)
                d, plo, chi = first_diff(p, c)
                print(f"    [字段 {key}] 长度 {len(p)} -> {len(c)}，首差 @{d}")
                print(f"        prev: ...{plo[:200]}...")
                print(f"        cur : ...{chi[:200]}...")
        print()

    # 缓存断点位置
    print("=== cache_control 断点位置（最后一个请求体）===")
    last = summarize(files[-1])
    if last:
        found = False
        for container in ("system", "tools", "messages"):
            val = last.get(container)
            if not isinstance(val, list):
                continue
            for idx, item in enumerate(val):
                if not isinstance(item, dict):
                    continue
                # system/tools：块自身可能直接带 cache_control
                if "cache_control" in item:
                    print(f"    {container}[{idx}]  ← 断点")
                    found = True
                # messages：content 是块列表
                content = item.get("content")
                if isinstance(content, list):
                    for bidx, b in enumerate(content):
                        if isinstance(b, dict) and "cache_control" in b:
                            print(f"    {container}[{idx}].content[{bidx}]  ← 断点")
                            found = True
        if not found:
            print("    （未发现 cache_control —— 客户端可能没有打分断点）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
