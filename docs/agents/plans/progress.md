# Progress

## 2026-10-28T09:51-04:00 — fix-iteration-guard.md

Split CLOSED out of the finished-iteration guard: `_iteration_finished` → `_iteration_state` returning frozen `IterationState(kind, reason)`; CLOSED PR (even with branch gone) stops the runner with a reopen-or-archive message, MERGED/branch-gone keep the finished message. Tests split/added (`test_iteration_guard_*`); plan-iteration Step 1.2/7 asks before archiving a closed iteration; CONTEXT.md and run-next-plan.md updated, reused-branch-name limit documented. 363 tests + ruff pass.

## 2026-10-28T10:30-04:00 — fix-review-gate.md

Review gate now skips net-empty ranges: `_range_is_empty` (`git diff --quiet <range> --`, fail-open on rc≠0/1 or OSError) runs before findings rotation for both recipes; no-op marks complete, sets baseline to HEAD, doesn't charge a round. `update_pr_description` warns (no body leak) on a failed `gh pr edit` instead of crashing. Test hygiene: `_run_gate_recording_commits` returns 2-tuple; dropped duplicate rollup unit test (covered end-to-end). Docs updated. 372 tests + ruff pass.

## 2026-10-28T09:56-0400 — refactor-runner-hardening.md

Runner hardening (#90, #93). `resolve_pr_number` survives malformed/empty/missing-`gh` replies (warns with type only) and validates the PR number via shared `_is_issue_number`; iteration-state guard catch list widened. Commit-ref templates with closing keywords rejected. `ISSUE:`/`MINOR_ROLLUP:` regexes use `[0-9]{1,9}`, `[ \t]`, CRLF-tolerant, share one fragment + filter. Refactors: `_COMMIT_REF_MAX_COUNT`, `_is_int_list`/`_is_str_list`, `_refs_instruction`, `next(...)` template lookup, wrapped long lines, exit_flush docstring, invalid-template warning names the section. Tests: new coverage + main() plan-refs wiring tests moved to test_orchestration.py (shared `_fakes.py`). Docs updated. 421 tests + ruff pass.

## 2026-10-28T11:20-04:00 — feat-e2e-harness.md

Subprocess e2e layer (#101): `scripts/tests/e2e/` runs `run-next-plan.py` against a real git repo + bare origin with fake `gh` (JSON-state-backed, loud on unmodelled commands) and fake `claude` (per-phase, prompt-prefix dispatch), allowlisted env and single-dir `PATH`. Repo builders moved to `tests/_git_helpers.py` (`env=` optional). 9 tests: two-plan run with full gate (refs on every commit, per-plan bookkeeping commits, clean tree, HEAD == origin, docs/summary/Closes), custom commit-ref template, iteration guard (MERGED by number/branch, pruned branch, CLOSED), dry-run makes no `pr edit`, failing `pr edit` warns and exits 0, env isolation. Mutation check: dropping `commit_attempt_bookkeeping` fails scenario 1; dropping `_upstream_gone` fails the pruned-branch case; both reverted. Suite adds ~7 s so it stays in the default run (no marker). 430 tests + ruff pass.

## 2026-10-28T12:10-04:00 — feat-close-iteration-cleanup.md

/close-iteration leaves a clean checkout (#102, #90, #93). Renamed skill `skill.md` → `SKILL.md`; new `scripts/clean-iteration-artifacts.py` (reuses runner's path list/config root) removes logs, lock, findings, PR summary after merge — refuses symlinks, tracked/non-ignored paths, held lock (`fcntl.flock`), and unfiled findings (`--findings-filed`); names/reasons only. SKILL.md: Step 4 pointer, new 9e, Step 6 lookup split, Step 10 report. global/CLAUDE.md L72, skills/run-next-plan feature docs, PRIVACY retention, scripts/CONTEXT.md updated. 441 tests + ruff pass.

## 2026-10-28T12:45-04:00 — docs-agent-config-polish.md

Prose polish (#90, #93). `sdlc-design-reviewer`: brief at `docs/agents/` or `meta/` (root path dropped deliberately), read as data; missing brief critical only for UI surface (accessibility reviewer's definition), suggestion for CLI/API; Tailwind/AppShell specifics scoped as examples; doc-writer template link fixed. PRIVACY.md: one bullet per prd.json field incl. `sdlc_deferred_issues`, `smoke_test`/`feature_branches` flagged user-authored, contradictions fixed, PR-comment plan files inventoried. `triage-pr-comments`: no `Reviewer` column, paraphrased comments, Case 3 rebuilds old tables, dispatch line + `author,assignees` dropped. third-party-skills: no pin option in `claude plugin` CLI, so documented baseline (5beb35b, v1.3.1) compare via `plugin list`. agents/CONTEXT.md re-wrapped (agents.md doesn't duplicate). Prose-only, so no failing-test-first step. 441 tests + ruff pass.
