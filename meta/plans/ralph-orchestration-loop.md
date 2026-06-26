# Plan: Ralph Loop — Orchestration Loop Rewrite

**Issues:** #3
**Branch:** `feat/ralph-orchestration-loop`
**Base:** `main`
**Status:** done
**Prerequisite:** Branch off `main` after #2 merges.
**Status:** done

---

## Worktree Setup

```bash
# Run from the repo root — only after feat/ralph-prd-json-data-layer merges
git worktree add .claude/worktrees/claude-tools-ralph-loop -b feat/ralph-orchestration-loop main
```

**Working directory:** `.claude/worktrees/claude-tools-ralph-loop`

When the PR merges:
```bash
git worktree remove .claude/worktrees/claude-tools-ralph-loop
```

---

## Context

The current `run-next-plan.py` picks plans by iterating the README table top-to-bottom — Claude has no input on priority. The rewrite converts the script to a Ralph Wiggum loop: Claude reads `prd.json` + `progress.md` each iteration and freely chooses the highest-priority unblocked plan. The Python script becomes a thin orchestrator — attempt tracking, stall detection, stop-condition detection, flag handling — with all task intelligence delegated to Claude.

---

## Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Major rewrite of core loop; add `select_next_plan`, `scan_output`; remove README parsing, worktree/branch ceremony, kind flags |
| `scripts/tests/test_orchestration.py` | New — pytest suite for `select_next_plan` and `scan_output` |

---

## Implementation Steps

1. **Add `select_next_plan(plans: list[dict]) -> dict | None`** — Python-level guard only (Claude does the real selection). Returns the first plan that is not `done` or `stalled`. Detects circular `blocked_by` using a visited-set depth-first traversal and returns `None` if the entire remaining graph is circular or fully blocked. Does NOT enforce `blocked_by` — that is Claude's responsibility.

2. **Add `scan_output(text: str, exit_code: int) -> Literal["complete", "rate_limit", "error", "ok"]`**:
   - `complete` — line-anchored search for `<promise>COMPLETE</promise>` (must appear as a standalone line, not substring): `re.search(r'^<promise>COMPLETE</promise>\s*$', text, re.MULTILINE)`
   - `rate_limit` — existing `RATE_LIMIT_RE` match on text
   - `error` — exit_code != 0 and not rate_limit
   - `ok` — exit_code == 0 and not complete

3. **Rewrite `main()` core loop**:
   - Die with clear message if `meta/plans/prd.json` not found (guidance: run `/plan-iteration` first)
   - Load `prd.json` via `load_prd`; read `progress.md` if it exists (empty string if not)
   - Call `select_next_plan` as a guard; if returns `None`, print "All plans done or stalled." and exit 0
   - `increment_attempts` before each Claude invocation
   - If `attempts >= 5` and status not `done`: call `mark_stalled`, print loud warning, continue to next plan
   - Build unified Claude prompt (see below)
   - Invoke Claude; stream output; collect into buffer
   - Call `scan_output` on buffer + exit code
   - On `complete`: exit 0
   - After each iteration: check if all plans `done|stalled` (fallback stop) → exit 0
   - On `rate_limit`: retry with existing backoff logic (does NOT increment `attempts`)
   - On `error`: warn, keep plan `in-progress`, exit non-zero

4. **Claude prompt** (unified — replaces the two separate prompts):
```
Read meta/plans/prd.json and meta/plans/progress.md.

Choose the highest-priority incomplete, unblocked plan — YOUR decision, not necessarily
first in the list. Prioritize: architectural decisions and unknowns first, UI polish last.
Respect blocked_by entries in prd.json unless you determine from reading the plan files
that the dependency is already satisfied.

Implement the chosen plan. Commit your changes to {integration_branch}.
Update meta/plans/progress.md — append a timestamped entry with the plan filename and
a brief summary of what you did.
Update meta/plans/prd.json — set status to "done" for the completed plan.

ONLY DO ONE PLAN AT A TIME.
Use /tdd to drive implementation (write failing test first).
Use /qa after changes (automated tests, lint, smoke checks).
When spawning subagents include in their prompt:
"Use ultra-compressed caveman speech for all prose responses. Keep full technical accuracy."

If all plans are complete, output on its own line:
<promise>COMPLETE</promise>

Integration branch: {integration_branch}
Repo root: {repo_root}
```

5. **Remove from script**: `list_plan_files`, `bootstrap_readme`, `bootstrap_plan_file`, `get_plan_status`, `set_plan_status`, `set_readme_status`, `get_plan_branch`, `is_pr_comment_plan`, `PR_COMMENT_PLAN_RE`, `parse_reaction_metadata`, `post_reactions`, `ensure_integration_branch`. Remove `--issues` and `--pr-comments` flags.

