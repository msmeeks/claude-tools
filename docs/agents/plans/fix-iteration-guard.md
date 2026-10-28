# Plan: A CLOSED integration PR is not a finished iteration

**Issues:** #92, #93

---

## Goal

A closed-but-unmerged integration PR stops the runner with a reopen-or-archive message, and
`/plan-iteration` asks before archiving instead of silently starting fresh.

---

## Context

`_iteration_finished` in `scripts/run-next-plan.py` treats `CLOSED` like `MERGED`, so a PR
closed by mistake (or closed and replaced) makes `/plan-iteration` move live `prd.json` to
`.bak` without asking. The maintainer decided (#92, 2026-10-27): only MERGED, or a
pushed-then-deleted branch, is finished; CLOSED is an unresolved state the user settles. This
plan also takes #93's finished-iteration items (glossary wording, a missing guard test, the
reused-branch-name limit), which the maintainer said must follow #92's decision.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Split CLOSED out of `_iteration_finished` (L675-714); CLOSED-specific `die()` in `main()` before `_register_exit_flush` (L2181-2187) |
| `scripts/tests/test_orchestration.py` | Rework `test_iteration_guard_*` for the MERGED/CLOSED split; add #93's missing guard test |
| `scripts/tests/test_config_root.py` | L109 stubs `_iteration_finished` by name — update on rename / new return shape |
| `skills/plan-iteration/SKILL.md` | Step 1.2 (L41-56) and Step 7.5a (L160-172): CLOSED → ask, never auto-archive |
| `scripts/CONTEXT.md` | "Finished iteration" entry (L87-92); add a "Closed iteration" term if useful |
| `docs/features/run-next-plan.md` | "Finished-iteration guard" (L203-205), Tests paragraph mention (L237), reused-branch-name limit |

### Steps

1. **Return shape and name.** Today `_iteration_finished(data, branch) -> str | None` returns
   a reason and `main()` branches on truthiness. Return a frozen dataclass
   (`kind: Literal["finished", "closed"]`, `reason: str`) or `None`, and have `main()` test
   `is not None` explicitly — a tuple is too easy to misuse with `if x:`. Rename to
   `_iteration_state` (the old name is wrong for CLOSED) and update **every** site:
   the autouse fixture in `test_orchestration.py` (L29-34, keyed off the
   `test_iteration_guard` prefix), the stub in `test_config_root.py` L109, the references at
   `test_orchestration.py` L821/897/984/1003/1047 (L1047's `lambda …: finished` stub needs
   the new shape, not a string), `skills/plan-iteration/SKILL.md` L41, `scripts/CONTEXT.md`
   L91, and `docs/features/run-next-plan.md` L205/L237. Finish with
   `grep -rn _iteration_finished` → zero hits.
2. **Precedence.** Check the PR first (as now). `MERGED` with matching head and not
   cross-repo → `finished`. `CLOSED` with matching head and not cross-repo → `closed`, and
   return immediately — do **not** fall through to the branch-gone probe (#92 AC: CLOSED with
   the branch gone from origin is still CLOSED handling). Cross-repo or other-head PRs stay
   ignored. Branch-gone (`_branch_is_pushed or _upstream_gone`, then `ls-remote` rc 2) stays
   `finished`.
