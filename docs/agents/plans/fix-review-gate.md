# Plan: Review gate skips net-empty ranges and survives a failed PR edit

**Issues:** #99, #93, #90

---

## Goal

A review round whose range has commits but no net diff completes without dispatching a
reviewer, and a failed `gh pr edit` at the end of the gate warns instead of crashing the run.

---

## Context

`run_sdlc_review_gate` skips a round only when `last_reviewed_sha == HEAD`. A commit plus its
revert, or a no-diff merge, still dispatches reviewers; under the skill recipe a reviewer
answers `SKIPPED … empty range` with no `<reviewed>` sigil and the runner `die()`s. Decided
in Hospitality-Delivered/hd-tech-standards#77: the runner detects the empty diff itself.
Separately, `update_pr_description`'s final `gh pr edit` runs with `check=True`, so a `gh`
failure raises a traceback after the docs commit (#93 item f). Two small test-hygiene items in
`test_sdlc_gate.py` ride along because this plan already edits that file.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | `git diff --quiet <range>` check in `run_sdlc_review_gate` (L1780-1916); catch `gh pr edit` failure in `update_pr_description` (L1472) |
| `scripts/tests/test_sdlc_gate.py` | Net-empty / non-empty / git-failure tests; `_run_gate_recording_commits` cleanup; drop the duplicate rollup test |
| `scripts/tests/test_pr_description.py` | Test for a failing final `gh pr edit` |
| `docs/features/run-next-plan.md` | Empty-increment rule widened to "no net diff"; failed-edit behaviour |
| `scripts/CONTEXT.md` | Only if a glossary entry describes the empty increment (none found today — check) |

### Steps

1. **Empty-diff helper.** Add `_range_is_empty(repo_root, review_range) -> bool` near
   `_compute_review_range` (L1321-1328): `subprocess.run(["git", "diff", "--quiet",
   review_range, "--"], cwd=repo_root)` — list argv, no shell, and the `--` terminator so a
   malformed `last_reviewed_sha` can't be read as an option. rc 0 → `True`; rc 1 → `False`; any other rc or `OSError`
   → `warn()` naming only the rc or `type(e).__name__` (no captured stderr) plus the
   fallback, e.g. `_range_is_empty: git diff rc=128 — reviewing anyway`, and `False` (a
   failed check never skips review). The range is used as-is,
   including the `<default>...HEAD` three-dot form.
2. **Gate.** In `run_sdlc_review_gate`, compute `review_range = _compute_review_range(...)`
   once, before the current empty-increment block (L1804-1820), and run the helper. If empty,
   or the existing `baseline == head_sha` shortcut holds, take the empty-increment path under
   the prd lock: `sdlc_review_status = "complete"`, clear `sdlc_review_completed_agents` and
   `sdlc_round_filed_issues`, set `last_reviewed_sha` to HEAD, leave `sdlc_review_rounds`
   unchanged, `info()` one line, return `"complete"`. Reword the existing L1812 line ("no
   new commits since the last review") to cover both paths, keeping the `SDLC review gate:`
   prefix and em dash: `SDLC review gate: no net changes since the last review — nothing to
   review.`, or `… no net changes in the review range — …` when there is no baseline yet. Dispatch no
   reviewer, file nothing, run no triage or docs phase. The check must run **before** the
   findings-file rotation (L1826-1827) so a no-op round doesn't touch the findings file, and
   before both recipes branch, so it covers skill and agents. Pass the same `review_range` on
   to the reviewers — don't recompute it. Move the `commit_refs = _pr_refs_line(...)` call
   (L1808) after the check if nothing on the empty path needs it.
3. **Baseline == HEAD shortcut.** It previously kept the baseline; it now sets it to HEAD,
   which is the same value. Existing tests
   `test_gate_empty_increment_marks_complete_without_reviewing` (L350) and
   `test_gate_does_not_count_an_empty_increment_as_a_round` (L772) must pass unchanged.
4. **Fake.** `_fake_subprocess_run` (test_sdlc_gate.py L221) rejects unknown commands. Teach
   it `git diff --quiet` with a configurable rc (default 1, "has changes") so every existing
   gate test still reviews.
5. **Tests** (`test_sdlc_gate.py`), using a real temp git repo where practical (commit +
   revert; see `_init_repo` in `test_orchestration.py` L59):
   - Net-empty range with commits since the baseline → `"complete"`, no `claude` call,
     `last_reviewed_sha == HEAD`, `sdlc_review_rounds` unchanged, findings file untouched,
     no `SDLC review` commit.
   - First-ever review (no baseline), `<default>...HEAD` net-empty → same no-op, baseline set.
   - Non-empty range → reviewed as before.
   - `git diff` rc 128 and `OSError` → normal review runs.
   - Both recipes (agents and skill) take the no-op path.
6. **`update_pr_description`** (L1472): follow `sync_pr_closes` (L806-815) — drop
   `check=True`, run with `capture_output=True, text=True`, check `returncode`, and on failure
   `warn()` in the `sync_pr_closes` shape with a consequence, as L1459/L1469 do:
   `update_pr_description: gh pr edit #{n} failed — PR summary not updated: <detail>`, where
   `<detail>` is the first line of `_scrub_credentials(r.stderr.strip())` (a deliberate
   deviation from `sync_pr_closes`, which prints all of stderr) or, on `OSError`,
   `type(e).__name__` only. A shared helper with `sync_pr_closes` is optional; two call sites
   are acceptable. **Never interpolate the exception or its `cmd`**: the argv carries
   `--body <new_body>`, which would dump the whole PR body into terminal and logs. Keep
   `_scrub_credentials` on `new_body` before the call (L1471). Leave the body unchanged and
   return normally so the gate still reaches `flush_push`. Tests in `test_pr_description.py`:
   the edit fails (rc 1 and `OSError`) → warning, no exception, body not re-attempted, and the
   body text is absent from the warning.
7. **#93 item d**: `_run_gate_recording_commits` (L1404) returns `(dict(commits), commits,
   prompts)`; return only the dict and the prompts and update the two callers (L1438, L1449).
8. **#90 item 13 (last bullet)**: `test_rollup_number_never_reaches_issue_parsing` (L1345)
   duplicates `test_minor_rollup_is_neither_triaged_nor_claimed_by_the_pr` (L1123). Delete the
   unit test if the end-to-end one asserts the same thing; otherwise keep it and say why in
   the commit.
9. **Docs**: in `docs/features/run-next-plan.md`, describe the widened rule ("no net diff,
   not just no new commits") wherever the empty increment is described (L144 at least; grep
   `docs/features/` and `scripts/CONTEXT.md` for others), and the failed-edit
   warning. Add one sentence on the accepted tradeoff (hd-tech-standards#77): a net-empty
   range skips the intermediate commits, so something added and reverted inside it is never
   reviewed, though it stays in history. Update the Tests sentence about "the empty-increment no-op".

---

## Acceptance Criteria

- [ ] A round whose range has commits but no net diff returns `"complete"` without invoking `claude` and without `die()`; `last_reviewed_sha == HEAD`; `sdlc_review_rounds` unchanged.
- [ ] A first-ever review with a net-empty `<default>...HEAD` range takes the same path.
- [ ] A non-empty range is reviewed exactly as before; existing gate tests pass unchanged.
- [ ] A `git diff` failure runs the normal review.
- [ ] A failing final `gh pr edit` prints a warning and the run continues to push; no traceback.
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass.

---

## Pre-Implementation Review
All findings below are folded into the steps above.

- **sdlc-security-reviewer:** findings
  - medium (Step 6): the warning must not interpolate `CalledProcessError`, whose argv carries `--body`. Follow `sync_pr_closes`: check rc and warn with the PR number plus scrubbed stderr; for `OSError`, the type name only. A test asserts the body is absent.
  - low (Steps 1-2): add a `--` terminator to `git diff --quiet <range>`; list argv, no shell.
  - info: fail-open on rc≠0/1 and `OSError` is right. A net-empty range skips intermediate commits, an accepted tradeoff that gets one sentence in the docs.
  - info: empty-path state handling matches the existing shortcut; no new surface or dependencies.
- **sdlc-privacy-reviewer:** findings (informational only)
  - info (Step 6): the body stays out of warnings; optionally truncate stderr to its first line.
  - info (Step 1): the `_range_is_empty` warning names only rc or the exception type.
  - info (Steps 2/9): nothing new is stored.
- **sdlc-accessibility-reviewer:** no findings (plain prefixed text, no colour, no spinners or box tables)
- **sdlc-design-reviewer:** findings (no design brief; reviewed against CLI conventions)
  - minor (Step 2): reword the net-empty info line; use neutral wording when there is no baseline.
  - minor (Step 1): the `_range_is_empty` warning names both the failure and the fallback.
  - minor (Step 6): use `gh pr edit #N failed — PR summary not updated: <detail>`, with the same template for `OSError`.
  - minor (Steps 2/5): assert no `SDLC review` commit on the empty path.
  - minor (Step 9): update the docs and the Tests sentence.
