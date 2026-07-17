# Plan: Fix SDLC skill instructions

**Issues:** #44, #49, #50, #51

---

## Goal

The planning/close/triage skill instructions correctly describe the incremental-review-gate contract, so a session following them literally does not auto-close unimplemented issues, drop prd.json fields, or desync the review gate.

---

## Context

The incremental SDLC review gate added several new invariants that the surrounding skill markdown never captured. Four gaps let a literal reader corrupt an iteration: `/close-iteration` builds the PR `Closes` list from *all* plans regardless of status, so a `stalled` plan's issues get auto-closed on merge with no work done (#44); both planning skills' prd.json merge steps document preserving plan-*entry* fields but not top-level keys, so a reconstructed object can drop `last_reviewed_sha` and stall the runner's re-arm (#49); `/triage-pr-comments` Case 3 doesn't warn against touching `sdlc_review_status` when re-opening a plan (#50); and `/close-iteration` Step 2b doesn't note that `sdlc_review_status` legitimately cycles `complete → pending → complete` across rounds (#51). All fixes are edits to skill markdown — no code.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `skills/close-iteration/skill.md` | #44: scope `Closes` to `done` plans + surface stalled-plan open issues; #51: Step 2b cycle note |
| `skills/plan-iteration/SKILL.md` | #49: Step 7 preserve all top-level prd.json keys |
| `skills/triage-pr-comments/SKILL.md` | #49: Step 6 preserve top-level keys; #50: Case 3 must not touch `sdlc_review_status` |

### Steps

1. **#44 — `close-iteration` Closes scoping.** In `skills/close-iteration/skill.md` Step 7 (line ~200), build the `Closes` list from `plans[?status=="done"].issues` + `sdlc_finding_issues`, **not** `plans[*].issues`. For each `stalled` plan, list its issues as deliberately left open and surface them in the Step 10 report (`Issues left open:` line). In Step 3, add an explicit warning that prints stalled-plan-with-open-issues and why. Optionally cross-check the computed list against the PR's `closingIssuesReferences` and confirm any issue no commit references.
2. **#51 — `close-iteration` Step 2b cycle note.** Add a note that `sdlc_review_status` may cycle `complete → pending → complete` across incremental rounds; a transient `pending` on a re-armed round is normal, not an anomaly. The pass condition (`complete` with no remaining eligible plans) is unchanged.
3. **#49 — preserve top-level prd.json keys.** In `skills/plan-iteration/SKILL.md` Step 7 and `skills/triage-pr-comments/SKILL.md` Step 6, add an explicit instruction: **preserve all existing top-level prd.json keys; only modify `plans[]`.** Name the fields: `last_reviewed_sha`, `sdlc_review_status`, `sdlc_finding_issues`, `sdlc_review_completed_agents`, `pr_number`, `prd_issue`, `feature_branches`, `smoke_test`.
4. **#50 — `triage-pr-comments` Case 3 note.** In Step 2c Case 3, state that re-opening the plan (`status: "pending"`, `attempts: 0`) is sufficient — do **not** touch `sdlc_review_status`; the runner re-arms the gate and reviews only the new commits (`last_reviewed_sha..HEAD`). Explain why (the runner handles re-arm/bookkeeping; a manual reset hits the `save_prd` latch or desyncs round state).

Note this plan edits `skills/plan-iteration/SKILL.md` Step 7 — the same step that produced *this* prd.json. Apply the #49 edit consistently with how this iteration's prd.json is structured.

---

## Acceptance Criteria

- [ ] `close-iteration` Step 7 builds `Closes` from `done` plans + `sdlc_finding_issues` only; stalled plans' issues are listed as left-open in Step 10 and warned in Step 3.
- [ ] `close-iteration` Step 2b documents the `complete → pending → complete` cycle with the pass condition unchanged.
- [ ] `plan-iteration` Step 7 and `triage-pr-comments` Step 6 each instruct preserving all top-level prd.json keys (naming the eight fields), modifying only `plans[]`.
- [ ] `triage-pr-comments` Step 2c Case 3 states not to modify `sdlc_review_status` and why.
