# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


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
    (str(prompt_dir / "M1_input_v0.4.schema.json"), "resources/prompts"),
    # Keep the legacy loader usable in a single-file build for old sessions and
    # compatibility checks; the normal path loads the v0.18 base plus the
    # current v0.22 judgment addendum above.
    (str(prompt_dir / "M1_system_v0.3.txt"), "resources/prompts"),
    (str(prompt_dir / "M1_input.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_output.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_input_v0.2.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M1_output_v0.2.schema.json"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.1.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.2.txt"), "resources/prompts"),
    (str(prompt_dir / "M2_system_v0.3.txt"), "resources/prompts"),
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
]

a = Analysis(
    [str(project / "run_promptsmith.py")],
    pathex=[str(project / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PromptSmith",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
