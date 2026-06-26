# Plan: Ralph Loop — prd.json Data Layer

**Issues:** #2
**Branch:** `feat/ralph-prd-json-data-layer`
**Base:** `main`
**Status:** done
**Status:** done

---

## Worktree Setup

```bash
# Run from the repo root
git worktree add .claude/worktrees/claude-tools-ralph-data-layer -b feat/ralph-prd-json-data-layer
```

**Working directory:** `.claude/worktrees/claude-tools-ralph-data-layer`

When the PR merges:
```bash
git worktree remove .claude/worktrees/claude-tools-ralph-data-layer
```

---

## Context

`run-next-plan.py` currently tracks plan state in a Markdown README table and per-plan `.md` frontmatter. The Ralph loop rewrite needs a machine-readable `prd.json` as the single source of truth for plan status, attempt counts, and blocker relationships. This slice creates the foundational data layer — all read/write functions plus a full pytest suite — that every subsequent slice depends on.

---

## Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Add `load_prd`, `save_prd`, `increment_attempts`, `set_status`, `mark_stalled` functions |
| `scripts/tests/test_prd_data_layer.py` | New — pytest suite for all data layer functions |
| `scripts/pyproject.toml` | New — pytest + ruff config for the scripts directory |

---

## Implementation Steps

1. Create `scripts/pyproject.toml` with `[tool.pytest.ini_options]` (testpaths = `["tests"]`) and `[tool.ruff]` (same settings as global CLAUDE.md standard).

2. Implement `load_prd(path: Path) -> dict` — reads and parses `prd.json`. Validate on load: top-level must be a dict with `integration_branch` (str) and `plans` (list). Each plan entry must have `file` (non-empty str matching `r'[\w.-]+\.md'`), `status` (one of `pending|in-progress|done|stalled`), `attempts` (int ≥ 0), `blocked_by` (list of str). Raise `SystemExit` with a clear message on any validation failure — never propagate `TypeError` or `KeyError`.

3. Implement `save_prd(path: Path, data: dict) -> None` — atomic write using `tempfile.mkstemp(dir=path.parent, prefix=".prd-", suffix=".tmp")` followed by `os.replace`. Never use a fixed tmp filename.

4. Implement `increment_attempts(path: Path, plan_file: str) -> None` — load, find the matching entry by `file`, increment `attempts`, save. Idempotent: if called twice in sequence, count is correct. Apply path-containment guard: resolve `plans_dir / plan_file` and assert it starts with `plans_dir.resolve()`.

5. Implement `set_status(path: Path, plan_file: str, status: str) -> None` — validate `status` is one of the four allowed literals before writing. Same path-containment guard.

6. Implement `mark_stalled(path: Path, plan_file: str) -> None` — calls `set_status(..., "stalled")` then emits a loud warning. Strip non-printable/ANSI characters from `plan_file` before passing to any output function. Warning must appear on stderr AND be written to `_log_fh` if open.

7. Write `scripts/tests/test_prd_data_layer.py` covering:
   - `load_prd` / `save_prd` round-trip without data loss
   - `save_prd` atomicity (corrupt the tmp file path mid-write to verify rename)
   - `increment_attempts` modifies only the targeted entry
   - `set_status` modifies only the targeted entry
   - `mark_stalled` sets status and emits to stderr (capture with `capsys`)
   - All mutations idempotent
   - `load_prd` raises `SystemExit` on missing required keys
   - `load_prd` raises `SystemExit` on invalid status literal
   - `load_prd` raises `SystemExit` on non-integer `attempts`
   - `load_prd` raises `SystemExit` on `file` value containing path traversal (`../../.env`)

---

## Pre-Implementation Review

### Security

**HIGH — Path traversal via `file` field**
After joining `plans_dir / plan_file`, always resolve and assert containment:
```python
resolved = (plans_dir / plan_file).resolve()
if not str(resolved).startswith(str(plans_dir.resolve())):
    die(f"Refusing to access path outside plans_dir: {plan_file}")
```
Apply in `increment_attempts`, `set_status`, and `mark_stalled`.

**HIGH — Prompt injection via `file` field**
Validate `file` matches `r'^[\w.-]+\.md$'` (no newlines, no path separators) inside `load_prd`. Reject on failure.

**MEDIUM — Predictable tmp filename in `save_prd`**
Use `tempfile.mkstemp(dir=path.parent, prefix=".prd-", suffix=".tmp")` — never a fixed `.tmp` suffix.

**MEDIUM — No schema validation in `load_prd`**
Validate all required fields and types on load. Raise `SystemExit` with actionable message on failure.

**MEDIUM — Concurrent read-modify-write race**
Wrap all mutation functions with `fcntl.flock` on a `meta/plans/prd.json.lock` file held for the full load → mutate → save cycle.

**INFO — ANSI escape sequences in plan filename**
Strip non-printable characters from `plan_file` before passing to `info()`, `warn()`, or `die()`.

**INFO — `status` enum not validated**
`set_status` must reject values not in `{"pending", "in-progress", "done", "stalled"}`.

### Privacy

**HIGH — `meta/PRIVACY.md` absent**
Create `meta/PRIVACY.md` documenting: implementation logs capture Claude stdout (may contain secrets from target repos), `progress.md` contains free-form narrative committed to git, `prd.json` encodes GitHub issue numbers. Include retention guidance for `implementation-logs/`.

---

## Review & Testing Workflow

### 1. Run tests and lint
```bash
cd scripts && python3 -m pytest && python3 -m ruff check .
```
All tests must pass; ruff must report no errors.

### 2. Push branch and open PR
```bash
git push -u origin feat/ralph-prd-json-data-layer
gh pr create --base main --title "feat: prd.json data layer for Ralph loop" --body "Closes #2"
```

### 3. Verify dry-run still works (smoke check)
```bash
# In any repo with meta/plans/ — confirm existing README-based path still functions
python3 ~/.claude/scripts/run-next-plan.py --dry-run
```

---

## Verification Checklist

- [ ] `python3 -m pytest scripts/tests/test_prd_data_layer.py` — all tests pass
- [ ] `python3 -m ruff check scripts/` — no errors
- [ ] Path traversal test case passes (rejects `../../.env` as `file` value)
- [ ] `save_prd` uses `mkstemp` (no fixed `.tmp` filename)
- [ ] `mark_stalled` warning appears on stderr and in log file
- [ ] `meta/PRIVACY.md` created with data flow documentation
