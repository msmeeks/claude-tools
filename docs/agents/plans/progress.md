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

## 2026-10-26 — chore-third-party-skills.md (#81)

- Reviewed upstream `5beb35b` (plugin v1.3.1). `third-party-skills.md`: plugin + skills.sh install, supply-chain review, single rename table, refreshed skill table, no local mods. README points to it.
- plan-iteration Step 8.6 finds the parent spec via `## Parent` (verified open, labelled, not a PR; legacy `prd` fallback); close-iteration Step 6/9a use `prd_issue` first with a closure allow-list.
- Runner prompt: `/qa` if installed, else `sdlc-qa-engineer` (static literal; 2 tests). global/CLAUDE.md in its own commit. PRIVACY.md notes `prd_issue` is a bare int; stale `/triage-issues` fixed.
- Follow-up filed: #84 (GLOSSARY.md decision). Labels verified present. Downstream search found no `to-prd`/`to-issues` hits. Plugin `/tdd` bare-vs-namespaced resolution unverified; prompts keep bare names.
- Human steps for PR: install plugin after source review; remove/choose skills.sh copy; decide #84.
- Tests: 297 passed; ruff clean.

## 2026-10-26 — fix-finished-iteration-guard.md (#85, #86)

- `_iteration_finished`: finished on a MERGED or CLOSED same-repo PR with matching head (`isCrossRepository` fetched); `ls-remote` fallback runs only via new `_branch_is_pushed` (upstream, no unpushed commits; probe errors = unknown). Local-only/unpushed branches no longer die.
- Tests: guard helper extended; added CLOSED, cross-repo, local-only, unpushed, probe-error, gh no-output, missing-head cases; warning text asserted; duplicate OPEN case removed.
- Docs: plan-iteration Step 1.2, run-next-plan.md.
- Tests: 306 passed; ruff clean.

## 2026-10-26 22:28 — test-commit-refs-coverage.md (#87, #88, #89)

- #87: `_coerce_refs` now warns (counts only, via `warn()`) about invalid/duplicate refs and, separately, cap overflow after truncation; comment on `type(x) is int` excluding bool.
- #88: template tests for the 40/41 length boundary, empty section (blank/EOF), shell and lookalike characters, invalid UTF-8; cache cleared in the `tracker_root` fixture.
- #89: `main()` wiring (plan `issues` → `refs=`, no key → empty, cap + warning) and gate wiring (PR ref reaches interrupt, triage, docs commits; empty when no PR). Mutation-checked: removing `refs=` at each call site or `>`→`>=` fails a test.
- Docs: run-next-plan.md. Tests: 347 passed; ruff clean.
