# Plan: Fix runner attempts accounting

**Issues:** #45, #46

---

## Goal

A plan's `attempts` counter reflects only sessions that actually ran and worked on *that* plan, so plans are never marked `stalled` (or escalated to max-effort) without ever having been implemented.

---

## Context

The Ralph-loop orchestrator (`scripts/run-next-plan.py`) charges an attempt to the wrong plan and at the wrong time. `select_next_plan()` returns `eligible[0]`, but the Claude prompt explicitly tells the session to pick the highest-priority plan — which may differ — so the counter tracks a plan no session touched (#45). Separately, `increment_attempts()` runs *before* the `claude` invocation with no rollback on the `rate_limit` path, so a session/usage-limit death that does zero work still burns an attempt (#46). Together, a plan can reach `stalled` in minutes with no implementation session, drop out of `eligible` permanently, and burn max-effort tokens via escalation reading the same inflated counter.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Move `increment_attempts` after the invocation; skip on `rate_limit`; attribute the attempt to the plan actually worked on |
| `scripts/tests/test_orchestration.py` | Cover: no increment on rate_limit, attribution to the worked plan, no `mark_stalled` for an unrun plan |

### Steps

1. **#46 — don't burn attempts on limit deaths.** Currently `increment_attempts(prd_path, selected["file"])` runs at `run-next-plan.py:1271`, before the `claude` subprocess. Move the increment (and the subsequent `mark_stalled` check at 1276–1281) to *after* the invocation completes and `scan_output()` has classified the outcome. When the outcome is `rate_limit`, do **not** increment and do **not** run the stall check — mirror the in-process retry policy already documented in the module docstring (the gate treats limits as non-failures). Preserve model-escalation reads of `attempts` (lines 1294–1297) — evaluate escalation from the counter's value *before* this run's increment, so behavior for genuine attempts is unchanged.
2. **#45 — charge the plan actually worked on.** `select_next_plan()` (`run-next-plan.py:334`, returns `eligible[0]` at 365) is the runner's guess. After the session, determine which plan Claude advanced and charge that one. Preferred approach (option 1 in #45): reload `prd.json` and find the entry that flipped to `status: "done"` this run; charge the attempt there. If nothing flipped to done, fall back to option 2: parse a declared sigil (e.g. `<plan>slug.md</plan>` on its own line, like the existing `COMPLETE_SIGIL_RE`) emitted by the session before implementing, and add that instruction to `_build_claude_prompt`. If neither signal is present, attribute nothing (do not guess).
3. **Guard `mark_stalled`.** Ensure `mark_stalled` can only fire for a plan that has a demonstrably-run session recorded against it — never for a plan that only absorbed guessed/limit increments.
4. Follow the failing-test-first workflow: write tests in `test_orchestration.py` asserting each behavior before implementing. Run `python3 -m pytest` from `scripts/`.

---

## Acceptance Criteria

- [ ] A `rate_limit` outcome does not increment the persisted `attempts` for any plan.
- [ ] The attempt is charged to the plan the session actually advanced (or nothing, if undeterminable) — never to `eligible[0]` by default.
- [ ] `mark_stalled` never fires for a plan no session demonstrably executed.
- [ ] Model escalation still triggers at the documented thresholds for genuine repeated attempts.
- [ ] Tests cover rate-limit no-charge, correct attribution, and the unrun-plan stall guard.

---

## Pre-Implementation Review

**Security (sdlc-security-reviewer):**

- **Medium — `<plan>` sigil trust boundary.** If Step 2 attributes the attempt from a Claude-emitted `<plan>...</plan>` sigil, that value is untrusted (Claude runs with `bypassPermissions` and can echo injected content from issue bodies, `progress.md`, PR comments, etc.). Existing guards (`PLAN_FILE_RE` at `run-next-plan.py:66`, `_resolve_plan_path` at 269, `_find_plan_entry` at 294) prevent traversal/RCE, so worst case is attempt-count integrity abuse — forcing `mark_stalled` on an unrelated plan (a DoS on loop progress). **Mitigation:** validate the parsed sigil against `selected["file"]` / the current eligible set; on mismatch, fall back to charging `selected["file"]` (or no-op) and emit `warn()`. Prefer the read-back-from-`prd.json`-diff approach (option 1), which sidesteps this entirely.
- **Informational — don't leak raw sigil/output into GitHub.** Do not fold raw `output_text` or sigil content into any `gh pr edit`/`gh issue create` body without the allow-list check; PR-body construction (lines 614/838) must keep building from `prd.json` state, not raw output.
- No new command/shell injection: all subprocess calls remain list-argv, no `shell=True`. Privacy/a11y/design: N/A (internal orchestration logic, no UI or user data).
