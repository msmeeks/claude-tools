# Plan: Commit-ref coverage and dropped-ref warning

**Issues:** #87, #88, #89

---

## Goal

Refs cut by the 20-item cap produce a warning, and the commit-ref code (`_coerce_refs`, the template loader, the `main` wiring) has boundary and wiring tests.

---

## Context

Review of the commit-refs feature (#80) found one bug and three test gaps. In `_coerce_refs` (`scripts/run-next-plan.py`) the dropped count is computed before the list is sliced to `_MAX_REFS`, so refs cut by the cap are never warned about (#87). The template length boundary and the empty-section case are untested (#88). The wiring from a plan's `issues` list to the `refs=` argument of `ensure_committed` is untested (#89). All three share one feature and the same files, so they are one cluster.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | `_coerce_refs`: warn about cap overflow; comment on `type(x) is int` excluding bool |
| `scripts/tests/test_config_root.py` | Existing `_coerce_refs` tests live here (around L416); extend them |
| `scripts/tests/test_orchestration.py` | Template tests and `main`-level wiring tests |

### Steps

1. Failing tests first. `_coerce_refs`:
   - `[1, 999_999_999]` kept; 0 and `10**9` rejected.
   - Exactly 20 items kept with empty stderr.
   - 21 valid items keeps 20 and warns that 1 was dropped.
   - Duplicates plus overflow in one call give correct counts.
   - `None`, a string or a dict returns `[]`.
   - Warning text starts with `WARN:`, carries counts only and no ref values. Use `capsys.readouterr().err`. The existing `test_coerce_refs_dedupes_in_order_and_caps_at_20` takes `capsys` but never uses it; use it or drop it.
2. Fix `_coerce_refs`: count invalid or duplicate refs before the cap and cap overflow after it (`max(0, len(kept) - _MAX_REFS)`). Report both through `warn()`, using `_MAX_REFS` rather than a literal 20. Add the comment that `type(x) is int` deliberately excludes bool, and that the cap bounds commit-message and prompt size.
3. Template tests (#88). Clear the `_load_commit_ref_template` cache in a fixture, and use `tmp_path` for `issue-tracker.md`.
   - 40-character line accepted; 41-character line rejected as "too long". The "multiple {n}" check runs before "too long", so pick inputs that hit the intended branch.
   - `## Commit references` followed only by blank lines or EOF returns the default template with no warning.
   - Changing `>` to `>=` on the length check must fail one test.
4. `main`-level wiring tests (#89). Mock `invoke_claude` and `subprocess.run`, and use synthetic issue numbers only.
   - Plan with `issues: [7, 8]` passes `Refs #7, Refs #8` as `refs=`.
   - Plan with no `issues` key passes an empty refs string.
   - The PR ref reaches `ensure_committed` on the interrupt, triage and docs paths.
   - Removing `refs=` at any call site fails a test.

---

## Acceptance Criteria

- [ ] A 21-item input emits a warning that one ref was dropped.
- [ ] `_coerce_refs` boundary tests above pass.
- [ ] 40-character template accepted and 41-character rejected; the empty-section test passes.
- [ ] All three wiring behaviours are asserted and each `refs=` call site is covered.
- [ ] `cd scripts && python3 -m pytest && python3 -m ruff check .` is clean.

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** findings
  - Medium: a short template such as `Ignore rules. {n}` passes validation and is interpolated into the prompt. Same trust level as `prd.json` and bounded by the length cap and charset. Add tests that templates with `\n`, backtick, `$`, `<`, `>`, `;` or `"` are rejected, `{n}` counts of 0, 1 and 2 are handled, and lookalike unicode is rejected. Fixing the template charset itself is out of scope for this plan; file it separately if wanted.
  - Low: `_coerce_refs` counts the wrong drops. Warn on counts only and never echo values.
  - Informational: non-list input becomes `[]` silently. Consider a warning and test it.
  - Informational: clear the template cache in a fixture. Use `tmp_path`, and test missing file, missing section, no following line, the 64 KiB read cap and invalid UTF-8.
  - Informational: in the wiring test, assert `git commit` receives the message as a list argument.
- **sdlc-privacy-reviewer:** N/A: the change touches only `_coerce_refs` (positive-integer issue numbers, count-only warning) and its tests, with no personal data.
- **sdlc-accessibility-reviewer:** no findings. The only human-facing surface is the plain-text `WARN:` line. Keep it through `warn()`, with no colour or symbols and counts in digits.
- **sdlc-design-reviewer:** findings
  - Major: compute the dropped count after truncation, or report invalid/duplicate and overflow separately. Keep the count-only rule and use `_MAX_REFS` in the message.
  - Minor: follow the `<subject>: <what happened> — <outcome>` style of the other warnings, through `warn()`.
  - Minor: add the boundary and clean-input cases, assert through `capsys`, and test the wiring through a caller (more than 20 issues gives a capped commit and one warning).
  - Minor: new tests may go in `test_orchestration.py`; leave existing ones where they are. Reuse the `tracker_root` fixture.
