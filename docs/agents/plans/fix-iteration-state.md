# Plan: Iteration state survives cleanly between iterations

**Issues:** #78, #76

Do #78 first, then #76. Both touch `prd.json` state handling in `scripts/run-next-plan.py` and the
same `/close-iteration` / `/plan-iteration` steps. Line numbers are against `main` @ 3eea893; re-locate
by function or heading if they have moved.

---

## Goal

A finished iteration's review state never leaks into the next one, and every issue the review gate
files — including final-round and minor-rollup issues — is recorded so `/close-iteration` neither
misses nor duplicates it.

---

## Context

Two failures from the 2026-10-26 end-to-end test (`Hospitality-Delivered/zz-quickstart-test-20261026`).
(#78) On the cap round, `_run_file_issues_phase` writes filed issue numbers only to the per-round
scratch `sdlc_round_filed_issues` (deliberately, so the PR never `Closes` unfixed findings, #47/#44),
and the gate's completion write clears it; `MINOR_ROLLUP: N` is never parsed. `/close-iteration` then
re-filed a duplicate and reported "Issues left open: none". The cap message in
`_rearm_sdlc_review_gate` also falls back to `sdlc_finding_issues`, listing the issues the PR *is*
fixing. (#76) When plans end up untracked, `/close-iteration`'s `git rm -r` no-ops and `prd.json`
survives; the next `/plan-iteration` merges into it, inheriting `sdlc_review_rounds` at the cap, so the
new iteration gets no review. Maintainer decision on #76: plans stay **git-tracked** on the integration
branch — the issue body's "change 0" (exclude `plans/`) is dropped; everything else is a fallback for
repos where plans end up untracked anyway, plus a stale-`prd.json` guard.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | `sdlc_deferred_issues` key, `MINOR_ROLLUP` parsing, cap-message fix (#78); `_iteration_finished` helper + runner guard (#76) |
| `scripts/tests/test_sdlc_gate.py` | Final-round, rollup, schema, re-arm cap-message tests (#78) |
| `scripts/tests/test_orchestration.py` | Runner-guard tests; stub `gh`/`git ls-remote` in existing `main()` tests (#76) |
| `scripts/tests/test_config_root.py` | Stub the guard's subprocess calls in existing `main()` tests (L269, L328) |
| `skills/close-iteration/skill.md` | Step 5 reconcile, Step 3/10 "Issues left open", Step 7 exclusion (#78); Step 4 archive fallback, Step 10 report (#76) |
| `skills/plan-iteration/SKILL.md` | Step 1.2 finished-iteration check, Step 7.5 fresh-vs-merge + preserve list (#76, #78) |
| `docs/features/run-next-plan.md` | Key table, final-round deferral, archive fallback, finished-iteration check, runner guard |
| `docs/agents/triage-labels.md` | `sdlc-finding` paragraph (L14-18) names `sdlc_deferred_issues` |
| `docs/agents/README.md` | "Not publishable" section: tracked vs gitignored split |
| `CONTEXT-MAP.md` | "Not publishable" callout (L7-12): same split |
| `global/CLAUDE.md` | L72 sentence only, in its own commit |

### Steps

**Part 1 — #78: record deferred and rollup issues**

1. **Rollup parsing.** Next to `ISSUE_NUMBER_RE` (`scripts/run-next-plan.py` L562), add
   `MINOR_ROLLUP_RE = re.compile(r"^MINOR_ROLLUP:\s*#?(\d+)\s*$", re.MULTILINE)` and a
   `parse_minor_rollup(text) -> int | None` that takes the **last** match and rejects `0`. Keep it
   separate from `parse_issue_numbers` (L566): a rollup number must never reach `ISSUE:` parsing or a
   `Closes` line.
2. **Schema.** In `_validate_prd_schema` (L169), validate `sdlc_deferred_issues` exactly like
   `sdlc_finding_issues` (L205-208): a list of ints, bools rejected.
3. **Record.** In `_run_file_issues_phase` (L1430-1508), inside `mutate` (L1493-1505) and **before**
   the `if final_round` early return (L1495-1500):
   - if `final_round`, append that round's `ISSUE:` numbers to `sdlc_deferred_issues`;
   - on every round, append the parsed rollup number if present (a missing line is fine).
   Dedupe, preserving order. Leave `sdlc_round_filed_issues` and the #47/#44 behaviour as is. The write
   already runs under `_with_prd_lock` (L338).
4. **Keep it.** The completion `mutate` in `run_sdlc_review_gate` (L1626-1637) and the empty-increment
   path (L1544-1547) clear only `sdlc_round_filed_issues`. Confirm neither touches the new key.
5. **Cap message.** `_rearm_sdlc_review_gate` (L1788): the "Findings deferred to a human" message
   (L1804) lists `sdlc_deferred_issues`, one `#N` per line, and no longer falls back to
   `sdlc_finding_issues`. Plain text, no colour-only meaning.
6. **Never `Closes`.** Wherever the PR-summary `Closes` list is built from `sdlc_finding_issues`,
   confirm `sdlc_deferred_issues` is not included. Add a test that asserts it.
7. **Tests** (`scripts/tests/test_sdlc_gate.py`, reusing `_fake_gate_claude` L734, `_run_gate` L742,
   `_completed_round_prd` L786, and the final-round tests at L842/L870/L894 and rollup tests at
   L1109/L1123/L1140):
   - a final round records its issues in `sdlc_deferred_issues` and not in `sdlc_finding_issues`;
   - a rollup is recorded on a non-final and on a final round; a missing rollup line is fine;
     `MINOR_ROLLUP: 0`, a trailing-junk line, and two rollup lines (last wins) behave as specified;
   - a rollup number never appears in `parse_issue_numbers` output or a `Closes` line;
   - re-arm keeps `sdlc_deferred_issues`; the cap message lists it (extend
     `test_rearm_suppression_logs_the_deferred_issue_numbers` L813);
   - schema rejects a non-list, a list containing a str, and a list containing `True`
     (next to the schema tests at L106/L115).
8. **close-iteration** (`skills/close-iteration/skill.md`):
   - **Step 5** (L170-183): before filing any follow-up for a finding, reconcile against
     `gh issue list --label sdlc-finding --state open --json number,title` plus
     `prd.json.sdlc_deferred_issues`. A finding already covered is not re-filed; name the existing issue.
   - **Step 3** (L116-131) and **Step 10** (L289-306, "Issues left open" at L299): list each still-open
     `sdlc_deferred_issues` entry as `#N — deferred by round cap` or `#N — minor rollup`. Never print
     "none" while any is open.
   - **Step 7** (L207-232): state that `sdlc_deferred_issues` is never added to the `Closes` block.
9. **Docs.** `docs/features/run-next-plan.md`: add `sdlc_deferred_issues` to the key table (L33) and
   to the "Final-round deferral" paragraph (L146). `docs/agents/triage-labels.md` L14-18: the
   `sdlc-finding` paragraph names `sdlc_deferred_issues` and keeps the point that those issues stay
   out of `Closes`.

**Part 2 — #76: finished iterations don't poison the next one**

10. **Shared helper.** Add `_iteration_finished(data, integration_branch) -> str | None` in
    `scripts/run-next-plan.py`. It returns a reason string when the iteration is over, `None` when it
    isn't, and on any lookup failure calls `warn()` and returns `None`, so offline runs aren't blocked.
    - PR: use `data["pr_number"]` if set (already int-validated), else `resolve_pr_number` (L585; it
      finds only *open* PRs, and its `json.loads` at L598 is unguarded, so wrap it).
      Run `gh pr view <N> --json state,headRefName`; finished only if `state == "MERGED"` **and**
      `headRefName == integration_branch`.
    - Branch: `["git", "ls-remote", "--exit-code", "--heads", "origin", "refs/heads/" + branch]`
      (argv list, never a shell string). rc 0 = exists, rc 2 = gone (finished), any other rc = warn
      and continue. Match the ref exactly.
    - Catch `json.JSONDecodeError`, `KeyError`, `OSError` and `subprocess.CalledProcessError`.
11. **Runner guard.** In `main()` (L1840), insert the guard **between** `integration_branch` being
    resolved (L1907) and `_register_exit_flush` (L1909). Otherwise the atexit push recreates a deleted
    branch. The `--dry-run` exits come after L1909, so the guard covers dry runs too. On a finished
    iteration, `die()` with a self-contained message:
    `prd.json at <path> belongs to a finished iteration (<reason>); run /plan-iteration to start a new one`.
12. **Tests** (`scripts/tests/test_orchestration.py`, using the `main()` harness at L679-727 and the
    `monkeypatch.setattr(run_next_plan.subprocess, "run", fake)` pattern with the passthrough at
    L568-589):
    - dies when the PR is `MERGED` with a matching `headRefName`;
    - dies when `ls-remote` returns rc 2;
    - does not die when the merged PR's `headRefName` differs;
    - warns and continues when `gh` is missing (`OSError`), returns bad JSON, or `ls-remote` returns
      rc 128;
    - runs normally when the PR is open;
    - the guard runs before `_register_exit_flush` and under `--dry-run`.
    The existing `main()` tests (test_orchestration.py L701/L724, test_config_root.py L269/L328) must
    stub the new calls so they don't hit the real network.
13. **close-iteration Step 4** (`skills/close-iteration/skill.md` L135-166):
    - Use `git rm -r --ignore-unmatch <config-root>/plans/` (L146). Commit and push only when
      something was staged. A match-nothing `git rm` is not an error.
    - If anything remains under `<config-root>/plans/` (untracked), archive it. Move everything except
      `archive/` itself, including `implementation-logs/`, into
      `<config-root>/plans/archive/<slug>/`.
      - `<slug>` is `integration_branch` with `/` replaced by `-`, restricted to `[A-Za-z0-9._-]`,
        with no leading `.` or `-`. Fall back to `iteration-<YYYY-MM-DD>`.
      - If the destination exists, append `-2`, `-3`, and so on.
      - Quote paths and use `--`. The resolved destination must sit inside the repo.
    - Before moving, if `git check-ignore -q <config-root>/plans/archive/` fails, append
      `<config-root>/plans/archive/` to the file named by `git rev-parse --git-path info/exclude`. Use
      the exclude file, not `.gitignore`. Exclude only `archive/`, never `plans/`.
    - Never delete untracked plans outright.
14. **close-iteration Step 10** (L305): the report says exactly one of
    `removed: yes (history on <branch>)` or `archived to <path>`. It never says "removed: no".
15. **plan-iteration Step 1.2** (`skills/plan-iteration/SKILL.md` L35-39). When `prd.json` exists,
    check whether its iteration is over, using the same rule as the runner's `_iteration_finished`:
    - Over means the integration PR (`pr_number`, or a lookup by `integration_branch`) is `MERGED`
      with a matching head, or `integration_branch` is gone on origin.
    - Do **not** treat "all plans terminal + `sdlc_review_status: complete`" as finished. Adding plans
      to an open iteration after review is supported; that is what `_rearm_sdlc_review_gate` is for.
    - If `gh` or `git` can't answer, warn and fall back to the merge.
    - Print which case applied: `fresh prd.json (previous iteration finished: <reason>)` or
      `merging into existing prd.json (iteration still open)`.
    - Step 1 must contain no instruction to ignore or exclude `<config-root>/plans/`.
16. **plan-iteration Step 7.5** (L138-142):
    - **Fresh case.** Move the old file to `prd.json.<YYYY-MM-DD>.bak`. Ensure
      `<config-root>/plans/prd.json.*.bak` is in `info/exclude`, the same way as the archive. Then
      write a new object with no `sdlc_*` keys, no `last_reviewed_sha`, no `pr_number` and no old
      plans. Strip at least `sdlc_review_status`, `sdlc_review_rounds`, `sdlc_finding_issues`,
      `sdlc_deferred_issues`, `sdlc_round_filed_issues` and `sdlc_review_completed_agents`.
    - **Merge case.** Unchanged. Add `sdlc_review_rounds`, `sdlc_round_filed_issues` and
      `sdlc_deferred_issues` to the preserve list.
    - Note that this write is not under `_with_prd_lock`, so it assumes no runner is active.
17. **Tracked-vs-ignored docs.** Use one shared sentence in all three places below:
    - **Tracked:** plan `.md` files, `prd.json` and `progress.md` are committed on the integration
      branch while an iteration runs. `/close-iteration` removes them with a commit before merge. They
      are still never swept into a docs-publishing pipeline.
    - **Gitignored, never committed or published:** `implementation-logs/`, `prd.json.lock`,
      `sdlc-review-findings.md`, `pr-summary.md`. This matches `.gitignore` and
      `_artifact_ignore_paths` (L842).
    - **Kept out of git locally (info/exclude):** the `plans/archive/` fallback and `prd.json.*.bak`.

    Where it goes:
    - `docs/agents/README.md`: the "Not publishable, ever" section (L6, L8, and the L13 `plans/` row).
    - `CONTEXT-MAP.md`: L7-12.
    - `global/CLAUDE.md`: **only** the L72 sentence beginning "Anything under `plans/`". Commit it on
      its own, as a 1–2 line diff. The file stays under 100 lines.
18. **Run-next-plan doc.** Document in `docs/features/run-next-plan.md` the archive fallback, the
    finished-iteration check in plan-iteration, and the runner guard. Also cover
    `/close-iteration` integration (L197) and the tests paragraph (L229).
19. **Verify.** Run `cd scripts && python3 -m pytest`, then `python3 -m ruff check .`.

**Out of scope** (per the #76 brief):
- changing whether plans are tracked;
- adding `plans/` to `_artifact_ignore_paths`;
- `MAX_REVIEW_ROUNDS` or the re-arm logic;
- `docs/agents/PRIVACY.md`;
- any `global/CLAUDE.md` edit beyond L72;
- #77.

---

## Acceptance Criteria

- [ ] After a final-round filing, `sdlc_deferred_issues` contains that round's issues and `sdlc_finding_issues` does not (existing #47/#44 tests still pass)
- [ ] `MINOR_ROLLUP: N` is parsed and stored in `sdlc_deferred_issues` for every round; a missing rollup line is fine
- [ ] Re-arm keeps `sdlc_deferred_issues`; the cap message lists it instead of `sdlc_finding_issues`; schema validation rejects a non-int-list value
- [ ] `/close-iteration` does not file an issue duplicating an open `sdlc-finding` issue or a deferred one
- [ ] The closing report's "Issues left open" lists open deferred issues; the `Closes` block does not
- [ ] `/plan-iteration` SKILL.md contains no instruction to ignore or exclude `<config-root>/plans/`
- [ ] `/close-iteration` with untracked plans leaves no `<config-root>/plans/prd.json`; files sit under `plans/archive/<branch-slug>/`, `git status` doesn't show the archive, the report says "archived to <path>"
- [ ] `/close-iteration` with tracked plans behaves as today: a removal commit and "removed: yes"
- [ ] `/plan-iteration` with a `MERGED` (or branch-gone) `prd.json` writes a fresh one with none of `sdlc_review_status`, `sdlc_review_rounds`, `last_reviewed_sha`, `sdlc_finding_issues`, `pr_number` or old plans, and leaves a `.bak`
- [ ] `/plan-iteration` with an open PR preserves all top-level keys, even when every plan is `done` and review is `complete`
- [ ] pytest: the runner dies with the finished-iteration message for a `MERGED` PR and for an absent branch; warns and continues when `gh`/`git ls-remote` fails; runs normally when the PR is open
- [ ] `docs/features/run-next-plan.md` documents all of the above; `docs/agents/triage-labels.md` names `sdlc_deferred_issues`
- [ ] `global/CLAUDE.md`, `CONTEXT-MAP.md` and `docs/agents/README.md` state the tracked/gitignored split; `global/CLAUDE.md` diff is 1–2 lines and stays under 100 lines
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** findings (no Critical/High)
  - Medium: the anchored, separate `MINOR_ROLLUP` regex. One number per round (the last match), 0 rejected, never fed to `parse_issue_numbers` or `Closes`, deduped, schema list of non-bool ints. Steps 1-3, 7.
  - Medium: branch→archive slug. Whitelist, no leading `.`/`-`, a date fallback, destination inside the repo, quoted paths with `--`, and a destination-exists guard. Step 13.
  - Low: use the `ls-remote --exit-code` argv form with an exact ref. rc 2 = gone, other = warn. Step 10.
  - Low: the guard catches JSONDecodeError/KeyError/OSError. `gh pr view --json state,headRefName`, matching the head. Step 10.
  - Info: the cap message reads `sdlc_deferred_issues`. The archive and `.bak` must never be staged by `git add -A` (they are excluded). Steps 5, 13, 16.
- **sdlc-privacy-reviewer:** findings
  - High: archiving `implementation-logs/` (raw transcripts) into an unpruned archive conflicts with PRIVACY.md's 30-day log retention. **Dismissed by maintainer (2026-10-26):** the archive is a local, gitignored file store, not production or a shared service, so the retention policy doesn't apply. Archive everything as the #76 brief says; no PRIVACY.md change.
  - Medium: `.bak` files are disposable and kept out of git via path-specific `info/exclude` entries. Step 16.
  - Medium: verify with `git check-ignore` before moving. Step 13.
  - Medium: docs keep the four runtime artifacts "never publishable". Step 17.
- **sdlc-accessibility-reviewer:** findings (CLI output only)
  - Minor: the `die()` message is plain and self-contained, naming the prd.json path and the fix command. Step 11.
  - Minor: deferred issues are listed one `#N` per line. No colour-only output; gate any colour on isatty/`NO_COLOR`. Steps 5, 8.
- **sdlc-design-reviewer:** findings (no UI; repo conventions)
  - Use one `_iteration_finished` helper and have `/plan-iteration` describe the same rule. Steps 10, 15.
  - Use `git rev-parse --git-path info/exclude` consistently. Keep `_artifact_ignore_paths` as the single list of runtime artifacts. Steps 13, 16, 17.
  - The fresh `prd.json` write is not under `_with_prd_lock`, and the step says so. Step 16.
  - Use exact report phrasings and one shared tracked-vs-ignored sentence across the docs. Steps 14, 17.
  - Info, out of scope: `skills/close-iteration/skill.md` is lowercase, while other skills use `SKILL.md`.
