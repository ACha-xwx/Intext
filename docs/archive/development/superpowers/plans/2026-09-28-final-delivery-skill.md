> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/plans/2026-09-28-final-delivery-skill.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Final Delivery and Skill Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reliable post-M2 delivery loop that produces a complete no-Skill task prompt, optionally selects locally verified Skill methods, preserves user decisions through invalidation and save/reopen, and exports confirmed results.

**Architecture:** Keep M1/M2 contracts and workflows unchanged. Add a small delivery domain around `SessionState`, with deterministic finalization/render/export logic and a local catalog reader; optional M3/M4 model calls are isolated behind request snapshots and use the existing API/evidence infrastructure. The UI exposes the no-Skill path first and then the catalog/optional model paths, while all confirmation, versioning, and persistence remain program-controlled.

**Tech Stack:** Python 3.11, dataclasses, JSON Schema, Tkinter/ttk, existing API adapters, pytest, PyInstaller.

---

### Task 1: Record baseline and contracts

**Files:**
- Create: `output/prompt/_design/acceptance_20260928_final_delivery_run01/`
- Create: `output/prompt/_design/M3_M4字段映射与状态规则_v0.1.md`
- Modify: `docs/开发交接.md`, `output/prompt/_design/README.md`, `progress.md`, `task_plan.md`

- [ ] Record current source/resource/EXE hashes, current test result, known F1-F3 as deferred, and an S0-S8 checklist.
- [ ] Describe the authoritative fields, migration rules, request identity, and UI actions before implementing them.

### Task 2: Extend session state and migration

**Files:**
- Modify: `src/promptsmith/session.py`, `src/promptsmith/storage.py`
- Test: `tests/test_delivery_session.py`

- [ ] Add `promptsmith.session.v0.2` migration from v0.1 with `delivery_revision`, structured `skill_state`, extended `final_result`, and `final_archive` defaults.
- [ ] Add program-side invalidation and confirmation guards for task/plan/selection/final edits.
- [ ] Preserve legacy selected Skill strings as unresolved history and reject future/corrupt formats without overwriting files.

### Task 3: Deterministic finalization, rendering, and export

**Files:**
- Create: `src/promptsmith/finalization.py`, `src/promptsmith/prompt_render.py`, `src/promptsmith/exporter.py`
- Test: `tests/test_final_delivery.py`, `tests/test_exporter.py`

- [ ] Implement entry validation, deep-copy no-Skill assembly, canonical body rendering, neutral/polite wrappers, final confirmation, and stale handling.
- [ ] Preserve unknowns and pending suggestions as explicit sections; ensure tone changes do not change body or semantic revision.
- [ ] Implement atomic Markdown export with draft/final gates and no secret fields.

### Task 4: Local Skill catalog and deterministic matching

**Files:**
- Create: `resources/skill_catalog/catalog_v0.1.json`, `resources/skill_catalog/NOTICE.md`
- Create: `src/promptsmith/skill_catalog.py`
- Test: `tests/test_skill_catalog.py`

- [ ] Read and hash the three local source records (`to-spec`, `domain-modeling`, `goal-prompt`) and encode source, capabilities, prerequisites, adaptation boundaries, and license evidence.
- [ ] Implement catalog validation, snapshot hashes, keyword/tag matching, no-match and incompatible outcomes, and bounded candidate batches.

### Task 5: Optional M3/M4 structured paths

**Files:**
- Create: `src/promptsmith/m3.py`, `src/promptsmith/m4.py`, `src/promptsmith/delivery_workflow.py`
- Create: `output/prompt/_design/M3_input_v0.1.schema.json`, `M3_output_v0.1.schema.json`, `M3_system_v0.1.txt`, `M4_input_v0.1.schema.json`, `M4_output_v0.1.schema.json`, `M4_system_v0.1.txt`
- Test: `tests/test_m3_m4.py`, `tests/test_delivery_workflow.py`

- [ ] Validate candidate IDs, bindings, prerequisites, contributions, proposed changes, and multi-to-multi selection without mixing recommendation and user choice.
- [ ] Add prepare/invoke/apply request snapshots with session/connection/selection/delivery revisions and atomic apply.
- [ ] Keep model failures and late responses from changing business state.

### Task 6: UI, save/reopen, and end-to-end checkpoints

**Files:**
- Modify: `src/promptsmith/ui.py`, `src/promptsmith/paths.py`, `PromptSmith.spec`
- Test: `tests/test_ui_final_delivery.py`

- [ ] Enable the Skill and Export pages with explicit no-Skill, search, select/cancel, integrate, tone, copy, save, reopen, and export actions.
- [ ] Keep long previews selectable, scrollable, and bound to existing context menus/wheel routing.
- [ ] Exercise the complete no-Skill path and one Skill selection/cancellation path through actual Tk callbacks.

### Task 7: Regression, build, and handoff

**Files:**
- Create: `output/prompt/_design/acceptance_20260928_final_delivery_run01/` evidence and reports
- Modify: `docs/开发交接.md`, `output/prompt/_design/README.md`, `progress.md`, `findings.md`

- [ ] Run focused tests, full pytest, compileall, layout checks, source smoke, and the final EXE in-project and in a one-EXE directory.
- [ ] Record fixture-only versus real model checks, complete T01-T24 status, known F1-F3, and remaining cross-machine/DPI limitations.
- [ ] Verify no credentials or runtime API objects enter session/export/catalog resources.
