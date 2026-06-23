---
name: triage-issues
description: Triage open GitHub issues, group into PR-sized workstreams, and write a plan file per group to meta/plans/. Each plan includes worktree setup, /sdlc plan review findings, implementation steps, Playwright testing on the dev branch, and /pr-image-upload checklist. Also runs /sdlc plan on existing plans when invoked as /triage-issues review. Use when asked to triage issues, group issues into plans, plan the backlog, create workstream plans, or review existing plans.
---

# Triage Issues

Groups open GitHub issues into PR-sized workstreams and writes a ready-to-execute plan file
per group to `meta/plans/`. Each plan is self-contained: a new Claude Code session can pick
it up and execute it end-to-end without additional context.

## Usage

```
/triage-issues          — full mode: fetch → explore → group → /sdlc plan review → write plans
/triage-issues review   — review existing meta/plans/*.md with /sdlc plan
```

> **Sister skill:** `/triage-pr-comments` does the same for open PR reviewer comments —
> one plan per PR, reusing existing branches/worktrees.

---

## Full Mode

### Step 1 — Bootstrap

1. Read `docs/llms.md`. If it doesn't exist, stop and tell the user to run `/sdlc` first to
   initialise the docs directory.
2. Ensure `meta/plans/` directory exists (`mkdir -p meta/plans`).

### Step 2 — Fetch Open Issues

```bash
gh issue list --state open --limit 100 --json number,title,labels,body,assignees,milestone
```

Print a compact table (number, title, rough complexity) so the grouping rationale is visible.

### Step 3 — Explore Codebase

Group the fetched issues by likely code area (schedule, auth, backend-data, frontend-admin,
etc.), then dispatch up to 3 Explore agents **in parallel** — one per code area — to find:
- Existing components/functions to reuse
- File-level overlap between issues (merge-conflict risk if worked simultaneously)
- Key patterns the implementation should follow

Include specific file paths in each agent prompt based on the issue titles and `docs/llms.md`.

### Step 4 — Group Issues

Apply these rules to form groups:

| Rule | Action |
|------|--------|
| Issues touch the same file(s) | Same group — avoids conflicts |
| Trivial issue (seed data, rename, config) | Bundle with nearest related group |
| Large independent feature | Own group |
| Issue B depends on Issue A merging first | Separate groups; B gets a rebase note |
| Multiple small unrelated UX fixes | One "ux-polish" group |

Name each group with a branch slug: `fix/<slug>`, `feat/<slug>`, `refactor/<slug>`.

### Step 5 — /sdlc Plan Review Per Group

For each group, dispatch four planning-review agents **in parallel**:

```
Agent(sdlc-security-reviewer): Review the planned changes for group "<name>".
Files affected: <list>. Intent: <one-line summary>.
Identify OWASP Top 10 risks, auth/authz gaps, injection vectors, CVE-exposed deps.

Agent(sdlc-privacy-reviewer): Review planned changes for group "<name>".
Files affected: <list>. Intent: <one-line summary>.
Flag PII handling, consent flows, data minimization, retention concerns.

Agent(sdlc-accessibility-reviewer): Review planned UI changes for group "<name>".
Files affected: <list>. Intent: <one-line summary>.
Flag WCAG 2.2 AA issues: keyboard nav, color contrast, ARIA, focus management.

Agent(sdlc-design-reviewer): Review planned changes for group "<name>" against meta/DESIGN_BRIEF.md.
Files affected: <list>. Intent: <one-line summary>.
Flag component reuse opportunities and design consistency risks.
```

Collect all non-empty findings. They populate the `## Pre-Implementation Review` section of
the plan file. If all four agents return no findings, omit that section entirely.

### Step 6 — Write Plan Files

Write one `meta/plans/<slug>.md` per group using the **Standard Plan Template** below.

Then write (or update) `meta/plans/README.md` using the **README Template** below. Row order
must match the **Suggested Order** list — `run-next-plan.sh` picks plans top-to-bottom.

#### README Template

