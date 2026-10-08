from __future__ import annotations

import os
import sys
from pathlib import Path


def application_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "PromptSmith"
    return Path.home() / ".promptsmith"


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "resources" / "prompts" / "M1_system_v0.5.txt").exists():
            return candidate
    override = os.environ.get("PROMPTSMITH_RESOURCE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    raise FileNotFoundError("找不到PromptSmith资源目录。")


def m1_asset_dir() -> Path:
    return resource_root() / "resources" / "prompts"


def m2_asset_dir() -> Path:
    return resource_root() / "resources" / "prompts"
