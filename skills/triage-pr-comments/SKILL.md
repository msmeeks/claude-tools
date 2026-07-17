---
name: triage-pr-comments
description: Triage comments on open GitHub PRs and write a response plan per PR to meta/plans/, indexed in meta/plans/prd.json. Each plan uses the PR's existing branch and worktree, groups all reviewer comments into concrete implementation steps, and runs /sdlc plan review. Supports iterative review cycles — re-running adds new comments to existing plans and skips already-addressed ones. Use when asked to respond to PR feedback, address review comments, triage PR comments, action reviewer requests, or plan PR responses.
---

# Triage PR Comments

Reviews all open pull requests for the current project, collects unresolved reviewer comments,
and writes one ready-to-execute plan file per PR to `meta/plans/`. Plans reuse the PR's
existing branch and worktree — no new branch is created. Comments from different PRs are never
combined into a single plan.

Designed for iterative review cycles: triage → execute → reviewer adds comments → triage again.
Re-running updates existing plans with new comments rather than creating duplicates.

## Usage

```
/triage-pr-comments          — full mode: fetch PRs → filter → /sdlc plan review → write plans
/triage-pr-comments review   — re-run /sdlc plan review on existing PR-comment plan files
```

---

## Full Mode

### Step 1 — Bootstrap

1. Read `docs/llms.md`. If it doesn't exist, stop and tell the user to run `/sdlc` first.
2. Ensure `meta/plans/` directory exists (`mkdir -p meta/plans`).
3. Resolve `{owner}` and `{repo}` once for use in all `gh api` calls:
   ```bash
   gh repo view --json nameWithOwner --jq '.nameWithOwner'
   ```

### Step 2 — Fetch Open PRs and Their Comments

```bash
gh pr list --state open --limit 50 --json number,title,headRefName,baseRefName,author,assignees,labels
```

For each open PR, fetch all review and inline diff comments with their IDs:

```bash
# Inline diff comments — includes comment ID
gh api repos/{owner}/{repo}/pulls/<number>/comments \
  --jq '[.[] | {id,path,line,body,user:.user.login}]'

# Review-level (non-diff) comments
gh pr view <number> --json reviews,comments
```

Then check which threads are resolved via GraphQL:

```bash
gh api graphql -f query='
  query {
    repository(owner: "{owner}", name: "{repo}") {
      pullRequest(number: <number>) {
        reviewThreads(first: 100) {
          nodes { isResolved path line comments(first: 5) { nodes { body author { login } } } }
        }
      }
    }
  }
'
```

**Skip a PR entirely if** all its threads are resolved and there are no non-empty review body
comments. Print a compact table of PRs with unresolved comment counts.

### Step 2b — Filter Comments by Existing Reactions

For each unresolved comment, check its current reactions:

```bash
gh api repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions \
  --jq '[.[] | .content]'
```

Apply these filters:

| Reaction present | Action |
|-----------------|--------|
| `rocket` (🚀) | **Skip** — already addressed by a previous plan execution |
| `eyes` (👀) | **In-review** — currently referenced by an existing plan |
| neither | **New** — include in plan |

Collect three lists per PR: `new_comments`, `in_review_comments`, `addressed_comments`.

### Step 2c — Incremental Plan Update Logic

Check whether `meta/plans/pr-<N>-comments.md` already exists:

**Case 1 — No existing plan:** proceed to Steps 3–6 to create one.

**Case 2 — Plan exists, `new_comments` is empty:**
All open comments are already tracked (👀). Print a note; skip writing. Done for this PR.

**Case 3 — Plan exists, `new_comments` is non-empty (iterative round):**
New reviewer comments arrived since last triage. Update the existing plan:
- Append new rows to the appropriate Reviewer Comment tables (categorise as in Step 3)
- Update the `<!-- reactions: ... -->` metadata line to include the new comment IDs
- Add 👀 reactions to all new comment IDs (Step 2d below)
- If the plan's `meta/plans/prd.json` entry has `status: "done"`, reset `status` to
  `"pending"` and `attempts` to `0` (new comments re-open the work). This entry-level reset is
  **sufficient** — do **not** touch the top-level `sdlc_review_status` (or any other top-level
  gate field). The runner re-arms the gate on its own and reviews only the new commits
  (`last_reviewed_sha..HEAD`); a manual `sdlc_review_status` reset either hits the `save_prd`
  latch or desyncs round state.
