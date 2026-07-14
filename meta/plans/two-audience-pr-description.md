# Two-audience PR description in run-next-plan

**Size:** M

## Context

`run-next-plan.py` drives an iteration to completion but leaves the integration PR body
with only a machine-generated `## Closes` list. Reviewers (product and engineering) get no
human-readable summary of what shipped.

## What to build

At the tail of `run_docs_phase` (the point where the iteration is genuinely complete),
generate a PR summary for two audiences and splice it into the PR body:

- **For the Product Manager** — the PRD it implements (`prd_issue`), a brief overview,
  a bulleted list of user-facing changes, and a `- [ ]` checklist test plan for them.
- **For the Engineer** — the same shape for non-customer-facing/backend changes, with a
  test plan focused on manual-reviewer verification (edge cases hard to hit via UI/API,
  integration seams, architectural changes) rather than re-running CI.

## Implementation Notes

- Add optional `prd_issue` / `pr_number` to the `prd.json` schema.
- `resolve_pr_number` prefers `prd.json`'s `pr_number`, falls back to branch lookup.
- `splice_summary_block` is idempotent (marker-delimited), preserving `## Closes`.
- `plan-iteration` captures the PR number and PRD issue into `prd.json`.

## Acceptance criteria

- PR body contains a PM section and an Engineer section, above `## Closes`.
- Re-running the phase replaces the prior block rather than stacking.
- No open PR / empty summary warns and skips without failing the run.