3. **`main()`** (L2181-2187): on `finished`, keep the existing message verbatim. On `closed`,
   `die()` with a distinct message mirroring the existing one, still before
   `_register_exit_flush`: `"prd.json at {prd_path} belongs to an unresolved iteration
   ({reason}); reopen the PR to continue, or run /plan-iteration to archive it and start a
   new one"` (reason is `PR #N was closed`, so don't say "closed" twice). Keep the actions in
   that order. Both paths apply under `--dry-run` too (unchanged). Keep the existing
   fail-open behaviour on `gh`/`ls-remote` errors — don't add a fail-closed path that blocks
   offline use.
4. **Docstrings.** Update the guard's docstring (L678 "merged or closed") and the
   `resolve_pr_number` docstring (L618-622, including "`include_finished` also finds merged
   and closed ones" for "the finished-iteration guard's case") so neither says closed means
   finished; call it the iteration-state guard.
5. **#93 reused-branch-name limit** (item g): pick the smaller change — document it. In
   `docs/features/run-next-plan.md`'s guard section, say that with no `pr_number`, the
   `--state all` lookup can match an older MERGED PR on a reused branch name and stop the new
   run; recording `pr_number` (which `/plan-iteration` Step 8 always does) avoids it. Say so
   in the commit message.
6. **Tests** (`test_orchestration.py` L785-1090):
   - Split the parametrized `test_iteration_guard_merged_or_closed_pr_with_matching_head_is_finished`
     (L829) into a MERGED → finished test and a CLOSED → closed test.
   - Add: CLOSED with the branch gone from origin → closed, not finished.
   - Keep cross-repo CLOSED ignored (L841) and other-head (L835) passing.
   - Name every new guard test `test_iteration_guard_*`; outside that prefix the autouse
     fixture stubs the guard and the test silently exercises nothing.
   - `test_iteration_guard_dies_before_the_exit_flush_is_registered` (L1062): add a CLOSED
     variant asserting the reopen/archive message, `/plan-iteration`, and that
     `_register_exit_flush` was never called, for `[]` and `["--dry-run"]`.
   - #93 item b: make `test_iteration_guard_branch_gone_from_origin_is_finished` (L857) set
     `upstream=True` explicitly instead of relying on the `_fake_gh_and_ls_remote` default,
     and add a test for `ls-remote` rc 2 + pushed branch + an OPEN PR found by branch lookup
     with `pr_number` absent. Pin whatever the code does after step 2 (an open PR doesn't
     short-circuit the branch-gone probe today — confirm and assert).
7. **`skills/plan-iteration/SKILL.md`**:
   - Step 1.2: "Over means the integration PR is `MERGED` …, or the branch was pushed and is
     gone on origin". Add a CLOSED bullet: same-repo, matching head, `CLOSED` → **ask** the
     user: continue (they reopen the PR; take the merge case) or archive and start fresh
     (take the fresh case). Tell the user that "continue" means the runner keeps refusing
     until the PR is reopened. With no one to ask, stop — reuse the existing "no one to ask"
     phrasing (SKILL.md ~L86). CLOSED takes precedence over branch-gone. Reuse the two
     existing print-line shapes rather than a new format:
     `fresh prd.json (previous iteration closed, archived at user's request: <reason>)` and
     `merging into existing prd.json (integration PR closed; user will reopen it)`, plus a
     stop line for the no-one-to-ask case.
   - Step 7 item 1 and 5a: the fresh case runs on MERGED/branch-gone, or on CLOSED only after
     the user chose archive.
   - Note: this file is symlinked live into `~/.claude/skills/`; the edit takes effect
     immediately.
8. **Docs**: `scripts/CONTEXT.md` "Finished iteration" → "A `prd.json` whose same-repo
   integration PR was merged, or whose pushed branch is gone from origin…"; add one sentence
   (not a new glossary term) saying a closed PR is not finished and what the runner and
   `/plan-iteration` do instead. This also
   covers #93's "reword Finished iteration" item. Update `docs/features/run-next-plan.md`
   L205 and the Tests sentence at L237 ("merged/closed/open PR") to match.
   `skills/close-iteration/skill.md` has no merged-or-closed wording — leave it.
9. Tick #92's and #93's items in commit messages (`Refs #92, #93`); #93's first item
   (`resolve_pr_number` only finding open PRs) was already fixed by PR #83 — say so.

---

## Acceptance Criteria

- [ ] MERGED still stops the runner with the existing finished message; `/plan-iteration` Step 1.2 takes the fresh case.
- [ ] CLOSED (same repo, matching head) stops the runner with the reopen-or-archive message: no wip commit, no push, `_register_exit_flush` never called — with and without `--dry-run`.
- [ ] CLOSED with the branch gone from origin is handled as CLOSED, not finished.
- [ ] A cross-repo CLOSED PR is ignored.
- [ ] `/plan-iteration` Step 1.2 / 7.5a never archives on CLOSED without asking, and stops with no one to ask.
- [ ] `scripts/CONTEXT.md`, `docs/features/run-next-plan.md` and the plan-iteration skill agree on the rule; the reused-branch-name limit is documented.
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass.

---

## Pre-Implementation Review
All findings below are folded into the steps above.

- **sdlc-security-reviewer:** findings
  - low (Steps 1-3): keep the existing fail-open behaviour on `gh`/`ls-remote` errors; don't add a fail-closed path that blocks offline use.
  - low (Step 3): `die()` interpolates the PR number and branch; terminal only, and git ref rules forbid control characters — no action.
- **sdlc-privacy-reviewer:** N/A: the change only reworks the closed-vs-merged PR state check in the runner's guard, its `die()` message, tests and skill/docs wording, so it handles no personal data, consent, analytics or retention.
- **sdlc-accessibility-reviewer:** no findings (plain-text stderr; keep the two actions in a fixed order)
- **sdlc-design-reviewer:** findings (no design brief; reviewed against existing conventions)
  - major (Step 1): the rename must update the `test_config_root.py` stub and every name reference in tests, SKILL.md, CONTEXT.md and the feature doc.
  - minor (Step 1): a frozen dataclass plus an explicit `is not None`, not a tuple; the L1047 stub needs the new shape.
  - minor (Step 3): mirror the existing message and don't say "closed" twice.
  - minor (Step 7): reuse the two existing print-line shapes and the "no one to ask" phrasing; explain that "continue" keeps the runner refusing until the PR is reopened.
  - minor (Steps 4/8): reword the `resolve_pr_number` docstring's `include_finished` wording too.
  - minor (Step 8): one sentence under "Finished iteration" rather than a new glossary term.
  - minor (Step 6): keep new tests under the `test_iteration_guard_` prefix.
