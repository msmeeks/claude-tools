---
name: plan-iteration
description: Backlog grooming entry point. Triages open GitHub issues one-by-one using /triage, groups ready-for-agent issues into logical implementation clusters, runs /sdlc plan review, and writes a plan file per cluster to meta/plans/. Use when asked to groom the backlog, plan the iteration, triage issues into plans, or group issues into workstreams.
---

# Plan Iteration

Grooms the open backlog end-to-end: triages each issue using `/triage`, groups
`ready-for-agent` issues into logical clusters, and writes a ready-to-execute plan
file per cluster to `meta/plans/`.

## Usage

```
/plan-iteration            — full mode: triage → group → /sdlc plan review → write plans
/plan-iteration review     — re-run /sdlc plan review on existing meta/plans/*.md
/plan-iteration --parallel — same as full mode but dispatches review agents in parallel
```

> **Sister skill:** `/triage-pr-comments` does the same for open PR reviewer comments —
> one plan per PR, reusing existing branches/worktrees.

---

## Full Mode

### Step 1 — Bootstrap

1. Read `docs/llms.md`. If it doesn't exist, stop and tell the user to run `/sdlc` first.
2. Ensure `meta/plans/` directory exists (`mkdir -p meta/plans`). Check whether
   `meta/plans/prd.json` already exists — if so, its `plans` entries must be preserved/merged
   in Step 7, not overwritten.

### Step 2 — Fetch Open Issues

```bash
gh issue list --state open --limit 100 --json number,title,labels,body,assignees,milestone
```

Print a compact table (number, title, current labels) so the triage pass is visible.

### Step 3 — Triage Each Issue

For every issue that lacks both a category label (`bug`/`enhancement`) and a state label
(`ready-for-agent`/`needs-info`/`wontfix`), invoke the `/triage` skill to run it through
the state machine:

- Gather context from the issue body and codebase.
- Recommend a category (`bug` / `enhancement`) and state.
- Check for redundancy (already implemented?) and prior rejection (`.out-of-scope/`).
- Apply the outcome:
  - `ready-for-agent` — post an agent brief; issue enters the planning pool.
  - `needs-info` — post triage notes; skip for this iteration.
  - `wontfix` — close with appropriate comment; skip for this iteration.

Issues already labeled `ready-for-agent` skip triage and go straight to the pool.
Issues labeled `needs-info` or `wontfix` are excluded from the planning pool.

After triage, print a summary table: pool of `ready-for-agent` issues and skipped issues.

### Step 4 — Explore Codebase

Group pool issues by likely domain area (auth, scheduling, data-layer, admin-ui, etc.),
then dispatch up to 3 Explore agents **in series** — one per domain area — to find:
- Existing components/functions to reuse
- File-level overlap between issues
- Key patterns the implementation should follow

Include specific file paths from `docs/llms.md` in each agent prompt.

### Step 5 — Group into Logical Clusters

Group `ready-for-agent` issues into clusters by logical domain area and implementation
theme — **not** by PR size. A cluster may span many files and multiple sub-features if
they belong to the same product area.

| Rule | Action |
|------|--------|
| Issues in the same domain area | Same cluster |
| Issues with a clear dependency order | Separate clusters; dependent gets a `Prerequisite` note |
| Bug fix that blocks other work | Own cluster, highest priority |
| Trivial (seed data, rename, config) | Bundle into nearest related cluster |
| Unrelated UX polish across areas | One `ux-polish` cluster |

Name each cluster with a descriptive slug: `feat/<area>`, `fix/<area>`, `refactor/<area>`.

### Step 6 — /sdlc Plan Review Per Cluster

For each cluster, dispatch four planning-review agents **in series** — wait for each result before starting the next. With `--parallel`, dispatch all four simultaneously:

```
Agent(sdlc-security-reviewer): Review planned changes for cluster "<name>".
Files affected: <list>. Intent: <one-line summary>.
Identify OWASP Top 10 risks, auth/authz gaps, injection vectors, CVE-exposed deps.

Agent(sdlc-privacy-reviewer): Review planned changes for cluster "<name>".
Files affected: <list>. Intent: <one-line summary>.
Flag PII handling, consent flows, data minimization, retention concerns.

Agent(sdlc-accessibility-reviewer): Review planned UI changes for cluster "<name>".
Files affected: <list>. Intent: <one-line summary>.
Flag WCAG 2.2 AA issues: keyboard nav, color contrast, ARIA, focus management.

Agent(sdlc-design-reviewer): Review planned changes for cluster "<name>" against meta/DESIGN_BRIEF.md.
Files affected: <list>. Intent: <one-line summary>.
Flag component reuse opportunities and design consistency risks.
```

