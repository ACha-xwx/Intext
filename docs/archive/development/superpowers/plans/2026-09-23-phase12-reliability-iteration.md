> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/plans/2026-09-23-phase12-reliability-iteration.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Phase 1-2 Reliability Iteration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing M1 requirement workflow preserve valid state on failure, bind confirmation to current content, apply candidate batches atomically, retain unresolved gaps and conflicts, expose review state, and provide a usable Tkinter review loop.

**Architecture:** Keep the existing `SessionState -> M1 validation/workflow -> Tkinter UI -> JSON storage` structure. Add small persisted state markers for the requirement version last covered by a successful analysis and candidate provenance; centralize requirement replacement, dependency review, gap reconciliation, and conflict reconciliation in `SessionState`. Treat a structurally valid `input_error` as a recorded business failure before state application. UI changes remain within the first tab and call the state model instead of owning business rules.

**Tech Stack:** Python 3.11, dataclasses, Tkinter/ttk, JSON Schema Draft 2020-12, pytest, PyInstaller directory mode.

---

### Task 1: Capture the reported failures as regression tests

**Files:**
- Modify: `tests/test_session.py`
- Modify: `tests/test_m1.py`
- Modify: `tests/test_workflow.py`
- Modify: `tests/test_storage.py`
- Modify: `tests/test_ui_contract.py`

- [x] Add focused tests for current-task confirmation, directional requirement removal, review IDs, stale response rejection, atomic proposal acceptance, duplicate acceptance, conflict preservation, gap retention and resolution, dependency cleanup, and round-trip state.
- [x] Add workflow/UI tests showing `input_error` preserves business state and is displayed as failure.
- [x] Add one complete UI path that edits the task, analyzes, accepts, reviews, confirms, saves, and reopens.
- [x] Run the new tests and confirm each fails for the behavior reported by acceptance review rather than a fixture error.

### Task 2: Make session state changes explicit and confirmation-safe

**Files:**
- Modify: `src/promptsmith/session.py`
- Test: `tests/test_session.py`, `tests/test_storage.py`

- [x] Add a persisted `analysis_basis_version` marker with backward-compatible loading defaults.
- [x] Separate manual semantic changes from accepting a model batch: task/category/edit/withdraw/answer invalidate the prior analysis basis; valid candidate acceptance advances the basis to the committed version.
- [x] Mark affected requirements `review_needed`, maintain `pending_review_item_ids`, and provide an explicit user review operation.
- [x] Require a current analysis basis, at least one directional requirement, no blocking gap/conflict/pending candidate/review item, and valid dependencies before confirmation.
- [x] Redirect or remove dependencies when a requirement is replaced or withdrawn, mark affected dependents for review, and prevent dangling references from being sent or saved as confirmable.
- [x] Keep skipped/unsure gaps unresolved; close an answered gap and remove a gap after a matching user-backed requirement is accepted.

### Task 3: Make candidate application atomic and conflict-aware

**Files:**
- Modify: `src/promptsmith/session.py`
- Test: `tests/test_session.py`

- [x] Attach request ID, source base version, and current valid version to staged candidates.
- [x] Prevalidate every selected ID, mutation target, duplicate target, dependency, and candidate version before changing live state.
- [x] Apply the whole batch to a deep working copy and commit only after all operations succeed.
- [x] Preserve a conflict when accepting a `new` candidate leaves the old conflicting requirement active; resolve it only when proposal dismissal or replace/withdraw/manual withdrawal leaves no contradictory pair.
- [x] Ensure a repeated click cannot create a duplicate requirement.

### Task 4: Separate valid JSON from successful M1 work

**Files:**
- Modify: `src/promptsmith/m1.py`
- Modify: `src/promptsmith/workflow.py`
- Modify: `src/promptsmith/runlog.py`
- Test: `tests/test_m1.py`, `tests/test_workflow.py`, `tests/test_runlog.py`

- [x] Reject missing `review_item_ids`, dangling active dependencies, and repeated skipped/unsure questions without new task context.
- [x] Merge old unresolved gaps with successful responses rather than treating omission as resolution.
- [x] Record `input_error`, transport, authentication, timeout, and invalid-response attempts with available latency/usage and explicit nulls for unavailable data.
- [x] Never call the normal state application path for `input_error`; remove only the pending request and preserve requirements, candidates, gaps, conflicts, review state, and question budget.

### Task 5: Improve the existing first-tab interaction

**Files:**
- Modify: `src/promptsmith/ui.py`
- Test: `tests/test_ui_contract.py`

- [x] Synchronize task/category controls before confirmation and saving.
- [x] Allow answering, skipping, or marking unsure while non-conflicting candidates remain as drafts; prevent a new analysis from silently overwriting untreated drafts.
- [x] Add explicit “review selected” behavior for requirements marked by `review_item_ids`.
- [x] Bind requirement, candidate, and question selection to a scrollable detail view showing full text, source quote, origin/type, strength, scope, dependencies, reason, options, and old/new values with Chinese labels.
- [x] Add a prominent Chinese next-step message for conflict, question, candidate review, requirement review, confirmation, and exhausted-budget states.

### Task 6: End-to-end verification, packaging, and handoff

**Files:**
- Modify: `scripts/run_ui_real_smoke.py` or create a deterministic offline UI-path script if needed
- Modify: `README.md`
- Modify: `docs/开发交接.md`
- Create: `docs/阶段一二可靠性迭代记录_20260923.md`
- Modify: `output/prompt/_design/acceptance_20260923/observed_results.json` only by rerunning its reproducer when compatible

- [x] Run the focused regression tests, a separate third-round acceptance verifier, the full pytest suite, and compile checks.
- [x] Run a complete Tk path through edit, answer, candidate review, confirmation, save, and reopen using a local deterministic response server.
- [ ] Run only feasible real-model checks using an explicitly available runtime key; otherwise list them as pending without creating simulated raw output.
- [x] Rebuild single-file `dist/PromptSmith.exe` and launch an isolated copy from `%TEMP%` with no sidecar dependencies.
- [x] Scan source/evidence for credential-shaped strings without printing matched content.
- [ ] Complete the three pending real-model checks when a runtime key is available.
- [x] Record fixed, partially fixed, and pending acceptance items and state whether M2 may begin.

## Scope Guard

Do not implement M2-M5, Skill search, online search, automatic Skill execution, or downstream task execution. Do not rewrite the competition plan, historical division-of-work files, existing prompt versions, or raw model evidence. Do not change M1 prompt text unless a verified content failure remains after program-state fixes.
