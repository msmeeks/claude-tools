# Plan: Fix Step 6a placement, numbering, and sequencing in /close-iteration

**Issues:** #19, #20, #21, #22, #23, #24, #25, #26, #27

---

## Goal

`/close-iteration`'s `meta/plans/` removal step is reviewed by the same gates as the
rest of the diff, reads unambiguously as its own numbered step, and its git sequencing
(push/commit/pull/branch-deletion) can't fail or silently invite a force-push.

---

## Context

The SDLC review of the fix for #17 (moving `meta/plans/` removal from a post-merge direct
push into a pre-merge commit on the integration branch) filed nine findings against the
new "Step 6a" in `skills/close-iteration/skill.md`. The most significant (#20, Major): the
step lands its commit *after* Step 6 promotes the PR to ready and *after* Step 4's
diff-based findings review, so the new commit is merged via Step 7 without ever passing
through review — undermining the point of moving off a direct push in the first place.
The rest (#19, #21, #22, #23, #24, #25, #26, #27) are numbering/heading, prose, and git-
sequencing issues in the same region, several of which are only resolved cleanly once #20's
renumbering happens. See the Agent Brief on #20 for full current/desired behavior.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `skills/close-iteration/skill.md` | Relocate the `meta/plans/` removal step to a top-level, numbered step before the SDLC Findings Review and PR-promotion steps; renumber all following steps; fix prose (commit message wording, force-push guidance, branch-switch fallback, pre-commit sanity check, race-window note); reorder post-merge cleanup so the default-branch pull precedes local integration-branch deletion. |

### Steps

1. Move the "Step 6a — Remove meta/plans/ on the integration branch" section so it becomes
   its own `## Step N` heading positioned after the Soft Warnings step and before the SDLC
   Findings Review step (i.e., before the step that runs `gh pr diff` and before the step
   that runs `gh pr ready`).
2. Renumber every subsequent `## Step N` heading (and any internal step cross-references in
   prose) consecutively; keep lettered sub-steps nested as H3 under their correct parent.
3. In the relocated step's prose:
   - Fix the commit message to describe committing *to* the integration branch, not merging
     into it.
   - Add a fallback for `git switch <default_branch>` when no local tracking branch exists
     yet (e.g. `git switch -c <default_branch> --track origin/<default_branch>`).
   - Add guidance that a rejected push must never be force-pushed — re-run from the fetch
     step instead.
   - Add a `git status` (or equivalent) sanity check immediately before the commit, after
     the fetch/pull.
   - Note the race window between this step's push and the later merge step.
4. In the post-merge cleanup step, reorder so the sub-step that pulls the default branch
   (to bring in the merge commit) runs *before* the sub-step that deletes the local
   integration branch, so the plain `git branch -d` always succeeds.

---

## Acceptance Criteria

- [ ] The `meta/plans/` removal step is a top-level `## Step N` heading, positioned so its
      commit is included in the diff the SDLC findings review step inspects, and lands
      before the PR is promoted from draft to ready.
- [ ] All steps are renumbered consecutively with no gaps or duplicates; sub-steps remain
      correctly nested.
- [ ] The commit message wording is corrected.
- [ ] A fallback exists for creating a local tracking branch for the default branch.
- [ ] Rejected-push guidance (never force-push, re-run from fetch) is documented.
- [ ] A pre-commit sanity check is documented.
- [ ] The push-to-merge race window is noted.
- [ ] Post-merge cleanup pulls the default branch before deleting the local integration
      branch.

---

## Pre-Implementation Review

Not run — this is a documentation-only change to a single skill file with no security,
privacy, accessibility, or design surface.