- Leave existing rows and comment IDs unchanged

**Case 4 — Plan exists, some 👀 comments now have 🚀 (addressed outside the runner):**
They were resolved manually. Remove their rows from the plan tables, update the
`<!-- reactions: ... -->` metadata, and append a `## Changelog` section noting the removals.

### Step 2d — Add 👀 Reaction to New Comments

After deciding which comments will appear in the plan (code-change, test-change, question,
style, doc-change — but **not** wontfix), add the `eyes` reaction to each new comment ID:

```bash
gh api repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions \
  -f content="eyes"
```

### Step 3 — Categorise New Comments Per PR

Group new comments into action types:

| Action Type | Examples |
|-------------|---------|
| `code-change` | "rename this var", "extract to helper", "add null check" |
| `test-change` | "add a test for the edge case", "this branch isn't covered" |
| `question` | "why did you choose X?" — needs a reply, not code |
| `style` | lint/formatting nit the linter didn't catch |
| `doc-change` | "update the README", "add a JSDoc" |
| `wontfix` | clearly obsolete, thread resolved, line no longer exists |

Questions and wontfix items → **Conversation Responses** section (answer only, no code change).
Everything else → **Implementation Steps**.

### Step 4 — Explore Codebase Per PR

For each PR with new comments, dispatch one Explore agent with:
- The PR's head branch name and files mentioned in the comments
- Specific file paths from the inline diff comments

Collect: existing helpers to reuse, patterns the reviewer expects the fix to follow,
and whether any comment references a file outside the PR's current diff.

### Step 5 — /sdlc Plan Review Per PR

For each PR with new comments, dispatch four planning-review agents **in parallel**:

```
Agent(sdlc-security-reviewer): Review planned comment responses for PR #<N> (<title>).
Files affected: <list>. Reviewer requests: <summary>.
Identify OWASP Top 10 risks, auth/authz gaps, injection vectors, CVE-exposed deps.

Agent(sdlc-privacy-reviewer): Review planned comment responses for PR #<N>.
Files affected: <list>. Reviewer requests: <summary>.
Flag PII handling, consent flows, data minimization, retention concerns.

Agent(sdlc-accessibility-reviewer): Review planned UI comment responses for PR #<N>.
Files affected: <list>. Reviewer requests: <summary>.
Flag WCAG 2.2 AA issues: keyboard nav, color contrast, ARIA, focus management.

Agent(sdlc-design-reviewer): Review planned comment responses for PR #<N> against meta/DESIGN_BRIEF.md.
Files affected: <list>. Reviewer requests: <summary>.
Flag component reuse opportunities and design consistency risks.
```

Collect non-empty findings for the `## Pre-Implementation Review` section.
Omit that section if all four agents return no findings.

### Step 6 — Write Plan Files

Write one `meta/plans/pr-<number>-comments.md` per PR using the **Standard Plan Template**
below. The filename `pr-<N>-comments.md` is the stable identifier across all iterative rounds.

Then write (or update) `meta/plans/prd.json` — the same plan index `/triage-issues` and
`run-next-plan.py` read:

1. Read `meta/plans/prd.json` if it exists; parse as JSON.
2. For each PR with new/updated comments, build a plan entry: `{"file": "pr-<N>-comments.md", "type": "pr-comments", "pr": N, "size": "S|M|L", "status": "pending", "attempts": 0, "blocked_by": []}`.
3. Merge: if an entry with the same `file` already exists, preserve its existing `status`
   and `attempts` values and overwrite all other fields. If no entry exists for that `file`,
   add it as-is (`status: "pending"`, `attempts: 0`).
