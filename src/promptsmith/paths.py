from __future__ import annotations

import os
import sys
import logging
from threading import RLock
from pathlib import Path

LOG = logging.getLogger(__name__)
_migration_lock = RLock()


def application_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "Intext"
    return Path.home() / ".intext"


def migrate_legacy_application_data() -> None:
    """Rename the legacy directory before reading settings; never merge profiles."""
    target = application_data_dir()
    legacy = target.with_name("PromptSmith" if os.environ.get("LOCALAPPDATA") else ".promptsmith")
    with _migration_lock:
        if not legacy.exists():
            return
        try:
            if target.exists():
                if not target.is_dir():
                    raise OSError("Intext 数据路径已被同名文件占用。")
                if any(target.iterdir()):
                    LOG.warning("Intext data directory already populated; existing Intext data takes priority, legacy directory retained: %s", legacy)
                    return
                target.rmdir()
            LOG.info("Migrating application data directory: %s -> %s", legacy, target)
            legacy.rename(target)
            LOG.info("Application data directory migrated; settings, protected credentials and history retained")
        except OSError as exc:
            LOG.exception("Application data directory migration failed; original data retained")
            raise OSError("无法把旧应用数据迁移到 Intext，原数据已保留。请关闭旧版程序并检查目录权限后重试。") from exc


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
    raise FileNotFoundError("找不到 Intext 资源目录。")


def m1_asset_dir() -> Path:
    return resource_root() / "resources" / "prompts"


def m2_asset_dir() -> Path:
    return resource_root() / "resources" / "prompts"
