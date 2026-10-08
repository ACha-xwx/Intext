> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`verification/acceptance_20260929_demo_features/offline_runner_audit_20260929.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Fixed D1/D2 runner offline audit

Audit date: 2026-09-29 (Asia/Shanghai)

## Scope

This is a read-only audit of `scripts/run_fixed_d1_d2_real_check.py`, its offline test client, and retained evidence. No production code and no previous evidence files were changed.

## Findings

- `DemoRun` accepts `evidence_mode="offline_fixture"`, but only its Python API exposes that parameter. The CLI has no `--offline`, `--fixture`, or fixture-file option and always requires an API key before constructing a run.
- The supported offline execution is therefore the pytest path in `tests/test_fixed_demo_runner.py`, where `FixedClient` and `InvalidClient` are injected. This exercises the same workflow/state application and persistence interfaces, but does not make a CLI run or a model-content result.
- A CLI invocation with an empty stdin key terminates before creating evidence with `missing API key` and exit code `1`. This is the expected missing-credential failure, not an offline pass.
- `exit_code()` maps `completed` to `0`, `needs_review` to `2`, and all other statuses (including `failed`, `budget_exhausted`, and `completed_with_findings`) to `1`.

## Reproduction

From the project root:

```powershell
& '.venv/Scripts/python.exe' -m pytest -q tests/test_fixed_demo_runner.py
```

Observed: `14 passed in 2.59s`, exit code `0`.

The completed fixture cases are persisted under the retained test evidence directory:

```text
verification/runner_offline_final_20260929_023354_8b4db9/test_fixed_case_uses_full_prod0/D1/run_summary.json
verification/runner_offline_final_20260929_023354_8b4db9/test_fixed_case_uses_full_prod1/D2/run_summary.json
```

Both summaries report `status=completed`, `evidence_mode=offline_fixture`, five module calls, final confirmation, trial completion, save/reopen checks, and exported Markdown. The surrounding test evidence also includes failure, retry, budget, stale checkpoint, interrupted-call, and trial-failure cases; those retain non-success statuses as expected.

Credential boundary reproduction:

```powershell
'' | & '.venv/Scripts/python.exe' scripts/run_fixed_d1_d2_real_check.py --api-key-stdin --case D1
```

Observed: `missing API key`, exit code `1`, with no real-model evidence run.

## Conclusion and handoff

Offline state-machine and persistence coverage is reproducible through the focused pytest command and has a stable status/exit-code contract. A person needing a command-line offline walkthrough would need a separately approved fixture CLI mode; adding that is outside this audit and was intentionally not implemented. Until a runtime credential is supplied, D1/D2 real content checks remain blocked and must not be represented by the offline fixture evidence.