4. `blocked_by` is `[]` by default for PR-comment plans — they neither block nor are blocked
   by issue plans unless a cross-cutting note makes a dependency explicit.
5. **Preserve all existing top-level prd.json keys** — only modify `plans[]`. When rebuilding
   the object, carry through every key already present, including `last_reviewed_sha`,
   `sdlc_review_status`, `sdlc_finding_issues`, `sdlc_review_completed_agents`, `pr_number`,
   `prd_issue`, `feature_branches`, and `smoke_test`. Dropping any of these desyncs the runner's
   incremental review gate — e.g. losing `last_reviewed_sha` stalls the re-arm on the next round.
6. Write the merged object back to `meta/plans/prd.json`.

**No `meta/plans/README.md` is written or updated by this skill.**

---

## Review Mode (`/triage-pr-comments review [pr-number]`)

1. List `meta/plans/pr-*-comments.md`. If a PR number is given, review only that plan.
2. For each plan, read its content and dispatch the same four planning-review agents as Step 5,
   using the plan's **Files to Modify** table and **Reviewer Comments** section as input.
3. Print a per-plan findings summary. Suggest specific edits but do not auto-modify plan files.

---

## Standard Plan Template

````markdown
# Plan: PR #<N> — Address Review Comments

**PR:** #<N> <title>
**Open comments:** <count> (<code-change: N, test-change: N, question: N, style: N>)

---

## Context

[One paragraph: what the PR does, who reviewed it, what themes the review comments cover.]

---

## Reviewer Comments

[All unresolved comments — grouped by action type, never by reviewer. Comment IDs are included
so run-next-plan.py can post emoji reactions after successful execution.]

### Code Changes Required

| File | Line | Comment ID | Reviewer | Comment | Action |
|------|------|------------|----------|---------|--------|
| `path/to/file` | 42 | 1234567890 | @reviewer | "rename foo to bar" | Rename variable |

### Test Changes Required

| File | Comment ID | Reviewer | Comment | Action |
|------|------------|----------|---------|--------|
| `path/to/test` | 2345678901 | @reviewer | "add edge case for empty list" | Add test case |

### Conversation Responses Needed

| Thread | Comment ID | Reviewer | Comment | Planned Response |
|--------|------------|----------|---------|-----------------|
| `path/to/file:42` | 9876543210 | @reviewer | "why did you choose X?" | Explain rationale: ... |

### Style / Doc Nits

| File | Line | Comment ID | Comment | Action |
|------|------|------------|---------|--------|

---

## Files to Modify

| File | Change |
|------|--------|
| `path/to/file` | What changes and why |

---

## Implementation Steps

[Numbered steps. Each step resolves one or more comments — reference by Comment ID so it's
clear what's being addressed. Describe the approach clearly enough that a fresh session can
execute without re-exploring the codebase.]

[For conversation responses: include the exact text to post as a GitHub PR reply comment.]

---

## Pre-Implementation Review

[Security / privacy / a11y / design findings from the /sdlc plan agents.
Omit this section entirely if all agents returned no findings.]

<!-- reactions: rocket=<comma-separated comment IDs for code/test/style/doc changes> +1=<comma-separated comment IDs for conversation responses> -->
````

> The `<!-- reactions: ... -->` line is machine-readable — `run-next-plan.py` parses it after
> successful execution to post 🚀 reactions to code-change comments and 👍 reactions to
> conversation-response comments. Omit a key if the list is empty.

---

## Comment Collection Heuristics

**Mark as `wontfix` (skip 👀, add to Conversation Responses with a short note):**
- Thread already resolved in GitHub UI
- Reviewer left a `nit:` prefix and approved anyway
- Comment references a line that no longer exists in the latest push
- Comment is a question with no action implied (just answer it)

**Escalate to its own Implementation Step (don't bundle):**
- A comment that requires touching a file outside the PR's original diff
- A comment that implies a design change (flag to user before implementing)
- A security or privacy finding — treat as blocking

**Bundle into one Implementation Step:**
- Multiple style nits in the same file
- Rename requests across a single function's call sites
- Doc/comment updates with no logic change
