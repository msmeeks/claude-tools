# Plan: Fix runner SDLC-findings lifecycle

**Issues:** #47, #48

---

## Goal

Across multiple incremental SDLC review rounds in one iteration, each round files GitHub issues only for its own findings (no duplicates), while `prd.json.sdlc_finding_issues` accumulates the full iteration's finding issues for `/close-iteration` to consume.

---

## Context

The incremental review gate can run several rounds per iteration (re-armed when new plans are appended after a `complete` review). Two round-interaction bugs exist in `scripts/run-next-plan.py`. First, `meta/sdlc-review-findings.md` is *appended* every round and `_run_file_issues_phase` reads the whole file, so round 2 re-files round 1's findings as duplicate `sdlc-finding` issues (#48). Second, the gate clears `prd.json.sdlc_finding_issues` to `[]` at each round's terminal write — but `/close-iteration` reads that field as the iteration-cumulative record for its "findings addressed" gate and the PR `Closes` block, so after any completed gate the field is empty and finding issues silently drop out of the PR (#47).

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Rotate findings file per round; make `sdlc_finding_issues` cumulative with a separate per-round file guard |
| `scripts/tests/test_sdlc_gate.py` | Cover two-round gate: distinct non-duplicated issue sets + cumulative dedupe |

### Steps

1. **#48 — rotate the findings file per round.** In `run_sdlc_review_gate` (`run-next-plan.py:930`), clear/remove `meta/sdlc-review-findings.md` **once at the start of each round's review phase** — not per attempt, so a within-round serial-reviewer resume after a session-limit retry still appends correctly. `_run_review_phase` (875) then only ever writes the current round's findings, and `_run_file_issues_phase` (911) only ever sees them. Do the rotation safely (no symlink-follow / traversal on the fixed `meta/` path).
2. **#47 — keep `sdlc_finding_issues` cumulative.** Stop wiping the field to `[]` at round end (`run-next-plan.py:962`, `1027`) and in `_rearm_sdlc_review_gate` (`1145`). Instead, append this round's newly-filed issue numbers and dedupe against the existing list. Move the runner's per-round "already filed this round" guard onto a *separate scratch field* in `prd.json` (e.g. `sdlc_round_filed_issues`) so a re-armed round still files its own findings exactly once without re-filing prior rounds'. Ensure `save_prd` validation (line 193) accepts the new scratch field.
3. Confirm `/close-iteration` needs no change: Steps 2c/5/7 read `sdlc_finding_issues` and must now see the whole iteration's set.
4. Preserve all existing `save_prd` invariants (the `complete → pending` re-arm carve-out that requires `last_reviewed_sha`). Test-first via `test_sdlc_gate.py`; run `python3 -m pytest` from `scripts/`.

---

## Acceptance Criteria

- [ ] Each round's file-issues phase files issues only for that round's findings; no duplicate `sdlc-finding` issues across rounds of one iteration.
- [ ] Within-round resume after a session-limit retry still accumulates that round's findings (rotation is once-per-round, not per-attempt).
- [ ] `sdlc_finding_issues` accumulates across all rounds (deduped) and is never reset to `[]` mid-iteration.
- [ ] A re-armed round files its own new findings exactly once — no re-file of prior rounds', no skip of the new round's.
- [ ] Tests cover: two-round distinct issue sets, cumulative dedupe, and the per-round re-file guard.

---

## Pre-Implementation Review

**Security (sdlc-security-reviewer):**

- **High — symlink/TOCTOU on findings-file rotation.** `meta/sdlc-review-findings.md` is today written only by the `claude` subagent (`bypassPermissions`), never by Python. If Step 1's per-round rotation is done with naive Python I/O (`Path.write_text("")`, `os.remove`+recreate), a symlink swapped in by a prior round/turn could clobber a file outside the repo. **Mitigation:** either do the rotation via the `claude` prompt (consistent with how the file is otherwise touched), or, if in Python, use the existing "resolve under `repo_root`, refuse symlinks (`path.is_symlink()` / `os.path.lexists`), unlink-then-recreate" pattern already used by `_resolve_plan_path` (269) and the atomic-tempfile write in `_with_prd_lock` (257).
- **Informational — validate the new scratch field.** The per-round "already filed" scratch field must get an `isinstance` type-check in `_validate_prd_schema` (line 157), matching how `sdlc_finding_issues` (193) and `sdlc_review_completed_agents` (197) are validated — `prd.json` is LLM-written and not fully trusted.
- **Informational — re-check `save_prd` terminal-status guard.** Ensure the cumulative append/dedupe doesn't let the new scratch field bypass the `complete → pending` re-arm carve-out (line 239). Add a unit test asserting the terminal-status refusal still fires with the new field present/absent.
- **Medium (awareness) — cumulative issue list widens injection blast radius.** Keeping finding issues across rounds means a once-filed misleading finding stays in every later triage prompt this iteration. Low severity — only integers are interpolated (`parse_issue_numbers`, anchored `\d+`) — confirm the triage prompt handles stale/duplicate numbers safely. No command/argument injection: `gh issue create` content is mediated through the `claude` CLI (list-argv, no `shell=True`). Privacy/a11y/design: N/A (no user data, no UI).
