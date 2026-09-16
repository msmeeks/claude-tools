# Plan: run-next-plan.py style cleanup

**Issues:** #58, #64

---

## Goal

Two small, mechanical style inconsistencies flagged by the SDLC review gate are cleaned up: an abbreviated variable name in `prd.json` schema validation, and function-scoped imports in one test file that don't match its siblings.

---

## Context

Both findings are cosmetic — neither changes behavior — but both are real inconsistencies against the surrounding code's own established style within the same branch. #58 is a single abbreviated local variable (`srr`) in the `sdlc_review_rounds` validation block of `scripts/run-next-plan.py`, where every other field's validation block spells its variable out. #64 is `scripts/tests/test_config_root.py` importing `subprocess` and `json` inside individual functions instead of once at module scope, unlike every other file in `scripts/tests/`. Bundled together as trivial, same-file-area cleanup per the grouping heuristic for trivial fixes.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Rename the abbreviated `srr` local in the `sdlc_review_rounds` validation block to a descriptive name (`rounds` or `review_rounds`) |
| `scripts/tests/test_config_root.py` | Move all function-scoped `import subprocess` / `import subprocess as sp` / `import json` statements to module-scope imports alongside the existing top-level imports |

### Steps

1. In `scripts/run-next-plan.py`, find the `prd.json` schema validation function's `sdlc_review_rounds` block (the one that dies on a non-negative-int violation) and rename its abbreviated local variable to a full, descriptive name. Update any f-string or reference inside that block that uses the old name.
2. In `scripts/tests/test_config_root.py`, add `import subprocess` and `import json` to the top-level import block (alongside `importlib.util`, `sys`, `pathlib.Path`, `pytest`), then remove every function-scoped `import subprocess`, `import subprocess as sp`, and `import json` statement found inside individual test/helper functions. If any function used the `sp` alias, either keep using `subprocess` directly or alias it once at module scope — match whichever reads more consistently with the rest of the file.
3. Run `cd scripts && python3 -m pytest` and `python3 -m ruff check .` to confirm nothing broke.

---

## Acceptance Criteria

- [ ] No abbreviated/cryptic local variable remains in the `sdlc_review_rounds` validation block
- [ ] `test_config_root.py` imports `subprocess` and `json` exactly once each, at module scope
- [ ] No function-scoped imports of either module remain in `test_config_root.py`
- [ ] `cd scripts && python3 -m pytest` passes
- [ ] `python3 -m ruff check .` passes
