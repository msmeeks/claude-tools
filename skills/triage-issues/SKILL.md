---
name: triage-issues
description: Triage open GitHub issues, group into PR-sized workstreams, and write a plan file per group to meta/plans/, indexed in meta/plans/prd.json. Each plan includes /sdlc plan review findings and implementation steps. Also runs /sdlc plan on existing plans when invoked as /triage-issues review. Use when asked to triage issues, group issues into plans, plan the backlog, create workstream plans, or review existing plans.
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
2. Ensure `meta/plans/` directory exists (`mkdir -p meta/plans`). Check whether
   `meta/plans/prd.json` already exists — if so, its `plans` entries must be preserved/merged
   in Step 6, not overwritten.

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

Then write (or update) `meta/plans/prd.json` — the plan index that `run-next-plan.py` reads:

1. Read `meta/plans/prd.json` if it exists; parse as JSON.
2. For each group produced in Steps 3–5, build a plan entry: `{"file": "<slug>.md", "issues": [N, M, ...], "size": "S|M|L|XL", "status": "pending", "attempts": 0, "blocked_by": []}`.
3. Merge: if an entry with the same `file` already exists in `prd.json`, preserve its existing
   `status` and `attempts` values and overwrite all other fields with the freshly computed ones.
   If no entry exists for that `file`, add the new entry as-is (`status: "pending"`,
   `attempts: 0`).
4. Populate each entry's `blocked_by` array from the file-overlap/dependency analysis in
   Step 4 — list the `file` values of plans that must merge first.
5. Set the top-level `integration_branch` field to `"integration/batch"` if it is not already
   set.
6. Write the merged object back to `meta/plans/prd.json`.

**No `meta/plans/README.md` is written or updated by this skill.**

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

---

## Goal

[One sentence: the user-facing outcome when this plan is complete.]

---

## Context

[One paragraph: the user-facing problem, root cause, and intended outcome.]

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `path/to/file` | What changes and why |

### Steps

[Numbered steps. Reference existing functions/components. Describe approach clearly enough
for a fresh Claude session to execute without re-exploring the codebase.]

---

## Acceptance Criteria

- [ ] Criterion 1 (user-observable behaviour)
- [ ] Criterion 2
- [ ] Criterion 3

---

## Pre-Implementation Review

[Security / privacy / a11y / design findings from the /sdlc plan agents.
Omit this section entirely if all four agents returned no findings.]
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
