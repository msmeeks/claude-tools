---
name: close-iteration
description: Closes an iteration by gate-checking completion, merging the integration PR to the default branch, closing linked issues, cleaning up branches/worktrees, removing <config-root>/plans/, and removing the gitignored runtime artifacts. The bookend to /plan-iteration. Use when all plans are done and the SDLC review is complete.
---

# Close Iteration

Closes an iteration end-to-end: verifies all gate conditions, promotes the draft PR, merges
to the default branch, closes linked issues, removes `<config-root>/plans/` from the working tree,
removes the gitignored runtime artifacts, and deletes the integration branch and all associated worktrees.

## Usage

```
/close-iteration
```

No arguments. All context is read from `<config-root>/plans/prd.json`.

---

## Step 1 — Bootstrap

1. Read the context index: `CONTEXT-MAP.md` (or a root `CONTEXT.md`), or `docs/llms.md` in
   un-migrated repos. If neither exists, stop and tell the user to run `/sdlc` first.
2. Resolve the config root (`<config-root>` below): `docs/agents/` if it exists, else `meta/`.
   Load `<config-root>/plans/prd.json`. If it doesn't exist, stop — there is no active
   iteration.
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
hasn't finished its SDLC gate — tell the user to let `run-next-plan.py` complete.

Note: `sdlc_review_status` legitimately cycles `complete → pending → complete` across
incremental review rounds. When a re-armed round (new commits since `last_reviewed_sha`)
resets the gate, a transient `pending` is normal, not an anomaly — the runner drives it back
to `complete` once the new commits pass. The pass condition here is unchanged: `complete`
with no remaining eligible plans.

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
- **Stalled plans with open issues** — the plan did no work and its issues are *not* in the
  Step 7 Closes set, so they stay open after merge (correct behaviour). Print each stalled
  plan's `file` and its still-open issue numbers so the user can consciously confirm leaving
  them for a future iteration. These carry through to the Step 10 `Issues left open:` line.
- **Deferred review issues** — each still-open `prd.json.sdlc_deferred_issues` entry (check with
  `gh issue view <N> --json state`). Print one per line as `#N — deferred by round cap` (filed
  on the final review round) or `#N — minor rollup` (the rollup issue). They stay open after
  merge and carry through to the Step 10 `Issues left open:` line.
- **Untraceable commits** — commits on `integration_branch` that contain no issue
  reference in their message. The reference format is the template on the first non-empty line
  under `## Commit references` in `<config-root>/issue-tracker.md` (default `Refs #{n}`; ignore
  a template that has no single `{n}` or contains characters outside letters, digits, spaces
  and `#:.,_-`). Match with the escaped template, replacing the escaped `{n}` with `\d+` —
  never use the raw template as a regex. The check is advisory. Mine with:
  ```bash
  git log origin/<default_branch>..origin/<integration_branch> --oneline
  ```
  Flag any commit whose message has no match for that pattern. Don't look for a literal `#`:
  a custom template such as `Tracks: GH-{n}` has none.

---

## Step 4 — Remove <config-root>/plans/ on the integration branch

Do this before the SDLC Findings Review and PR-promotion steps, so the removal commit
rides through the same diff-based review as the rest of the iteration's work instead of
landing as an unreviewed change.

```bash
git switch <integration_branch>
git fetch origin
git pull origin <integration_branch>
git status
git rm -r --ignore-unmatch <config-root>/plans/
```

If `git rm` staged anything (`git diff --cached --quiet` exits non-zero), commit and push.
A `git rm` that matches nothing (plans were never tracked) is not an error — skip the commit
and push.
```bash
git commit -m "chore: remove iteration plans from <integration_branch>

Plans are preserved in git history on <integration_branch>."
git push origin <integration_branch>
```

**Archive fallback.** If `prd.json` or any plan `.md` file remains under `<config-root>/plans/`
afterwards (untracked plans), archive it — never delete untracked plans outright. Gitignored
runtime artifacts (`implementation-logs/`, `prd.json.lock`) always survive `git rm`; on their own
they are not a trigger for archiving — Step 9e removes them after the merge. When archiving, move everything
except `archive/` itself and the runtime artifacts (`implementation-logs/`, `prd.json.lock`) —
Step 9e removes those — into
`<config-root>/plans/archive/<slug>/`:

- `<slug>` is `integration_branch` with `/` replaced by `-`, restricted to `[A-Za-z0-9._-]`,
  with no leading `.` or `-`. Fall back to `iteration-<YYYY-MM-DD>` if nothing is left.
- If the destination exists, append `-2`, `-3`, and so on.
- Quote every path and pass `--` to `mv`. The resolved destination must sit inside the repo.
- Before moving, if `git check-ignore -q <config-root>/plans/archive/` fails, append
  `<config-root>/plans/archive/` to the file named by `git rev-parse --git-path info/exclude`.
  Use the exclude file, not `.gitignore`. Exclude only `archive/`, never `plans/`, so
  `git status` stays clean and the archive is never committed or published.

