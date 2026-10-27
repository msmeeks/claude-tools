# Plan: Finished-iteration guard no longer blocks valid runs

**Issues:** #85, #86

---

## Goal

The runner stops on a finished iteration only when it has seen that iteration's PR merged or closed, and the guard's `gh pr view` paths are covered by tests.

---

## Context

`_iteration_finished` in `scripts/run-next-plan.py` treats `git ls-remote --exit-code` exit 2 as "branch gone, iteration finished". A branch that was never pushed, failed to push, or lives on another remote looks finished, so `main` calls `die()` on a valid run (#85). The guard's tests cover only FileNotFoundError, malformed JSON and an OPEN PR (#86). The tests in #86 describe the behaviour that #85 changes, so do #85 first and write #86's tests against the new behaviour.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | `_iteration_finished`: finished on a MERGED or CLOSED PR whose `headRefName` matches; run the `ls-remote` fallback only when the local branch has an upstream and no unpushed commits |
| `scripts/tests/test_orchestration.py` | Guard tests (`test_iteration_guard_*`, `_finished` helper) |
| `skills/plan-iteration/SKILL.md` (Step 1.2) | Update the finished-iteration rule so it matches the code |
| `docs/features/run-next-plan.md` | Update any wording of the old rule (grep "finished") |

### Steps

1. Failing tests first (#85):
   - Local-only branch (no upstream, no PR) is not finished and makes no `ls-remote` call.
   - Branch with unpushed commits and absent from origin is not finished.
   - MERGED PR with matching head is finished.
   - CLOSED PR with matching head is finished.
   - MERGED or CLOSED PR with a different head is not finished.
   - `test_iteration_guard_branch_gone_from_origin_is_finished` is inverted or replaced on purpose, not just deleted.
2. Implement. Build the reason string from the state, `f"PR #{n} was {state.lower()}"`, to match the existing "was merged" shape. Keep the `die()` text, including its `run /plan-iteration` fix-it, byte-identical (tests match on "finished iteration").
3. Add `isCrossRepository` to the `--json` fields. A cross-repo PR does not count as finished.
4. Probe upstream and unpushed state with `git rev-parse @{u}` and `git rev-list @{u}..HEAD`. If a probe errors, return None (unknown), never "finished". Treat only `ls-remote` exit 2 as "gone". Keep this path quiet: no `warn` for an unpushed branch.
5. Tests for #86:
   - `gh pr view` exits non-zero with empty stdout: result is `None` and stderr mentions "gh pr view".
   - MERGED payload with no `headRefName`: result is `None`, falls through to the `ls-remote` check.
   - The FileNotFoundError and bad-JSON warning tests assert the warning text through `capsys`.
   - Delete the `{"pr": {"state": "OPEN"}}` parametrisation that duplicates the open-PR test.
6. Keep warnings to the PR number, exit code and exception class. Do not log stderr or exception messages.
7. Update the docstring, `/plan-iteration` Step 1.2 and the feature doc to the new rule.

---

## Acceptance Criteria

- [ ] Local-only branch (no upstream, no PR) is not reported finished and the run proceeds.
- [ ] Branch with unpushed commits and absent from origin is not reported finished.
- [ ] Branch with a MERGED or CLOSED PR (matching head) is reported finished and the runner stops with the existing fix-it message.
- [ ] #86's new tests exist and pass, and the duplicate OPEN case is gone.
- [ ] Removing a guard warning makes a test fail.
- [ ] `cd scripts && python3 -m pytest && python3 -m ruff check .` is clean.

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** findings
  - Low: a false "finished" is the more dangerous error. Run the fallback only with an upstream and no unpushed commits, and treat probe errors as unknown. Accept only exit 2 as "gone".
  - Low: `pr_number` comes from repo content. Require `headRefName` to match for both MERGED and CLOSED. Add `isCrossRepository` so a fork PR with the same branch name cannot satisfy the check. CLOSED is a weaker signal than MERGED, so confirm that is the intent.
  - Informational: warnings carry only PR number, exit code and exception class. Do not log stderr or exception messages.
  - Informational: cover the missing-`headRefName` case.
- **sdlc-privacy-reviewer:** N/A: the change touches only the iteration-finished check (PR state and `ls-remote` fallback) and its tests, with no personal data.
- **sdlc-accessibility-reviewer:** N/A: the change touches only an internal orchestration function, its plain-text `warn`/`die` messages (no colour) and its tests.
- **sdlc-design-reviewer:** findings
  - Major: add the CLOSED reason as a parallel lowercase past-tense string. Keep the `die()` text byte-identical.
  - Major: update `/plan-iteration` Step 1.2, the docstring and the feature docs in the same change.
  - Minor: the unpushed-branch path is quiet. Reuse the existing local-branch check where there is one.
  - Minor: keep the head-ref check for CLOSED.
  - Minor: reuse the `_finished` helper and `test_iteration_guard_<case>` naming, update the gone-from-origin test deliberately, and leave the autouse no-network fixture alone.
  - Minor: both paths still return `str | None` and print only through `warn()` and `die()`.
