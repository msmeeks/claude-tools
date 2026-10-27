# Progress

## 2026-10-26 22:13 — fix-iteration-state.md (#78, #76)

- #78: `parse_minor_rollup`, `sdlc_deferred_issues` (schema, final-round + rollup recording, kept across completion/re-arm), cap message lists it; never in `Closes`.
- #76: `_iteration_finished` + runner guard before `_register_exit_flush`; close-iteration Step 4 archive fallback; plan-iteration finished-iteration check and fresh-vs-merge `prd.json`.
- Docs updated (run-next-plan, triage-labels, agents README, CONTEXT-MAP, global/CLAUDE.md L72 in its own commit).
- Tests: 256 passed; ruff clean.
