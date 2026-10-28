# Plan: Runner hardening and cleanup from SDLC minor findings

**Issues:** #90, #93
**Prerequisite:** complete `fix-iteration-guard.md` first (#90/#93 items touching the closed-PR rule follow #92).

---

## Goal

`run-next-plan.py` can't be crashed by a malformed `gh` reply or an oversized issue number,
rejects auto-closing commit-ref templates, and its tests and docs stop drifting.

---

## Context

#90 and #93 collect lower-severity findings from earlier SDLC rounds on
`scripts/run-next-plan.py` and its tests. The maintainer marked every item small and
decision-free: where an item offers options, pick the smaller change and say which in the
commit. This plan takes the runner-code and test items. Gate-area items are in
`fix-review-gate.md`, guard items in `fix-iteration-guard.md`, close-iteration items in
`feat-close-iteration-cleanup.md`, and prose-only items in `docs-agent-config-polish.md`.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Items 1, 3-12 below |
| `scripts/tests/test_config_root.py` | Tighten two assertions; move the `main()` plan-refs wiring tests out |
| `scripts/tests/test_orchestration.py` | Receive the moved tests; new `_pr_refs_line`, docs-prompt and `exit_flush` tests |
| `scripts/tests/test_pr_description.py` | `resolve_pr_number` malformed-reply tests |
| `scripts/tests/test_sdlc_gate.py` | Rollup/issue-number digit-bound tests |
| `docs/features/run-next-plan.md` | Tests paragraph (L237) rewritten to file-level responsibilities; message-prefix convention |

Line numbers below are from `main` @ 2308890; the two prerequisite plans shift them.

### Steps

**Runner code (`scripts/run-next-plan.py`)**

1. **#90.1 Unguarded `gh` JSON.** `resolve_pr_number` (L612-645): `json.loads(r.stdout)` and
   `prs[0]["number"]` are unguarded. Catch `(ValueError, KeyError, IndexError, TypeError,
   AttributeError, OSError)` in that one `except` — `ValueError` covers `JSONDecodeError`;
   `AttributeError` is what a list of non-dicts (`["x"]`, `[null]`) raises on `pr.get(...)` in
   the `include_finished` branch; `OSError` is a missing `gh`, and belongs here rather than in
   `_pr_refs_line` because `sync_pr_closes` and `update_pr_description` call this too —
   `warn(f"resolve_pr_number: unusable gh reply ({type(e).__name__}) — treating as no PR")`
   (type only, never stdout, so the iteration-state guard doesn't fail open silently) and
   return `None`. Callers then also warn "no open PR found … — skipping"; two warnings is
   acceptable — note it in the commit. **Validate the number** on both return paths (the
   early prd.json `pr_number` return, L623-624, and the `gh` one) and return `None`
   otherwise: it is passed as `str(pr_number)` to `gh pr view`/`gh pr edit`, so a string like
   `--body` would be read as a flag. Extract `_is_issue_number(x)` (`type(x) is int and
   0 < x < 10**9`) and use it here, in `_coerce_refs`, and in step 7's helpers.
   `_pr_refs_line` (L949-953) then returns `""` naturally with no catch of its own. Check the iteration-state
   guard's own catch list covers `TypeError`/`AttributeError` for a non-list reply too.
   Tests: malformed JSON, `{}`, `["x"]`, `[null]`, and `number` as `"--body"`, `true`, `-1`,
   `10**9` → `None`.
2. **#90.2 Guard under `--dry-run`.** The feature doc already says the guard deliberately
   covers `--dry-run` (a dry run should still report a finished iteration) and a test pins
   it. Smaller change: keep the behaviour; tick the item with that rationale in the commit.
3. **#90.3 Auto-close keywords.** `_commit_ref_template_problem` (L876-887): reject a template
   containing a GitHub closing keyword, case-insensitive, bounded by **letters** rather than
   `\b` (which misses `Fixes_#{n}`, `Fix#{n}`, `Closes#{n}`):
   `(?<![A-Za-z])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)(?![A-Za-z])` with `re.IGNORECASE`,
   on the stripped candidate. Run it **last**, after the `disallowed characters` check, so
   existing precedence is unchanged. Problem text follows the bare-category shape of the
   existing ones (`no {n}`, `multiple {n}`, `too long`, `disallowed characters`):
   `closing keyword '<kw>'` with the keyword lowercased, never echoing the template line. Add
   the category to the list in `docs/features/run-next-plan.md` (~L93) in the same commit. Tests: `Closes #{n}`, `fixes #{n}`, `RESOLVED: #{n}`,
   `Fixes_#{n}`, `Fix#{n}`, `Re-closes #{n}` rejected; `Refs #{n}`, `Tracks: GH-{n}`,
   `Prefix-{n}` accepted.
4. **#90.4 Digit bounds.** `ISSUE_NUMBER_RE` (L579) and `MINOR_ROLLUP_RE` (L580) use `\d+`
   (matches non-ASCII digits; >4300 digits makes `int()` raise at ~L1746 and in
   `parse_minor_rollup`). Use `[0-9]{1,9}` (the `$` anchor already rejects 10+ digits, so no
   separate `10**9` check is needed) and drop `0` as `_coerce_refs` does. Replace `\s*` with
   `[ \t]*` in both so a match can't span newlines. Decide CRLF handling explicitly (`$` with
   `MULTILINE` doesn't match before `\r`; allow an optional `\r?` or strip lines) and test it.
   Tests: 5000-digit number, Arabic-Indic digits (`#١٢`), `0`, and `MINOR_ROLLUP:\n\n5` are
   not parsed; a 9-digit number is; one test goes through `_run_file_issues_phase`, not only
   the parsers. Share one fragment constant (e.g. `_ISSUE_NUM = r"([0-9]{1,9})"`) between the
   two regexes and one post-match filter (int + drop 0) between `_run_file_issues_phase` and
   `parse_minor_rollup` so they can't drift.
5. **#90.5 Constant names.** Rename `_MAX_REFS` → `_COMMIT_REF_MAX_COUNT` and move it with
   `DEFAULT_COMMIT_REF_TEMPLATE` (L530) into the `_COMMIT_REF_*` block (L869-873). Keep
   `DEFAULT_COMMIT_REF_TEMPLATE`'s public name if tests import it.
6. **#90.6** `_run_file_issues_phase` (L1759): drop the redundant `[*issue_ints]` copy.
7. **#90.7** `_validate_prd_schema` (L206-225): extract `_is_int_list(value)` (and
   `_is_str_list` for the two str-list checks) and use them. Error messages unchanged.
8. **#90.8** `_load_commit_ref_template` (L907-912): replace `for … else` with a `next(...)`
   expression.
9. **#90.9 Shared refs instruction.** "End the commit message with this last line: {refs}"
   appears in `ensure_committed` (L1200) and `run_docs_phase` (L1360). Extract one helper,
   e.g. `_refs_instruction(refs) -> str` returning the **bare sentence** (or `""` when refs is
   empty). The call sites differ today — `ensure_committed` prepends a space, `run_docs_phase`
   prepends `"\n   "` — so each caller keeps its own separator; otherwise one prompt changes.
   Pin both prompts' exact text in step 13's tests. It takes the already-formatted refs line
   and never formats the template itself. `_build_claude_prompt` (L558-561) words a different
   instruction (fill the template per issue) — leave it.
10. **#90.10 Long lines.** Wrap the `ensure_committed(..., refs=commit_refs)` calls at L1834,
    L1871, L1888, L1914 and the prompt line at L1204 to ≤100 chars. Don't add a ruff
    line-length rule (out of scope).
11. **#90.11 `exit_flush` docstring** (L1247-1257): say it is registered by `main` after the
    iteration-state guard and not under `--dry-run`, and that the wip message carries no
    ref — one line, pointing at the feature doc for the "exit paths must not raise"
    rationale rather than restating it. (The feature doc already documents the no-ref wip
    commit at L93 — that #90 item needs no change; say so.)
12. **#90.12 Messages.** The invalid-template warning (L917-920) should name the section:
    `"{path.name}: '## Commit references' template invalid ({problem}); using 'Refs #{n}'"`
    — keep `path.name` as today, not a hardcoded file name. Prefix convention (smaller
    change: document current practice, don't rewrite every message): `die`/`warn`/`info`
    add `ERROR: `/`WARN: `/`==> ` (the `==>` belongs to `info`); a message about a file
    starts with its path, one about a function with `<function>: `, and phase-level messages
    are plain sentences ("Uncommitted changes detected after…"). Word it as "current
    practice, not exhaustive" — some messages (the hand-printed `WARN: Plan marked stalled`
    at L384, `die("Failed to read prd.json …")`) fit none. Bring the topic-label outliers
    (`finished-iteration check`, `issue references`) in line only if trivial, and grep the
    tests for those strings first. Record the convention in `docs/features/run-next-plan.md`.

**Tests**

13. **#90.13** add: `_pr_refs_line` with no `pr_number` and an empty-stdout `gh` lookup
    returns `""`; the docs-phase prompt contains no "End the commit message" line when refs
    are empty (and contains it when present — extend
    `test_docs_phase_asks_for_and_commits_with_pr_ref`, test_orchestration.py L1149);
    `exit_flush`'s `git commit -m` arg equals exactly `"wip: uncommitted changes at runner
    exit"` (tighten L518). The duplicate-rollup-test item is handled in `fix-review-gate.md`.
14. **#93 c** `test_main_caps_refs_at_the_limit_and_warns_once` (test_config_root.py L583)
    asserts `>= 1`, but the warning fires twice per plan (`_coerce_refs` runs in both
    `ensure_committed` and `commit_attempt_bookkeeping`). Take the smaller change: rename the
    test to describe what it checks (behaviour unchanged; asserting the exact count would pin
    the double warning, which is arguably a bug). Say so in the commit.
15. **#93 h** `test_coerce_refs_over_cap_warns_that_overflow_was_dropped` (L476): assert the
    exact text `"1 over the cap of 20"` like its sibling (L484).
16. **#93 e** move the `main()` plan-refs wiring tests (test_config_root.py L512-635:
    `_run_main_recording_plan_commits` and the four tests using it) to
    `test_orchestration.py`, unchanged in behaviour. Helpers or fixtures they share with
    `test_config_root.py` go to `conftest.py` (or are imported), not duplicated.
17. **#93 Tests paragraph**: rewrite `docs/features/run-next-plan.md` L237 as one short line
    per test file stating its responsibility, without enumerating test names. It must
    reflect step 16: `test_orchestration.py` now owns the `main()` plan-refs wiring
    (plan `issues` → `ensure_committed(refs=)`), not `test_config_root.py`.

18. Commits: `Refs #90, #93`. In the final commit body, list which items were done, which
    took the "document" option, and which needed no change.

---

## Acceptance Criteria

- [ ] A malformed or empty `gh pr list` reply makes `resolve_pr_number` return `None` and `_pr_refs_line` return `""` — no traceback.
- [ ] A commit-ref template with a closing keyword is rejected with a warning and the default is used.
- [ ] Issue/rollup numbers with non-ASCII digits or more than 9 digits are ignored, not crashed on.
- [ ] Every #90 runner/test item and #93 items c, e, h and the Tests paragraph are done or explicitly ticked with a reason.
- [ ] No behaviour change beyond the above; the existing suite passes.
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass.

---

## Pre-Implementation Review
All findings below are folded into the steps above.

- **sdlc-security-reviewer:** findings
  - medium (Step 3): `\b` misses `Fixes_#{n}`, `Fix#{n}` and `Closes#{n}`; use letter lookarounds with `IGNORECASE`.
  - medium (Step 1): catch `AttributeError` (a list of non-dicts) and `ValueError`.
  - medium (Step 1): validate the PR number from `gh`/prd.json so a string like `--body` can't reach `gh` argv.
  - low (Step 1): warn with the exception type on an unusable reply.
  - low (Step 4): use `[ \t]*`, drop 0, and test CRLF and the `_run_file_issues_phase` path.
  - info (Steps 9/12): the refs helper never formats the template, and the warning never echoes it.
- **sdlc-privacy-reviewer:** no findings (log the exception type only, never `gh` stdout)
- **sdlc-accessibility-reviewer:** no findings (plain-text prefixed output)
- **sdlc-design-reviewer:** findings (no design brief; reviewed against conventions)
  - major (Step 9): the helper returns the bare sentence and callers keep their own separators; pin both prompts.
  - major (Step 1): `OSError` belongs inside `resolve_pr_number`; validate both return paths; share `_is_issue_number`.
  - major (Step 3): use the problem text `closing keyword '<kw>'`, document it in the same commit, and run the check last.
  - major (Step 12): the prefix convention is "current practice, not exhaustive"; grep the tests before renaming outliers.
  - minor: the warning suffix; keep `path.name`; a shared regex fragment and filter; rename the test (Step 14); shared helpers go to `conftest.py`; the docstring and the Tests paragraph.
