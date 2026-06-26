# Plan: Ralph Loop — Update /triage-pr-comments to write prd.json

**Issues:** #6
**Branch:** `feat/ralph-triage-pr-comments-prd-json`
**Base:** `main`
**Status:** done
**Prerequisite:** Branch off `main` after #5 merges.
**Status:** done

---

## Worktree Setup

```bash
# Run from the repo root — only after feat/ralph-plan-iteration-prd-json merges
git worktree add .claude/worktrees/claude-tools-triage-pr-prd -b feat/ralph-triage-pr-comments-prd-json main
```

**Working directory:** `.claude/worktrees/claude-tools-triage-pr-prd`

When the PR merges:
```bash
git worktree remove .claude/worktrees/claude-tools-triage-pr-prd
```

---

## Context

`/triage-pr-comments` currently appends a separate "PR Response Plans" table to `meta/plans/README.md`. PR-comment plans and issue plans should live in the same `prd.json` queue so the Ralph loop can schedule them together. This slice updates Step 6 to merge PR-comment entries into `prd.json` and simplifies the plan file template by removing the Worktree section — while preserving all the incremental-update, reaction-tracking, and review-mode logic that makes the skill useful across multiple review cycles.

---

## Files to Modify

| File | Change |
|------|--------|
| `skills/triage-pr-comments/SKILL.md` | Update Step 6: replace README Template with prd.json merge; add `"type": "pr-comments"` field; simplify plan file template |

---

## Implementation Steps

1. **Replace Step 6 — Write Plan Files** in `skills/triage-pr-comments/SKILL.md`:

   **prd.json merge logic** (same pattern as #5):
   - Read `meta/plans/prd.json` if it exists; parse as JSON
   - For each PR with new/updated comments: if an entry with the same `file` (`pr-<N>-comments.md`) already exists, preserve its `status` and `attempts`; update other fields. If it does not exist, add with `status: "pending"`, `attempts: 0`.
   - Each PR-comment entry must include `"type": "pr-comments"` — this replaces the `PR_COMMENT_PLAN_RE` filename regex used in the current `run-next-plan.py`.
   - Write merged result back to `prd.json`.
   - `blocked_by`: leave empty `[]` for PR-comment plans by default (they do not block issue plans and are not blocked by them unless a cross-cutting note makes a dependency explicit).

   **Remove:** README Template (PR Response Plans section). No more `meta/plans/README.md` appends.

2. **Simplify the Standard Plan Template** — apply same philosophy as #5:

   **Keep:** PR metadata (`**PR:**`, `**Open comments:**`), reviewer comment tables (Code Changes, Test Changes, Conversation Responses, Style/Doc Nits), Files to Modify table, Implementation Steps, Pre-Implementation Review, and the `<!-- reactions: ... -->` machine-readable metadata line.

   **Remove:** Worktree section (`git worktree add` commands), `**Branch:**`, `**Base:**`, `**Status:**`, Review & Testing Workflow section, Verification Checklist.

   The `<!-- reactions: ... -->` line must remain — `run-next-plan.py` (post #3 rewrite) no longer posts reactions (that code was removed), but `/triage-pr-comments`'s own incremental-update logic still uses reaction state to filter already-addressed comments. Keep it.

3. **Update Step 2c (Incremental Plan Update Logic)** — Case 3 previously reset `README.md` Status cell to `pending`; replace with: update the plan's `prd.json` entry `status` to `"pending"` and `attempts` to `0` when new comments arrive on a `done` plan.

4. **Update skill description** in YAML frontmatter — remove references to README.md; add prd.json.

5. **Keep unchanged:** Steps 2–2d (fetch, filter by reactions, incremental update cases 1–4, add 👀 reactions), Step 3 (categorise comments), Step 4 (explore codebase), Step 5 (/sdlc plan review agents), `/triage-pr-comments review` mode.

---

## Pre-Implementation Review

No security, privacy, accessibility, or design findings. This slice modifies only a Markdown skill definition file. The `<!-- reactions: ... -->` metadata line is preserved, maintaining the existing emoji-reaction workflow for tracking addressed comments.

---

## Review & Testing Workflow

### 1. Lint
```bash
python3 -m ruff check scripts/
```

### 2. Manual smoke test
Run `/triage-pr-comments` against a repo with open PRs that have reviewer comments. Verify:
- `meta/plans/prd.json` updated with `pr-<N>-comments.md` entries having `"type": "pr-comments"`
- Issue plan entries in `prd.json` not overwritten
- Generated `pr-<N>-comments.md` files have reviewer comment tables and `<!-- reactions: ... -->` but no Worktree section
- Re-running a done plan that gets new comments resets `status` to `pending` and `attempts` to `0`
- `README.md` not written or modified

### 3. Push branch and open PR
```bash
git push -u origin feat/ralph-triage-pr-comments-prd-json
gh pr create --base main --title "feat: /triage-pr-comments writes into prd.json with simplified templates" --body "Closes #6"
```

---

## Verification Checklist

- [ ] `skills/triage-pr-comments/SKILL.md` Step 6 merges into `prd.json`
- [ ] Each PR-comment entry has `"type": "pr-comments"` field
- [ ] Existing issue plan entries in `prd.json` are untouched
- [ ] Re-run preserves existing `status` and `attempts` for unchanged plans
- [ ] New comments on a `done` plan reset `status` to `pending` and `attempts` to `0`
- [ ] Generated plan files contain reviewer comment tables and `<!-- reactions: ... -->`
- [ ] No plan file contains Worktree section, Branch/Base/Status frontmatter, or Review & Testing Workflow
- [ ] `README.md` not written or modified by the skill
- [ ] `/triage-pr-comments review` mode unchanged
- [ ] Incremental update logic (Cases 1–4) and reaction filtering unchanged
