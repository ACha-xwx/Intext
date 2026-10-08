> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`verification/acceptance_20260929_demo_features/build_verify_v08_20260929_143747/report.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Build and Smoke Verification

Date: 2026-09-29 (Asia/Shanghai)

No business code was modified for this verification. This report covers the current shared workspace after the M1 v0.8 source freeze.

## Results

- `compileall` for `src`, `scripts`, and `run_promptsmith.py`: exit code 0 (`compileall.txt`).
- Source smoke (`.venv/Scripts/python.exe run_promptsmith.py --smoke-test`): exit code 0 (`source_smoke.txt`).
- Full offline suite: `395 passed in 77.60s` (`pytest.txt`).
- PyInstaller single-file build via `scripts/build.ps1`: exit code 0 (`build.txt`).
- Project-directory `dist/PromptSmith.exe --smoke-test`: process waited to completion, exit code 0 (`exe_project_smoke.txt`).
- Isolated directory containing only `PromptSmith.exe`: process waited to completion, exit code 0 (`exe_isolated_smoke.txt`).

## Artifact

- Path: `dist\PromptSmith.exe`
- Build output timestamp: `2026-09-29 14:37:47 +08:00` (see `artifact_info.txt`).
- Size: `13,717,311` bytes.
- SHA-256: `4490E5528D41A06ABA27CB3E28D280FE4BAA026148AFD9A08DE35673C69FA256`.
- Isolated copy SHA-256 matches the project binary; isolated directory contains exactly `PromptSmith.exe`.

This is local offline/package/startup evidence. It does not assess real-model content quality, D1/D2 business-chain completion, or another computer's runtime.
