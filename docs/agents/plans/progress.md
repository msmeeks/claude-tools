# Progress

## 2026-10-28T09:51-04:00 — fix-iteration-guard.md

Split CLOSED out of the finished-iteration guard: `_iteration_finished` → `_iteration_state` returning frozen `IterationState(kind, reason)`; CLOSED PR (even with branch gone) stops the runner with a reopen-or-archive message, MERGED/branch-gone keep the finished message. Tests split/added (`test_iteration_guard_*`); plan-iteration Step 1.2/7 asks before archiving a closed iteration; CONTEXT.md and run-next-plan.md updated, reused-branch-name limit documented. 363 tests + ruff pass.

## 2026-10-28T10:30-04:00 — fix-review-gate.md

Review gate now skips net-empty ranges: `_range_is_empty` (`git diff --quiet <range> --`, fail-open on rc≠0/1 or OSError) runs before findings rotation for both recipes; no-op marks complete, sets baseline to HEAD, doesn't charge a round. `update_pr_description` warns (no body leak) on a failed `gh pr edit` instead of crashing. Test hygiene: `_run_gate_recording_commits` returns 2-tuple; dropped duplicate rollup unit test (covered end-to-end). Docs updated. 372 tests + ruff pass.
