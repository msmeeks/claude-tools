# Progress

## 2026-10-26 22:13 — fix-iteration-state.md (#78, #76)

- #78: `parse_minor_rollup`, `sdlc_deferred_issues` (schema, final-round + rollup recording, kept across completion/re-arm), cap message lists it; never in `Closes`.
- #76: `_iteration_finished` + runner guard before `_register_exit_flush`; close-iteration Step 4 archive fallback; plan-iteration finished-iteration check and fresh-vs-merge `prd.json`.
- Docs updated (run-next-plan, triage-labels, agents README, CONTEXT-MAP, global/CLAUDE.md L72 in its own commit).
- Tests: 256 passed; ruff clean.

## 2026-10-26 23:05 — feat-commit-refs.md (#80)

- Runner: `_load_commit_ref_template` (whitelist-validated, cached, default `Refs #{n}`), `_coerce_refs`, `_format_refs`; plan prompt carries the rule and quoted template; `ensure_committed(refs=)` adds it to the commit prompt and wip trailer; plan, docs-phase and SDLC call sites pass refs (plan `issues` / integration PR number). `exit_flush` unchanged by design.
- `docs/agents/issue-tracker.md` gets `## Commit references`; close-iteration Step 3 matches against the same template; run-next-plan feature doc updated; global/CLAUDE.md L66 in its own commit.
- Tests: 295 passed; ruff clean.

## 2026-10-26 23:40 — fix-plan-review-roster.md (#79)

- plan-iteration Step 6 and triage-pr-comments Step 5: shared reply contract (findings / `no findings` / `N/A: reason` / `ERROR: reason`), always dispatch the full roster, bare-filename roster names, description quoted as data; triage-pr-comments now reads `plan_review.reviewers`.
- Accessibility and design prompts and agent files re-scoped (design: UI/CLI/API; a11y: UI/HTML/docs + terminal check, N/A for APIs/backend); N/A reply added to both output formats.
- `## Pre-Implementation Review` is never omitted; templates and Review Modes list every agent. Nothing in `scripts/` parses it.
- Docs: skills.md, run-next-plan.md. Prose-only change, so no new tests; 295 passed, ruff clean.