```bash
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

Read `<config-root>/sdlc-review-findings.md`. For each finding section:

0. **Reconcile before filing.** Before filing a follow-up for any finding, check
   `gh issue list --label sdlc-finding --state open --json number,title` and
   `prd.json.sdlc_deferred_issues`. A finding already covered by either is not re-filed;
   name the existing issue instead.
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

## Step 6 — Spec Issue Coverage Check

Take the spec issue from `prd.json.prd_issue` first (the identifier keeps its name; the
value is a bare integer from `/plan-iteration` Step 8.6). Only if it is absent, fall back to
the legacy `prd` label (June `to-prd` install; lowercase), never to all `ready-for-agent`
issues:
```bash
gh issue view <prd_issue> --json number,title,body
```

Only if `prd_issue` is absent:
```bash
gh issue list --label prd --state open --limit 100 --json number,title,body
```

For each spec issue, run all three checks:

1. **Child issues covered** — parse every `#N` reference from the issue body. Each must be
   closed (`gh issue view <N> --json state`) or in this PR's **Closes set** (defined in Step 7),
   which the Step 8 merge closes. Check the set, not the PR body: Step 7 hasn't written it yet.
   A child that is open and outside the set — a stalled plan's or deferred issue, say — fails.
2. **Plan entries done** — verify the corresponding `prd.json` plan entry has `status: "done"`
3. **Scope covered** — inspect the PR diff for changes that implement the spec issue's stated
   goals; use Claude's judgment to assess coverage

Mark a spec issue **ready to close** only if all three pass. Surface any failures with
the specific gap (which child issue is open and not in the Closes set, which plan is not done,
what scope is missing).

---

## Step 7 — Issue Linking and PR Promotion

Compile the **Closes set** from **`done` plans only** — `prd.json.plans[?status=="done"].issues`
— plus `prd.json.sdlc_finding_issues`. Step 6 counts spec children against this same set.
Do **not** include issues from `stalled` plans: a stalled plan did no work, so auto-closing its issues on merge would silently mark unimplemented
work as resolved. Those issues stay deliberately open (surfaced in Step 3 and Step 10).
`prd.json.sdlc_deferred_issues` is **never** added to the `Closes` block: those issues were
filed but not fixed in this iteration. Including the SDLC finding issues here guarantees they auto-close on merge even if the
commit(s) that addressed them didn't happen to use a closing keyword.

Optionally cross-check the computed list against the PR's `closingIssuesReferences` (fetched
in Step 2c) and confirm no `done`-plan issue is missing and no `stalled`-plan issue slipped in.

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
`<config-root>/plans/` removal commit from Step 4. `--delete-branch` removes the remote
integration branch automatically.

---

## Step 9 — Post-Merge Cleanup

Run all sub-steps in order.

### 9a — Close spec issues

Closure allow-list: only `prd.json.prd_issue` or a legacy `prd`-labelled issue, and only
after it passed all three checks in Step 6. Child `#N` refs in a spec body are state checks,
never closed here. A child Step 6 counted as covered by the Closes set should have closed on
the merge; if one is still open, list it on the Step 10 `Issues left open:` line rather than
closing it.

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

### 9e — Remove runtime artifacts

Only after Step 8's merge succeeded, on the default branch after 9c (so the ignore rules come
from that checkout). Removes `implementation-logs/`, `prd.json.lock`, `sdlc-review-findings.md`
and `pr-summary.md`, so the next iteration can't read this one's findings or summary:
```bash
python3 ~/.claude/scripts/clean-iteration-artifacts.py [--findings-filed]
```

Pass `--findings-filed` only if Step 5 filed or explicitly dismissed every finding — the
findings file is the only local copy of unfiled ones. The helper documents its safety rules
(symlinks, tracked files, held lock); don't restate or bypass them. If it exits non-zero,
report `Runtime artifacts:  cleanup failed (<first stderr line>)` and carry on. If
`~/.claude/scripts/clean-iteration-artifacts.py` is missing, re-run `setup-symlinks.sh` from
the claude-tools checkout first.

---

## Step 10 — Print Closing Report

```
=== Iteration Closed ===

Branch merged:       <integration_branch> → <default_branch>
PR:                  #<N> <title> (<url>)

Plans:               <done> done, <stalled> stalled, <total> total
Issues closed:       #N, #M, ...
Issues left open:    #N, #M (stalled plans — no work done)
                     #N — deferred by round cap / #N — minor rollup (one per line; never "none"
                     while any is open)
                     #N — spec child, still open after merge (Step 9a)
Spec issues closed:  #N, ...
Spec issues skipped: #N (reason: <gap>)

Branches deleted:    <list>
Worktrees removed:   <list>
Runtime artifacts:   removed: <a>, <b>
                     skipped: <path> (<reason>)   (one per skip)
<config-root>/plans/:  removed: yes (history on <integration_branch>)
                      — or — archived to <path>
```

Report exactly one of `removed: yes (history on <integration_branch>)` or `archived to <path>`;
never "removed: no".

For `Runtime artifacts`, echo the helper's output: reasons verbatim, names only, never
contents. Omit `absent` artifacts. A skipped `implementation-logs/` or findings file stays on
disk and is among the most sensitive artifacts (`docs/agents/PRIVACY.md`) — add a one-line hint
for it: for `findings unfiled`, file or dismiss the findings, then re-run the helper with
`--findings-filed`; for any other reason, delete it by hand.
