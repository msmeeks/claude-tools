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
`prd.json.sdlc_review_status` must equal `"complete"`. If it's `"pending"`, the runner
hasn't finished its SDLC gate — tell the user to let `run-next-plan.py` complete. If it's
`"needs-human"`, the gate ran but triage wasn't confident resolving every finding
autonomously; the low-confidence issue(s) were left `needs-info` and logged in
`meta/plans/implementation-logs/run-next-plan-*-triage.log` — tell the user to run a
normal `/triage` pass on those issues, then update `sdlc_review_status` before retrying.

### 2c — SDLC findings addressed
An issue in `sdlc_finding_issues` counts as addressed if it is already `CLOSED`, **or** if it
is linked to the integration PR as a closing reference — GitHub will auto-close it the moment
Step 8's merge lands, so it is expected to still show `OPEN` at this point in the run. Do not
treat that as a failure.

First find the integration PR number:
```bash
gh pr list --head <integration_branch> --state open --json number --jq '.[0].number'
```

Then fetch the set of issues GitHub will auto-close on merge of that PR:
```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $pr:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$pr) {
        closingIssuesReferences(first: 100) { nodes { number } }
      }
    }
  }' -f owner=<owner> -f repo=<repo> -F pr=<pr-number> \
  --jq '.data.repository.pullRequest.closingIssuesReferences.nodes[].number'
```

For each issue number in `prd.json.sdlc_finding_issues`:
```bash
gh issue view <N> --json number,title,state
```
- `state: CLOSED` → addressed.
- `state: OPEN` and the issue number appears in the `closingIssuesReferences` list above →
  addressed (will auto-close on merge) — note this in the table but do not block.
- `state: OPEN` and **not** in `closingIssuesReferences` → hard blocker. No merge is currently
  going to close it, so it's genuinely unaddressed.

Print a table: number, title, state, resolution (`closed` / `will auto-close on merge` /
`BLOCKER — not linked`). Only rows marked `BLOCKER` stop the run.

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

## Step 4 — Remove meta/plans/ on the integration branch

Do this before the SDLC Findings Review and PR-promotion steps, so the removal commit
rides through the same diff-based review as the rest of the iteration's work instead of
landing as an unreviewed change.

```bash
git switch <integration_branch>
git fetch origin
git pull origin <integration_branch>
git status
git rm -r meta/plans/
git commit -m "chore: remove iteration plans from <integration_branch>

Plans are preserved in git history on <integration_branch>."
git push origin <integration_branch>
git switch <default_branch> || git switch -c <default_branch> --track origin/<default_branch>
```

Fetching/pulling the integration branch immediately before committing avoids a
non-fast-forward push if the branch moved since the Step 2d `git fetch`. The `git status`
check right before `git rm` confirms the working tree is clean, catching any leftover local
changes before they get swept into this commit. If `git push` is rejected (non-fast-forward),
never force-push — re-run this step from the `git fetch` line so the new commit is built on
top of the branch's current tip. Switching back to the default branch afterward ensures Step
9d's local branch deletion isn't blocked by the integration branch being currently checked
out; the fallback creates a local tracking branch if one doesn't already exist.

Race window: there is a gap between this step's push and the merge in Step 8. If the PR was
reviewed against a specific commit before this step ran, the push here changes the tip that
Step 8 will actually merge — keep that gap short and re-check the PR diff if it's been a
while.

---

## Step 5 — SDLC Findings Review

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

## Step 6 — PRD Issue Coverage Check

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

## Step 7 — Issue Linking and PR Promotion

Compile the full `Closes` list from all `prd.json.plans[*].issues` arrays plus
`prd.json.sdlc_finding_issues`. Including the SDLC finding issues here guarantees they
auto-close on merge even if the commit(s) that addressed them didn't happen to use a
closing keyword.

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

## Step 8 — Merge

```bash
gh pr merge <pr-number> --merge --delete-branch
```

`--merge` preserves the full integration branch commit history, including the
`meta/plans/` removal commit from Step 4. `--delete-branch` removes the remote
integration branch automatically.

---

## Step 9 — Post-Merge Cleanup

Run all sub-steps in order.

### 9a — Close PRD issues

For each PRD issue that passed all three checks in Step 6:
```bash
gh issue close <N> --comment "Closed by iteration <integration_branch>. All scoped work merged in PR #<pr-number>."
```

### 9b — Clean up worktrees and branches

Read `prd.json.feature_branches`. For each branch:
1. Find its worktree: `git worktree list --porcelain` → match path → `git worktree remove <path> --force`
   (abort if worktree has uncommitted changes — surface the path and stop)
2. Delete local branch: `git branch -d <branch>` (warn if not fully merged; require user
   confirmation before using `-D`)
3. Delete remote branch: `git push origin --delete <branch>`

Also enumerate `git worktree list --porcelain` for any remaining worktree whose branch
matches `integration_branch` and remove it.

### 9c — Final pull

```bash
git switch <default_branch>
git pull origin <default_branch>
```

### 9d — Delete local integration branch

Delete the local integration branch if it still exists locally. It was already switched off
in Step 4 and is fully merged via Step 8, and 9c has just pulled the merge commit into the
local default branch, so this succeeds without `-D`:
```bash
git branch -d <integration_branch>
```

---

## Step 10 — Print Closing Report

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