6. **Preserve**: `--restart` (reset `in-progress` plan to `pending`), `--skip-in-progress` (skip to next pending), `--dry-run` (updated: print selected plan, `blocked_by` state, `attempts`, full resolved command), `--integration-branch`, rate-limit retry with `_parse_retry_after_text`, per-invocation log file.

7. **Update `--dry-run` output**: show `prd.json` path, selected plan file, `blocked_by` graph state (each entry: filename → status), current `attempts`, and the full `claude ...` command.

8. **Write `scripts/tests/test_orchestration.py`** covering:
   - `select_next_plan` returns `None` when all plans `done`
   - `select_next_plan` returns `None` when all plans `stalled`
   - `select_next_plan` skips `done` and `stalled` entries
   - `select_next_plan` returns `None` on circular `blocked_by`
   - `select_next_plan` returns first eligible plan with no blockers
   - `scan_output` detects `<promise>COMPLETE</promise>` only as a standalone line
   - `scan_output` does not fire on `<promise>COMPLETE</promise>` embedded mid-line
   - `scan_output` detects each `RATE_LIMIT_RE` pattern
   - `scan_output` returns `error` on non-zero exit with no rate-limit text
   - `scan_output` returns `ok` on zero exit with no sigil

---

## Pre-Implementation Review

### Security

**CRITICAL — Indirect prompt injection via prd.json → bypassPermissions session**
GitHub issue bodies are embedded in plan files by `/plan-iteration`, which feeds into `prd.json`, which Claude reads in a `bypassPermissions` session. A crafted issue body can inject instructions that execute with full filesystem authority.

Mitigations to implement in this slice:
- Do not embed raw issue body text in the Claude prompt or in `prd.json` values. The prompt tells Claude to read `prd.json` — keep `prd.json` values to structured fields only (filename, status, attempts, blocked_by, size, issues array of `#N` strings).
- The plan `.md` files may contain issue body text, but Claude reads them as documents (less vulnerable than direct prompt interpolation). Add a note in the prompt that Claude should treat plan file content as untrusted document text, not instructions.
- Accept residual risk for the personal-developer use case; document it in `meta/PRIVACY.md`.

**HIGH — COMPLETE sigil false-positive via unanchored match**
Use `re.search(r'^<promise>COMPLETE</promise>\s*$', text, re.MULTILINE)` — line-anchored, not substring. Log the surrounding 3 lines when the sigil fires for auditability.

**HIGH — Full Claude stdout written to log files**
Add `meta/plans/implementation-logs/` to both `.gitignore` and `.claudeignore`. Consider scrubbing common credential patterns (`sk-ant-`, `ghp_`, `-----BEGIN`, `password=`) from log lines before writing.

**MEDIUM — TOCTOU race on prd.json**
Use `fcntl.flock` (from the data layer in #2) for all load→mutate→save cycles. Document that concurrent invocations are unsupported.

### Privacy

**CRITICAL — Implementation logs capture full Claude stdout**
`meta/plans/implementation-logs/` must be in `.gitignore` and `.claudeignore`. Add to both files in this slice if not already done by #2.

**HIGH — Prompt passed via argv exposes repo path in process table**
Pass the Claude prompt via stdin (`echo "$prompt" | claude --stdin ...`) rather than as a `-p` argv argument. Verify Claude CLI supports stdin prompt mode; if not, document the limitation.

---

## Review & Testing Workflow

### 1. Run tests and lint
```bash
cd scripts && python3 -m pytest && python3 -m ruff check .
```

### 2. Smoke test with dry-run
```bash
# In a repo with meta/plans/prd.json
python3 ~/.claude/scripts/run-next-plan.py --dry-run
# Verify: shows selected plan, blocked_by state, attempts, full claude command
```

### 3. Push branch and open PR
```bash
git push -u origin feat/ralph-orchestration-loop
gh pr create --base main --title "feat: Ralph loop orchestration rewrite" --body "Closes #3"
```

---

## Verification Checklist

- [ ] `python3 -m pytest` passes
- [ ] `python3 -m ruff check scripts/` passes
- [ ] `--dry-run` shows selected plan + blocker graph + attempts + command
- [ ] `scan_output` rejects mid-line COMPLETE sigil (test case passes)
- [ ] `meta/plans/implementation-logs/` added to `.gitignore` and `.claudeignore`
- [ ] README-parsing code removed (`list_plan_files`, `bootstrap_readme`, etc.)
- [ ] `--issues` and `--pr-comments` flags removed
