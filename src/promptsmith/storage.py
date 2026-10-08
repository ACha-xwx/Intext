from __future__ import annotations

import json
import os
from pathlib import Path

from .session import SessionState


def save_session(session: SessionState, path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    payload = json.dumps(session.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


def load_session(path: str | Path) -> SessionState:
    source = Path(path).expanduser().resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("会话文件根节点必须是JSON对象。")
    return SessionState.from_dict(data)
