# Plan: Fold meta/plans/ removal into the integration PR merge

**Issues:** #17

---

## Goal

`/close-iteration` completes end-to-end under Claude Code auto-mode without triggering a manual "direct push to default branch" permission prompt.

---

## Context

Step 8a of `/close-iteration` currently removes `meta/plans/` by committing directly to the default branch *after* the integration PR has already been merged (Step 7). Under Claude Code auto-mode, with no pre-existing allow-rule for direct pushes to the default branch, this push is denied by the permission classifier, forcing a manual confirmation round-trip. This breaks unattended/CI use of `/close-iteration` (e.g. `run-next-plan.py` or an unattended loop with no human available to answer the prompt).

The fix: commit the `meta/plans/` removal to the integration branch itself, before the integration PR is merged, so the removal rides along as part of the normal PR merge (`gh pr merge`) into the default branch. No step in the flow should push a commit directly to the default branch afterward — Step 7's PR merge already carries it in.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `skills/close-iteration/skill.md` | Move the `meta/plans/` removal from post-merge Step 8a to a new pre-merge step between Step 6 and Step 7; update Step 8 accordingly; adjust the closing report in Step 9 if wording assumes post-merge removal. |

### Steps

1. Insert a new step (e.g. "Step 6a — Remove meta/plans/ on the integration branch") after Step 6 (Issue Linking and PR Promotion) and before Step 7 (Merge). It must:
   - Check out and fetch/pull the *integration branch* (not the default branch) immediately before committing, so the subsequent push can't be rejected as non-fast-forward if the branch moved since the Step 2d `git fetch`.
   - Run `git rm -r meta/plans/` and commit with a message equivalent to the current Step 8a message (e.g. "chore: remove iteration plans before merging `<integration_branch>`" — adjust tense since it now runs pre-merge), noting the plans remain in git history.
   - Push the commit to the *integration branch* (`git push origin <integration_branch>`), not the default branch. This is an ordinary feature-branch push and is not subject to the auto-mode default-branch classifier.
   - After committing, switch off the integration branch (e.g. back to the default branch) so a later local-branch deletion isn't blocked by the branch being currently checked out.

2. Remove the old Step 8a from Step 8 (Post-Merge Cleanup). Step 8 now starts with what was 8b (Close PRD issues), renumbered as needed. Step 8c (worktree/branch cleanup) still needs to delete the local integration branch — since the new pre-merge step already switches off it, this should work without a special case, but verify the branch is fully merged (it will be, since Step 7 already merged it via GitHub) so `git branch -d` succeeds without `-D`.

3. Update Step 9's closing report line `meta/plans/ removed: yes (history on <integration_branch>)` if needed — the meaning (plans preserved in integration-branch history, removed from default branch) is unchanged, but confirm the report still reads correctly given the new step order.

4. Confirm no other step in the skill performs a direct push to the default branch. (Verified during triage: Step 8a was the only one.)

---

## Acceptance Criteria

- [ ] Running `/close-iteration` merges the integration branch to the default branch exactly once, via `gh pr merge`, with zero direct `git push` calls targeting the default branch anywhere in the flow.
- [ ] `meta/plans/` is absent from the default branch immediately after the PR merge completes — no separate step is required afterward to remove it.
- [ ] The `meta/plans/` removal commit is present in the default branch's history as part of the merged PR, retrievable via git history the same way it is today.
- [ ] The removal happens only after Steps 4-6 (which read `meta/plans/prd.json` for gating) have already completed.
- [ ] Under Claude Code auto-mode with no pre-existing allow-rule for direct pushes to the default branch, running `/close-iteration` end-to-end does not trigger a "direct push to default branch" permission prompt.
- [ ] Step 8c's local integration-branch deletion (`git branch -d <integration_branch>`) succeeds without needing `-D`, since the branch is fully merged and not currently checked out.
- [ ] No new polling/retry logic for branch-protection status checks or approval resets is added.

---

## Pre-Implementation Review

**Security (sdlc-security-reviewer):** No vulnerabilities. The reordering reduces direct-push surface rather than adding any; it doesn't expand what automation is allowed to do. Two robustness hazards to encode into the implementation (both folded into the Steps above): (1) fetch/pull the integration branch immediately before committing the removal, to avoid a non-fast-forward push if the branch moved since the earlier `git fetch`; (2) switch off the integration branch after committing, so Step 8c's local branch deletion doesn't fail on a checked-out branch. Pre-existing shell interpolation of branch names/PR numbers into git/gh commands is unchanged by this plan and out of scope.

**Privacy (sdlc-privacy-reviewer):** Nothing substantive. Internal dev-tooling workflow change with no user-facing data processing; no PII, consent, or retention implications. Retention behavior (plans preserved in git history, removed from default branch working tree) is unchanged by the reordering. One workflow-correctness note (not a privacy issue): confirm Step 6's PR-ready promotion and `Closes` block update happen before the removal commit is pushed to the integration branch, so the PR body edit isn't racing a rebase of the same branch.

Accessibility and design reviews were skipped — this change is confined to a markdown workflow-skill definition with no UI surface.