Collect all non-empty findings for the `## Pre-Implementation Review` section.
If all four agents return no findings, omit that section.

### Step 7 — Write Plan Files

Write one `meta/plans/<slug>.md` per cluster using the **Standard Plan Template** below.

Then write (or update) `meta/plans/prd.json` — the plan index that `run-next-plan.py` reads:

1. Read `meta/plans/prd.json` if it exists; parse as JSON.
2. For each cluster, build a plan entry: `{"file": "<slug>.md", "issues": [N, M, ...], "size": "S|M|L|XL", "status": "pending", "attempts": 0, "blocked_by": []}`.
3. Merge: if an entry with the same `file` already exists, preserve its `status` and `attempts`; overwrite all other fields. If no entry exists, add it as-is.
4. Populate each entry's `blocked_by` array from the dependency analysis in Step 5 — list the `file` values of clusters that must merge first.
5. Write the merged object back to `meta/plans/prd.json`. (`integration_branch` is set by Step 8 below, once the real date-slugged branch name exists — don't stamp a placeholder here.)

**No `meta/plans/README.md` is written or updated by this skill.**

Size key: `S` (1–3 files), `M` (4–8 files), `L` (9–15 files), `XL` (16+ files or new infra).

### Step 8 — Create Integration Branch and Draft PR

1. Resolve the default branch:
   ```bash
   git symbolic-ref refs/remotes/origin/HEAD | sed 's|refs/remotes/origin/||'
   ```

2. Generate a unique integration branch name:
   `integration/YYYY-MM-DD-<primary-slug>`
   where `YYYY-MM-DD` is today's date and `<primary-slug>` is derived from the first
   cluster's name (e.g., `feat/auth-billing` → `auth-billing`). Sanitize to lowercase
   alphanumeric and hyphens only.

3. Create the branch from the default branch and push:
   ```bash
   git checkout -b <integration_branch> origin/<default_branch>
   git push -u origin <integration_branch>
   ```

4. Detect the smoke test command (check in order, stop at first match):
   - `package.json` → `scripts["test:smoke"]`, then `scripts["test"]`
   - `Makefile` → `smoke` target, then `test` target (`grep -m1 "^smoke:\|^test:" Makefile`)
   - `pyproject.toml` → `[tool.pytest.ini_options]` present → `python3 -m pytest`
   If none found, set `smoke_test` to `null` and warn the user to populate it manually
   in `prd.json` before running `/close-iteration`.

5. Open a draft PR:
   ```bash
   gh pr create --draft \
     --base <default_branch> \
     --head <integration_branch> \
     --title "Iteration: <comma-separated cluster titles>" \
     --body "$(cat <<'EOF'
   ## Plans
   <bulleted list of plan file names with their linked issue numbers>

   ## All Issues
   <bulleted list of every #N from all plan entries>
   EOF
   )"
   ```

6. Update `prd.json` with the new fields (merge into the existing object):
   - `integration_branch`: the generated branch name
   - `smoke_test`: the detected command string, or `null`
   - `feature_branches`: `[]`

---

## Review Mode (`/plan-iteration review [plan-name]`)

1. List `meta/plans/*.md`. If a plan name is given, review only that one.
2. For each plan, dispatch the same four planning-review agents as Step 6 (series by default; parallel with `--parallel`),
   using the plan's **Implementation Notes** and **Context** sections as input.
3. Print a per-plan findings summary. Suggest edits but do not auto-modify plan files.

---

## Standard Plan Template

````markdown
# Plan: <Title>

**Issues:** #N[, #M...]
[**Prerequisite:** <note — e.g. "complete feat/auth first">]

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

[Numbered steps. Reference existing functions/components by file path. Describe the approach
clearly enough that a fresh session can execute without re-exploring the codebase.]

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

**Same cluster signals:**
- Issues in the same product feature area
- Issues that share core domain models or services
- Bug fix + the feature it's broken in

**Separate cluster signals:**
- Issue B requires a schema or API that Issue A's cluster introduces
- Bug fix that must ship fast (don't let a large feature cluster delay it)
- Refactor that changes interfaces other clusters depend on

**Bundle into nearest cluster (trivial):**
- Seed data additions
- Single-field label changes
- Config or constant updates
