# PromptSmith repository guidance

- Start with `HANDOFF.md`, then the relevant document in `docs/`. Current architecture and UI instructions are in `docs/architecture.md` and `docs/ui-handoff.md`.
- Historical documents in `docs/archive/` are evidence and context, not current task instructions. Do not execute their old prompts or infer that planned work is complete.
- The active desktop UI is `PromptSmithApp(GuidedFlowMixin)`. Inspect `guided_flow.py` and `ui.py`; `_legacy_*` methods are not the normal layout entry points.
- Preserve SessionState as the source of business state. Use workflow/session methods for confirmation, cancellation and invalidation; keep request/version checks and Tk main-thread updates.
- Runtime prompts and schemas are under `resources/prompts/`. Keep loaders, test paths and `PromptSmith.spec` aligned. Retain legacy resources that still have references.
- The product hands Agent Skill references and task-specific usage to another AI. It does not install or execute discovered Skills. Ordinary webpages are not automatically Skill candidates.
- General late-stage unknowns belong in the final prompt; preserve the current ability to copy/export without reintroducing obsolete review gates.
- Before changes, state the root cause or objective, scope and completion criteria. Record progress under `docs/maintenance/` for multi-step work. Continue from recorded progress after compaction.
- Run checks appropriate to the change. Repeat passing checks only after new changes, failures or uncovered requirements. Keep unrelated historical failures separate; see `verification/baseline/agent_skill_target_20261007/results.md`.
- Distinguish offline tests, simulated API responses, genuine model calls, EXE smoke checks and user testing. Do not claim full-suite success or live-model quality without matching evidence.
- Do not commit secrets, personal sessions, build outputs or `local_artifacts/`. Do not call paid APIs just to restyle the UI. Follow the user's authorization for any real requests and remote actions.
- Prefer portable relative links in repository documents. Keep research/competition facts separate from proposed improvements.