```markdown
# <Project> — Implementation Plans

<One sentence: how many workstreams, how many issues, where to start.>

| Plan | Branch | Issues | Size | Status |
|------|--------|--------|------|--------|
| [<slug>.md](<slug>.md) | `<branch>` | #N[, #M] | S/M/L/XL | pending |

## Suggested Order

1. **`<branch>`** — <one-line rationale, e.g. "unblocks all other features">
2. **`<branch>`** + **`<branch>`** — Can run in parallel (no file overlap)
...

## Cross-cutting Notes

- <Any files touched by multiple plans — merge conflict risk>
- <DB migration numbering, shared config, etc.>
```

**Rules:**
- `Status` column is required; always set to `pending` for new plans.
- Rows must be ordered by suggested execution sequence (bugs first, then features, XL plans last).
- The `| Plan |` cell must use `[filename.md](filename.md)` link syntax so `run-next-plan.sh` can parse it.
- Size values: `S` (1–3 files), `M` (4–8 files), `L` (9–15 files), `XL` (16+ files or new infra).

---

## Review Mode (`/triage-issues review [plan-name]`)

1. List `meta/plans/*.md` (skip `README.md`). If a plan name is given, review only that one.
2. For each plan, read its content and dispatch the same four planning-review agents as Step 5
   above, using the plan's **Files to Modify** table and **Context** section as input.
3. Print a per-plan findings summary. Suggest specific edits but do not auto-modify plan files
   — let the user decide what to incorporate.

---

## Standard Plan Template

````markdown
# Plan: <Title>

**Issues:** #N[, #M...]
**Branch:** `<type>/<slug>`
**Base:** `staging`
**Status:** pending
[**Priority:** <note> | **Prerequisite:** <note — e.g. "branch off staging after #N merges">]

---

## Worktree Setup

```bash
# Run from the repo root
git worktree add .claude/worktrees/hospitality-<slug> -b <branch>
```

**Working directory:** `.claude/worktrees/hospitality-<slug>`

When the PR merges:
```bash
git worktree remove .claude/worktrees/hospitality-<slug>
```

---

## Context

[One paragraph: the user-facing problem, root cause, and intended outcome.]

---

## Files to Modify

| File | Change |
|------|--------|
| `path/to/file` | What changes and why |

---

## Implementation Steps

[Numbered steps. Reference existing functions/components by file path. Describe the approach
clearly enough that a fresh session can execute without re-exploring the codebase.]

---

## Pre-Implementation Review

[Security / privacy / a11y / design findings from the /sdlc plan agents.
Omit this section entirely if all agents returned no findings.]

---

## Review & Testing Workflow

### 1. Run /sdlc
```
/sdlc
```
Includes lint and ruff. Address all findings before pushing.

### 2. Push Branch & Open PR
```bash
git push -u origin <branch>
gh pr create --base staging --title "<title>" --body "Closes #N"
gh pr edit --add-label deploy
```

### 3. Resolve Merge Conflicts & Deployment Issues
```bash
git fetch origin && git merge origin/staging   # use rebase if noted in Prerequisite above
```
- Wait for the dev environment to be healthy:
  `curl https://hospitality-api-dev-<slug>.fly.dev/api/v1/health`
- If deploy fails, check Fly.io logs before testing:
  `flyctl logs -a hospitality-api-dev-<slug>`

### 4. Test on Dev Environment Using Playwright
Navigate to `https://hospitality-app-dev-<slug>.fly.dev` and run through the checklist below.
Capture a screenshot with `browser_take_screenshot` after each visual check.

### 5. Upload Screenshots & Update PR
```
/pr-image-upload
```
Paste the returned `![caption](url)` tags into the PR description or a follow-up comment.

---

## Verification Checklist

- [ ] `/sdlc` review complete — all findings addressed (includes lint + ruff)
- [ ] <specific check> *(screenshot)*
- [ ] <specific check>
- [ ] Screenshots uploaded to PR via `/pr-image-upload`
````

---

## Grouping Heuristics Reference

**Conflict-risk signals** (put in same group or note dependency):
- Two issues edit the same large file (e.g. a 2000-line page component)
- One issue adds a new API endpoint another issue consumes
- One issue refactors a component another issue extends

**Good bundle candidates** (trivial issues to attach to a related group):
- Seed data additions
- Single-field UI label changes
- Config or constant updates

**Keep separate** (own group):
- Bug fixes (merge quickly; don't let features block them)
- Issues spanning the full stack with no shared files
- Issues > ~5 files changed that are unrelated in UX flow
