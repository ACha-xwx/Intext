> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/specs/2026-10-07-parallel-skill-search-design.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Parallel Skill Search Design

## Goal

Make network Skill discovery resilient when `skills.sh` is large or slow. The
index, GitHub, and open web sources should run independently, each with its
own timeout, so one slow source cannot consume the budget of the others.

## Architecture

`skill_network_discovery.search_network_skill_candidates` generates the query
set once, then submits three source jobs to a small thread pool:

1. the configured Skill index, without the implicit GitHub supplement;
2. the GitHub repository search and SKILL.md verifier;
3. the open web adapter.

The existing source adapters keep their provenance and validation rules. Each
source receives the same per-source budget (the UI timeout is interpreted as a
per-source timeout), and each source verifies at most eight candidates. Results
are merged by source URL/content hash and sent to the existing AI selector.
Successful source results are cached in memory for fifteen minutes using the
source, URL, query set, task works, and content policy as the key. Errors are
never cached.

## Status and failure handling

Diagnostics record each source's status, elapsed time, discovered count,
verified count, and error. A timeout or failure from one source is reported as
partial source failure while candidates from other sources remain selectable.
Only when all three sources fail and no result exists is the operation raised
as a network error.

## Verification

Tests cover parallel execution, independent timeouts, source isolation,
verification caps, cache reuse, and diagnostic output. Existing indexed and
open-web source tests remain valid.
