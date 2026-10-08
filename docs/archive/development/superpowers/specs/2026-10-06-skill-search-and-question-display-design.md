> 历史资料：仅用于追溯当时的设计与验证；当前状态以根目录 HANDOFF.md 为准。原始路径：`docs/superpowers/specs/2026-10-06-skill-search-and-question-display-design.md`。原始日志、截图及失效旧链接的查找方式见归档索引。

# Skill Search and Complete Question Display Design

Date: 2026-10-06

## Scope

After a confirmed initial plan, PromptSmith will search the local Skill catalog first and expose explicit progress states. The user may then opt into an online search. Online results use the GitHub public Repository Search API by default, with the endpoint kept configurable for future replacement. Local and online candidates share one selectable list and continue through the existing M3/M4 method-adaptation flow. No result is installed or executed automatically.

The M1 follow-up panel will present one complete question body. If the model supplies an explanation, choices, or examples needed to understand the question, they are appended to the same display text instead of being rendered as a separate explanatory paragraph.

## Data flow

1. The Skill page starts a background local lookup. The session records the source kind, query basis, status, candidate snapshot, and timestamps. UI states are `searching_local`, `local_ready`, `searching_network`, `ready`, `no_match`, and `search_error` while preserving the existing delivery statuses for compatibility.
2. Local lookup results are normalized into the existing candidate shape and retain catalog hashes and source verification metadata.
3. The user explicitly starts online lookup. A background HTTP request builds a concise query from confirmed task text and key work. GitHub results are normalized into method-adaptation candidates with repository URL, immutable API result snapshot, retrieval time, and `network_unverified` provenance. A network result is selectable for recommendation, but its snapshot states that it is uninstalled and unexecuted.
4. The combined batch stores separate local and network result metadata plus a deduplicated candidate list. Selecting candidates creates the same binding structure used by M3/M4. The batch hash covers both sources so late or stale responses are rejected.
5. Search failures and empty results remain actionable: the page explains the state, preserves prior candidates, allows retry, and keeps the skip path available.

## UI behavior

The Skill controls become: `查找本地 Skill`, `继续联网搜索`, `选择方法`, `AI分析候选`, `取消选用`, `全部跳过并生成最终草稿`, and `AI整合所选方法`. Buttons are disabled while their corresponding lookup is active. The status line always shows a human-readable state and count, for example `正在查找本地 Skill…`, `本地找到 2 项；可继续联网搜索`, `联网搜索完成：找到 4 项`, `未找到适用 Skill`, or `联网搜索失败：…`.

The candidate table adds a source column so local and network records are distinguishable. Network detail text includes the URL and retrieval timestamp. The existing provenance boundary is shown before selection and carried into the final method binding.

The M1 question panel uses one wrapped, scrollable text widget for the complete question context. The answer entry and controls remain below it. The previous separate explanation label is removed from the visual flow; the full text is derived from the question text plus any model explanation/choice text with stable separators.

## Error and concurrency handling

All local and online searches run through the existing `ThreadPoolExecutor` and completion queue. A search token and session/basis fingerprint guard every completion. If the user edits or replaces the confirmed plan while a request is in flight, the response is discarded and the current state remains intact. HTTP timeout, non-2xx response, malformed JSON, rate limiting, and transport failures map to `search_error` with retry guidance. The request never stores API keys in the session or logs.

## Testing

Tests will cover local searching state transitions, online GitHub response normalization, timeout/non-2xx/malformed/empty results, merging and deduplicating candidates, mixed local/network selection, stale completion rejection, and the complete M1 question text including explanation/choices. Existing M3/M4 and local catalog tests must remain green.
