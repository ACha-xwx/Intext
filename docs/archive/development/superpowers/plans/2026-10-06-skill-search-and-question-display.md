> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/plans/2026-10-06-skill-search-and-question-display.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Skill Search and Complete Question Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local-first and optional GitHub Skill search with visible asynchronous states and mergeable candidates, and render each M1 follow-up question with all of its options and explanation in one complete context.

**Architecture:** Add a focused `skill_search.py` HTTP/normalization module. Keep local catalog matching as the source of local candidates, store search metadata and combined snapshots inside `SessionState.skill_state`, and use the existing UI executor/completion queue with a separate search token. Extend the Skill page controls and candidate source column without changing M3/M4 contracts. Build one formatted M1 question string from `text`, `options`, and `reason`, and render it through the existing wrapped reading widget.

**Tech Stack:** Python 3.11, urllib, Tkinter/ttk, pytest, existing SessionState and M3/M4 delivery workflow.

---

### Task 1: Network Skill Search Module

**Files:**
- Create: `src/promptsmith/skill_search.py`
- Test: `tests/test_skill_search.py`

- [ ] **Step 1: Write failing tests** for query construction, GitHub JSON normalization, empty results, HTTP errors, malformed JSON, and deduplication metadata. Patch `skill_search.urlopen` with deterministic responses so no external request is made.
- [ ] **Step 2: Run `pytest tests/test_skill_search.py -q` and confirm failures** because the module and result types do not yet exist.
- [ ] **Step 3: Implement** `SkillSearchError`, `NetworkSkillSearchResult`, `build_skill_query`, `search_github_repositories`, and `merge_candidates`. Use `urllib.request.Request`, `Accept: application/vnd.github+json`, a short timeout, and a configurable endpoint from `PROMPTSMITH_SKILL_SEARCH_URL` with `https://api.github.com/search/repositories` as default. Normalize only valid repository rows into M3-compatible candidates with `method_adaptation_allowed=True`, `selection_allowed=True`, `verification_status="network_unverified"`, repository URL, retrieval timestamp, and an immutable raw metadata snapshot; never store credentials.
- [ ] **Step 4: Run the focused tests and make them pass.**

### Task 2: Persist Search State and Combined Candidate Batch

**Files:**
- Modify: `src/promptsmith/session.py`
- Test: `tests/test_skill_search_state.py`

- [ ] **Step 1: Write failing tests** for default/migrated `search_state`, preserving it through `set_skill_state`, and combined batch hashes that change when network metadata changes.
- [ ] **Step 2: Run `pytest tests/test_skill_search_state.py -q` and confirm failures.**
- [ ] **Step 3: Implement** nested `search_state` metadata (`status`, `local`, `network`, `last_error`, `updated_at`) in `_default_skill_state` and `_migrate_skill_state`; preserve it in `set_skill_state` and add a small validated setter/helper if needed. Keep existing delivery statuses and M3/M4-required `catalog_hash` fields intact.
- [ ] **Step 4: Run the focused state tests and existing session tests.**

### Task 3: Skill Page Async Search and Mixed Selection

**Files:**
- Modify: `src/promptsmith/ui.py`
- Modify: `src/promptsmith/guided_flow.py`
- Test: `tests/test_ui_skill_search.py`

- [ ] **Step 1: Write failing Tk tests** for local searching/progress, network opt-in, success/no-match/error status, stale completion rejection, source column rendering, and selecting both local and network candidates.
- [ ] **Step 2: Run the focused UI tests and confirm failures.**
- [ ] **Step 3: Add Skill controls** for local lookup and explicit network lookup, register widget names, and add a source column/detail text. Use `_submit` with a `_skill_search_request` token and `skill_search_busy` flag; disable lookup/selection buttons while the corresponding request is active and update `skill_status_var` before and after completion.
- [ ] **Step 4: Refactor `find_skills`** into an asynchronous local operation that loads/matches the catalog in the worker, merges into a batch, and records `search_state` and human-readable status. Add `search_online_skills` using the network module and merge/deduplicate into the existing batch. Preserve old candidates on failures, allow retry, and retain the skip path.
- [ ] **Step 5: Update mixed candidate selection** to accept network candidates, preserve source metadata in bindings, and compute the combined batch hash. Keep M3/M4 request preparation unchanged except for the richer candidate snapshots.
- [ ] **Step 6: Run focused UI tests plus existing delivery/UI contract tests.**

### Task 4: Complete M1 Question Display

**Files:**
- Modify: `src/promptsmith/guided_flow.py`
- Test: `tests/test_question_display.py`

- [ ] **Step 1: Write failing tests** asserting a question such as `text="在学分部积分法之前，你已经学过下面哪些内容？"` renders its `options` and `reason` in the same `question_context_var`, and that no separate explanatory label is required.
- [ ] **Step 2: Run the focused test and confirm it fails** because only `text` is currently rendered.
- [ ] **Step 3: Implement** `_format_guided_question` and `_format_guided_questions`; include numbered questions, `可选内容：…`, and `确认原因：…` in one wrapped string. Replace the separate `draft_explanation_var` visual label with a single context display while keeping draft authorization data unchanged.
- [ ] **Step 4: Run focused question and guided-state tests.**

### Task 5: Verification and Documentation

**Files:**
- Modify: `CHANGELOG.md`
- Test: existing `tests/` suite

- [ ] **Step 1: Run the focused regression set:** `pytest tests/test_skill_search.py tests/test_skill_search_state.py tests/test_ui_skill_search.py tests/test_question_display.py tests/test_ui_contract.py tests/test_ui_delivery_interactions.py tests/test_guided_state.py -q`.
- [ ] **Step 2: Run the full suite:** `pytest -q` and fix only regressions caused by this feature.
- [ ] **Step 3: Run source smoke verification:** `\.venv\Scripts\python.exe run_promptsmith.py --smoke-test`.
- [ ] **Step 4: Update `CHANGELOG.md` with the user-visible behavior and test evidence; do not claim a rebuilt EXE unless a separate build is explicitly requested and completed.**
