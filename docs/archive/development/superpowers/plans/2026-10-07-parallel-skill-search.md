> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/plans/2026-10-07-parallel-skill-search.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Parallel Skill Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Run Skill index, GitHub, and open-web discovery in parallel with independent budgets and bounded verification so a slow `skills.sh` request does not hide usable results.

**Architecture:** Add source-selection flags and a verification cap to the existing indexed search adapter. Coordinate three source jobs in `skill_network_discovery.py` with `ThreadPoolExecutor`, per-source diagnostics, and a short-lived in-memory cache. Preserve the current AI review and UI contract.

**Tech Stack:** Python standard library (`concurrent.futures`, `threading`, `time`), existing Skill search adapters, pytest.

---

### Task 1: Lock the source isolation contract

**Files:**
- Modify: `tests/test_skill_network_discovery.py`

- [ ] **Step 1: Write failing tests** for three source calls, independent timeout values, cache reuse, and per-source diagnostics.
- [ ] **Step 2: Run the focused tests** and confirm they fail against the serial shared-deadline implementation.

### Task 2: Bound indexed and GitHub verification

**Files:**
- Modify: `src/promptsmith/skill_search.py`
- Modify: `tests/test_skill_search.py`

- [ ] **Step 1: Add `include_index`, `include_github_supplement`, and `max_verified_candidates` parameters.**
- [ ] **Step 2: Keep the default behavior compatible while allowing index-only and GitHub-only calls.**
- [ ] **Step 3: Cap source verification at eight records and expose the cap in diagnostics.**
- [ ] **Step 4: Run the focused source tests.**

### Task 3: Parallelize and cache network discovery

**Files:**
- Modify: `src/promptsmith/skill_network_discovery.py`
- Modify: `tests/test_skill_network_discovery.py`

- [ ] **Step 1: Add a bounded TTL cache for successful source results.**
- [ ] **Step 2: Submit index-only, GitHub-only, and open-web jobs concurrently with the configured timeout passed to each job.**
- [ ] **Step 3: Merge verified candidates, preserve successful results after partial failures, and report source diagnostics.**
- [ ] **Step 4: Run the focused discovery tests.**

### Task 4: Verify UI and build artifacts

**Files:**
- Modify: `tests/test_ui_skill_search.py` only if status expectations need updating.

- [ ] **Step 1: Run targeted Skill and UI tests.**
- [ ] **Step 2: Run `compileall` and the source smoke test.**
- [ ] **Step 3: Build a new staged EXE, run the offline release-chain verification, and record its SHA-256 and report path.**
