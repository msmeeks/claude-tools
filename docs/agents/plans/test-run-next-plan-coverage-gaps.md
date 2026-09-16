# Plan: run-next-plan.py test coverage gaps

**Issues:** #59, #61, #63

---

## Goal

Close three test-coverage gaps the SDLC review gate found in `scripts/run-next-plan.py`'s test suite: an untested intermediate-symlink path-traversal branch in config-root resolution, an untested `.gitignore`-append branch, and a missing assertion that the issue-filing prompt still carries its privacy-redaction instruction.

---

## Context

All three findings share a shape: existing production logic is very likely already correct, but a real branch or invariant has no test standing guard over it, so a future refactor could silently regress it without the suite noticing. None require behavior changes unless a new test actually catches a latent bug — in which case the fix is to make the code match what the existing tests already assume. Grouped together as same-theme, same-area (`scripts/tests/`) test-only additions.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/tests/test_config_root.py` (or wherever config-root resolution is tested) | Add a test for an intermediate symlinked ancestor of the config root escaping the repo |
| `scripts/tests/` (gitignore-append test file) | Add a test for appending to a `.gitignore` whose last line lacks a trailing newline |
| `scripts/tests/` (issue-filing / SDLC gate test file) | Add an assertion that the issue-filing prompt contains the redaction instruction |

### Steps

1. **#59 — intermediate symlink escape.** In the config-root resolution tests, add a test that: creates a real directory tree *outside* the repo containing a config-root-shaped subdirectory; creates an intermediate directory *inside* the repo (a parent of, but not equal to, the leaf config root) as a symlink pointing into that external tree; and asserts that config-root resolution refuses the result, the same way it refuses a directly-symlinked leaf. If the assertion fails against current code, fix the resolution function so the "outside the repo" guard actually catches this case, then confirm the leaf-symlink and normal-case tests still pass.
2. **#61 — `.gitignore` no-trailing-newline branch.** In the gitignore-append tests, add a test that writes a `.gitignore` file whose content does not end in `\n`, runs the artifact-ignore-ensuring logic, and asserts the newly appended rules land on their own line(s) — not concatenated onto the existing last line. Confirm the two existing branch tests (no file, file ending in newline) still pass.
3. **#63 — issue-filing redaction instruction.** Find (or add) the test file covering the issue-filing phase's prompt construction. Add a test that builds/captures the prompt sent during issue filing and asserts it contains the `[REDACTED]` marker and language naming the sensitive-data categories (credentials, tokens, keys, connection strings, personal data) the instruction currently covers.
4. Run `cd scripts && python3 -m pytest` and `python3 -m ruff check .`.

---

## Acceptance Criteria

- [ ] A test proves config-root resolution rejects an intermediate-symlink escape, not just a leaf-symlink escape
- [ ] A test proves `.gitignore` append correctly separates new rules when the existing file has no trailing newline
- [ ] A test proves the issue-filing prompt contains the redaction/rewrite instruction
- [ ] All three new tests pass against current (or newly fixed) production code
- [ ] `cd scripts && python3 -m pytest` passes in full
- [ ] `python3 -m ruff check .` passes
