# Plan: Fix and cover clean-iteration-artifacts

**Issues:** #106, #107

---

## Goal

`clean-iteration-artifacts.py` only reports `removed:` for paths it actually deleted, and every safety branch has a test.

---

## Context

The script deletes gitignored runner artifacts after merge; `/close-iteration` Step 10 echoes its output verbatim. `main()` reports `removed:` whenever a skip reason is `None`, even when nothing was deleted (logs safe + lock unsafe, or logs absent + lock safe). Many safety branches are also untested. The fix (#106) changes behaviour the tests (#107) pin, so they share one plan.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/clean-iteration-artifacts.py` | Handle logs and lock independently; report `removed:` only after a delete returns; real skip reason for every undeleted artifact; held lock still skips both |
| `scripts/tests/test_clean_iteration_artifacts.py` | Mixed-case tests for #106; one parametrized case per #107 scenario |

### Steps

1. Write failing tests for the two mixed cases (logs safe + lock unsafe; logs absent + lock safe) and the "no `removed:` for a path that still exists" invariant.
2. Rework `_remove_logs_and_lock` / `main()` (around `report()`) to decide per artifact and report from the delete's actual result.
3. Add parametrized tests for each #107 scenario: legacy `meta/` root; symlinked config root (all four paths `skipped (symlink)`, nothing outside repo touched); parent resolving outside the repo; tracked lock; logs-only and lock-only; `rmtree` raising `OSError` while the lock is held; non-empty `plans/` (rmdir skipped); outside a git repo. Assert printed line and filesystem state.
4. Fix any behaviour bug the tests expose, or file it separately if large.

---

## Acceptance Criteria

- [ ] Logs safe + lock unsafe: logs removed and reported, lock reported `skipped` with its reason
- [ ] Logs absent + lock safe: lock removed and reported
- [ ] No `removed:` line for a path that still exists
- [ ] Each #107 scenario has a test asserting the printed line and filesystem state
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
- **sdlc-privacy-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
- **sdlc-accessibility-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
- **sdlc-design-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
