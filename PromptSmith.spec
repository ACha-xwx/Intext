# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files


project = Path(SPECPATH)
prompt_dir = project / "resources" / "prompts"
datas = [
    (str(prompt_dir / "M1_system_v0.5.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.6.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.7.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.8.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.9.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.2.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_input_v0.3.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_output_v0.3.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.10.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.3.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.11.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.4.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.16.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.9.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.17.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.10.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.18.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.11.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.20.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.13.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.21.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.14.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.22.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.15.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.23.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.16.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.24.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.17.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_contract_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_system_v0.25.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_incremental_v0.18.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_input_v0.5.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_output_v0.4.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_input_v0.4.schema.json"), "resources/prompts"),
    # Keep the legacy loader usable in a single-file build for old sessions and
    # compatibility checks; the normal path loads the v0.18 base plus the
    # current v0.24 interview addendum above.
    (str(prompt_dir / "M1_system_v0.3.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_input.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_output.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_input_v0.2.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_output_v0.2.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.2.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.3.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.4.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.5.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.6.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_input_v0.2.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M2_input_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M2_output_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M2_output_v0.2.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M3_system_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M3_input_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M3_output_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M4_system_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M4_system_v0.2.txt"), "resources/prompts"),
    (str(prompt_dir / "M4_input_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M4_output_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M5_system_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M5_system_v0.2.txt"), "resources/prompts"),
    (str(prompt_dir / "M5_input_v0.1.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M5_output_v0.1.schema.json"), "resources/prompts"),
    (str(project / "resources" / "skill_catalog" / "catalog_v0.1.json"), "resources/skill_catalog"),
    (str(project / "resources" / "skill_catalog" / "NOTICE.md"), "resources/skill_catalog"),
    (str(project / "resources" / "skill_catalog" / "sources"), "resources/skill_catalog/sources"),
    (str(project / "resources" / "ui" / "model_icons"), "resources/ui/model_icons"),
    (str(project / "resources" / "ui" / "action_icons"), "resources/ui/action_icons"),
    (str(project / "resources" / "ui" / "workspace"), "resources/ui/workspace"),
]
datas += collect_data_files("webview")
# jsonschema imports this optional format checker when installed. Its parser
# reads a grammar at import time, including before a frozen window is created.
datas += collect_data_files("rfc3987_syntax", includes=["*.lark"])

a = Analysis(
    [str(project / "run_promptsmith.py")],
    pathex=[str(project / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["webview.platforms.winforms", "webview.platforms.edgechromium"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

bundle_mode = os.environ.get("INTEXT_BUNDLE_MODE", "onefile")
if bundle_mode not in {"onefile", "onedir"}:
    raise ValueError("INTEXT_BUNDLE_MODE must be onefile or onedir")

exe = EXE(
    pyz,
    a.scripts,
    a.binaries if bundle_mode == "onefile" else [],
    a.datas if bundle_mode == "onefile" else [],
    [],
    name="Intext",
    exclude_binaries=bundle_mode == "onedir",
    icon=str(project / "resources/ui/workspace/brand/intext.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    manifest=str(project / "resources" / "ui" / "PromptSmith.manifest"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if bundle_mode == "onedir":
    distribution = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="Intext")
