# Plan: Ralph Loop — Update /plan-iteration to write prd.json

**Issues:** #5
**Branch:** `feat/ralph-plan-iteration-prd-json`
**Base:** `main`
**Status:** done
**Prerequisite:** Branch off `main` after #2 merges (prd.json schema defined).
**Status:** done

---

## Worktree Setup

```bash
# Run from the repo root — only after feat/ralph-prd-json-data-layer merges
git worktree add .claude/worktrees/claude-tools-plan-iteration-prd -b feat/ralph-plan-iteration-prd-json main
```

**Working directory:** `.claude/worktrees/claude-tools-plan-iteration-prd`

When the PR merges:
```bash
git worktree remove .claude/worktrees/claude-tools-plan-iteration-prd
```

---

## Context

`/plan-iteration` currently produces `meta/plans/README.md` (a Markdown table with ordering) and verbose plan files with Worktree Setup, Branch/Base/Status frontmatter, and Review & Testing Workflow sections. The Ralph loop needs `prd.json` as the plan index. Plan files should be lean — only what Claude needs to implement the work. This slice rewrites Step 6 of the skill and the Standard Plan Template accordingly.

---

## Files to Modify

| File | Change |
|------|--------|
| `skills/plan-iteration/SKILL.md` | Update Step 6 (Write Plan Files): replace README Template with prd.json write/merge logic; replace Standard Plan Template with simplified 4-section template |

---

## Implementation Steps

1. **Replace Step 6 — Write Plan Files** in `skills/plan-iteration/SKILL.md`:

   **prd.json write/merge logic:**
   - Read `meta/plans/prd.json` if it exists; parse as JSON
   - For each new plan group from Steps 3–5: if a plan entry with the same `file` already exists in `prd.json`, preserve its `status` and `attempts` fields; update all other fields. If it does not exist, add a new entry with `status: "pending"`, `attempts: 0`.
   - Write the merged result back to `prd.json`
   - Set `integration_branch` at the top level to `"integration/batch"` if not already set
   - Populate `blocked_by` arrays from the cross-cutting notes generated in Step 4 (file-overlap analysis → dependency ordering)

   **Remove:** README Template entirely. No more `meta/plans/README.md` writes.

2. **Replace Standard Plan Template** with simplified 4-section format:

```markdown
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
```

   **Remove from template:** Worktree Setup, `**Branch:**`, `**Base:**`, `**Status:**`, Review & Testing Workflow, Verification Checklist, all `git worktree` commands.

   **Keep:** `**Issues:**`, Pre-Implementation Review section.

3. **Update skill description** in YAML frontmatter — remove references to worktree setup and README.md output; add reference to prd.json.

4. **Update Step 1 (Bootstrap)** — change `meta/plans/README.md` existence check to `meta/plans/prd.json`.

5. **Keep `/plan-iteration review` mode unchanged** — it reads plan files and dispatches review agents; no changes needed.

---

## Pre-Implementation Review

No security, privacy, accessibility, or design findings. This slice modifies only a Markdown skill definition file. The prd.json schema itself is defined and validated in #2.

---

## Review & Testing Workflow

### 1. Lint
```bash
python3 -m ruff check scripts/
```
(No Python changes in this slice — ruff is a sanity check only.)

### 2. Manual smoke test
Run `/plan-iteration` against a test repo with a few open GitHub issues. Verify:
- `meta/plans/prd.json` created with correct schema
- Plan files use the simplified 4-section template (no Worktree Setup)
- Re-running does not clobber existing `status`/`attempts` in `prd.json`

### 3. Push branch and open PR
```bash
git push -u origin feat/ralph-plan-iteration-prd-json
gh pr create --base main --title "feat: /plan-iteration writes prd.json with simplified plan templates" --body "Closes #5"
```

---

## Verification Checklist

- [ ] `skills/plan-iteration/SKILL.md` Step 6 writes/merges `prd.json`
- [ ] `prd.json` entries have `file`, `issues`, `size`, `status`, `attempts`, `blocked_by`
- [ ] Re-run preserves existing `status` and `attempts`
- [ ] `blocked_by` arrays populated from cross-cutting notes
- [ ] Generated plan files contain only: Goal, Context, Implementation Notes, Acceptance Criteria, Pre-Implementation Review
- [ ] No plan file contains Worktree Setup, Branch, Base, Status frontmatter, or Review & Testing Workflow
- [ ] `README.md` no longer written by the skill
- [ ] `/plan-iteration review` mode still works
