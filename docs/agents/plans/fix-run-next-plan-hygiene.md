# Plan: run-next-plan hygiene (stray backup, validator tests)

**Issues:** #105, #108

---

## Goal

No stray backup copy of `run-next-plan.py` is tracked, and every `prd.json` list field's validation is tested.

---

## Context

`scripts/run-next-plan.py.bak` is a tracked byte-identical duplicate that can drift and ships via the `~/.claude/scripts` symlink. Separately, `_validate_prd_schema` die paths are tested for only two fields, so a regression in `blocked_by`, `sdlc_finding_issues` or `feature_branches` validation would go unnoticed.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py.bak` | `git rm` |
| `.gitignore` | Add `*.bak` (confirm no other tracked file matches) |
| `scripts/tests/test_prd_data_layer.py` (or the file already holding the validator tests) | Parametrized `(field, bad_value)` test |

### Steps

1. `git rm scripts/run-next-plan.py.bak`; add `*.bak` to `.gitignore`.
2. Write a parametrized test: `blocked_by` with `[1]`, `"x"`, `None`; int-list fields (e.g. `sdlc_finding_issues`) with `[True]`, `["1"]`, `1`; `feature_branches` with `[1]`. Assert `SystemExit` and the field name in the message; `[]` passes for each.
3. Fix validator behaviour if a case is wrongly accepted.

---

## Acceptance Criteria

- [ ] `git ls-files | grep '\.bak$'` prints nothing; `git check-ignore scripts/x.bak` succeeds
- [ ] Every listed field and bad value is rejected with the field name; `[]` accepted
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass

---

## Pre-Implementation Review

- **sdlc-security-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
- **sdlc-privacy-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
- **sdlc-accessibility-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
- **sdlc-design-reviewer:** ERROR: not dispatched (non-interactive triage fold-in pass); the iteration review gate covers it
