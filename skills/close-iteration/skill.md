---
name: close-iteration
description: Closes an iteration by gate-checking completion, merging the integration PR to the default branch, closing linked issues, cleaning up branches/worktrees, and removing meta/plans/. The bookend to /plan-iteration. Use when all plans are done and the SDLC review is complete.
---

# Close Iteration

Closes an iteration end-to-end: verifies all gate conditions, promotes the draft PR, merges
to the default branch, closes linked issues, removes `meta/plans/` from the working tree,
and deletes the integration branch and all associated worktrees.

## Usage

```
/close-iteration
```

No arguments. All context is read from `meta/plans/prd.json`.

---

## Step 1 — Bootstrap

1. Read `docs/llms.md`. If it doesn't exist, stop and tell the user to run `/sdlc` first.
2. Load `meta/plans/prd.json`. If it doesn't exist, stop — there is no active iteration.
3. Resolve `{owner}` and `{repo}` for all `gh api` calls:
   ```bash
   gh repo view --json nameWithOwner --jq '.nameWithOwner'
   ```
4. Read `integration_branch` from `prd.json`.
5. Resolve the default branch:
   ```bash
   git symbolic-ref refs/remotes/origin/HEAD | sed 's|refs/remotes/origin/||'
   ```

---

## Step 2 — Hard Blockers

Check all of the following before taking any action. Print a clear table of every failure
and stop immediately if any blocker is present.

### 2a — All plans terminal
Every entry in `prd.json.plans` must have `status: "done"` or `status: "stalled"`.
Any `pending` or `in-progress` entry is a hard blocker — tell the user to let
`run-next-plan.py` finish or mark the plan stalled manually.

For stalled plans: check whether their linked GitHub issues are already closed (manual fix
outside the runner). If so, surface as a **warning** (Step 3) rather than a blocker.

### 2b — SDLC review complete
`prd.json.sdlc_review_status` must equal `"complete"`. If not, the runner hasn't finished
its SDLC gate — tell the user to let `run-next-plan.py` complete.

### 2c — SDLC findings addressed
Fetch each issue number in `prd.json.sdlc_finding_issues`:
```bash
gh issue view <N> --json number,title,state
```
Any issue still in state `OPEN` is a hard blocker. Print a table: number, title, state.

### 2d — No merge conflicts
```bash
git fetch origin
git merge-tree $(git merge-base HEAD origin/<default_branch>) \
  origin/<default_branch> origin/<integration_branch>
```
Any conflict markers in the output are a hard blocker. Tell the user to resolve conflicts
on the integration branch and re-run.

### 2e — Smoke test passes
Run the command in `prd.json.smoke_test` from the repo root. A non-zero exit code is a
hard blocker — print the full output. If `smoke_test` is absent or `null`, warn and skip.

---

## Step 3 — Soft Warnings (require confirmation)

Print a warning table and ask for explicit confirmation before proceeding:

- **Stalled plans with closed issues** — the work landed outside the runner; confirm the
  plan's scope is actually covered by inspecting the PR diff.
- **Untraceable commits** — commits on `integration_branch` that contain no `#N` issue
  reference in their message. Mine with:
  ```bash
  git log origin/<default_branch>..origin/<integration_branch> --oneline
  ```
  Flag any commit whose message has no `#` reference.

---

## Step 4 — SDLC Findings Review

Read `meta/sdlc-review-findings.md`. For each finding section:

1. Identify the corresponding issue number from `prd.json.sdlc_finding_issues`.
2. Check whether that issue is closed (covered by 2c, but here inspect *why*: code change vs
   won't-fix comment).
3. Inspect the PR diff for code that addresses the finding:
   ```bash
   gh pr diff <pr-number>
   ```

Summarize: findings addressed in code, findings closed as won't-fix, any gaps found.
If gaps exist, surface them and ask the user to confirm before continuing.

---

## Step 5 — PRD Issue Coverage Check

Fetch all open issues with the `PRD` label:
```bash
gh issue list --label PRD --state open --limit 100 --json number,title,body
```

For each PRD issue, run all three checks:

1. **Child issues closed** — parse every `#N` reference from the issue body; verify each is
   closed: `gh issue view <N> --json state`
2. **Plan entries done** — verify the corresponding `prd.json` plan entry has `status: "done"`
3. **Scope covered** — inspect the PR diff for changes that implement the PRD issue's stated
   goals; use Claude's judgment to assess coverage

Mark a PRD issue **ready to close** only if all three pass. Surface any failures with
the specific gap (which child issue is open, which plan is not done, what scope is missing).

---

## Step 6 — Issue Linking and PR Promotion

Compile the full `Closes` list from all `prd.json.plans[*].issues` arrays.

Fetch the integration PR:
```bash
gh pr list --head <integration_branch> --state open --json number,title,body
```

Update the PR body to include a `Closes` block listing every issue:
```
Closes #N, #M, #P ...
```

Promote from draft to ready:
```bash
gh pr ready <pr-number>
```

---

## Step 6a — Remove meta/plans/ on the integration branch

Do this before merging, so the removal rides along as part of the normal PR merge in
Step 7 rather than requiring a separate direct push to the default branch afterward.

```bash
git switch <integration_branch>
git fetch origin
git pull origin <integration_branch>
git rm -r meta/plans/
git commit -m "chore: remove iteration plans before merging <integration_branch>

Plans are preserved in git history on <integration_branch>."
git push origin <integration_branch>
git switch <default_branch>
```

Fetching/pulling the integration branch immediately before committing avoids a
non-fast-forward push if the branch moved since the Step 2d `git fetch`. Switching back
to the default branch afterward ensures Step 8b's local branch deletion isn't blocked by
the integration branch being currently checked out.

---

## Step 7 — Merge

```bash
gh pr merge <pr-number> --merge --delete-branch
```

`--merge` preserves the full integration branch commit history, including the
`meta/plans/` removal commit from Step 6a. `--delete-branch` removes the remote
integration branch automatically.

---

## Step 8 — Post-Merge Cleanup

Run all sub-steps in order.

### 8a — Close PRD issues

For each PRD issue that passed all three checks in Step 5:
```bash
gh issue close <N> --comment "Closed by iteration <integration_branch>. All scoped work merged in PR #<pr-number>."
```

### 8b — Clean up worktrees and branches

Read `prd.json.feature_branches`. For each branch:
1. Find its worktree: `git worktree list --porcelain` → match path → `git worktree remove <path> --force`
   (abort if worktree has uncommitted changes — surface the path and stop)
2. Delete local branch: `git branch -d <branch>` (warn if not fully merged; require user
   confirmation before using `-D`)
3. Delete remote branch: `git push origin --delete <branch>`

Also enumerate `git worktree list --porcelain` for any remaining worktree whose branch
matches `integration_branch` and remove it.

Delete the local integration branch if it still exists locally (it was already switched off
in Step 6a and is fully merged via Step 7, so this succeeds without `-D`):
```bash
git branch -d <integration_branch>
```

### 8c — Final pull

```bash
git switch <default_branch>
git pull origin <default_branch>
```

---

## Step 9 — Print Closing Report

```
=== Iteration Closed ===

Branch merged:       <integration_branch> → <default_branch>
PR:                  #<N> <title> (<url>)

Plans:               <done> done, <stalled> stalled, <total> total
Issues closed:       #N, #M, ...
PRD issues closed:   #N, ...
PRD issues skipped:  #N (reason: <gap>)

Branches deleted:    <list>
Worktrees removed:   <list>
meta/plans/ removed: yes (history on <integration_branch>)
```
