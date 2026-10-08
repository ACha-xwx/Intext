> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`verification/acceptance_20260929_demo_features/build_verify_v08_20260929/report.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# M1 v0.8 Offline and EXE Verification

Date: 2026-09-29 (Asia/Shanghai)

This is offline source/build verification only. It contains no real model-call result and does not assess D1/D2 model content.

## Results

- Full offline suite: `393 passed in 59.95s` (`pytest.txt`).
- `compileall` for `src`, `scripts`, and `run_promptsmith.py`: exit code 0 (`compileall.txt`).
- Source UI smoke, `run_promptsmith.py --smoke-test`: exit code 0 (`source_smoke.txt`).
- PyInstaller single-file build using `scripts/build.ps1` and `PromptSmith.spec`: succeeded (`build.txt`). The archive listing confirms that M1 v0.8 and both M1 v0.2 schemas are bundled (`archive_contents.txt`).
- Project-directory EXE smoke: waited for process completion; exit code 0 (`exe_project_smoke.txt`).
- Isolated EXE smoke: copied the binary into a new directory containing only `PromptSmith.exe`, waited for process completion; exit code 0 (`exe_isolated_smoke.txt`).

## Artifact

- Path: `dist/PromptSmith.exe`
- Built: `2026-09-29 10:40:57 +08:00`
- Size: `13,713,523` bytes
- SHA-256: `132C963BEC1290137213087DA6672442A00255C4A4000816DE92C2AFA9B9F663`
- The isolated copy has the same SHA-256. Metadata is in `artifact_info.txt`.

## Evidence Scope

These checks establish offline tests, packaging, and startup smoke behavior on this machine. They do not establish real-model response quality, the D1/D2 end-to-end business flows, or operation on another computer.
