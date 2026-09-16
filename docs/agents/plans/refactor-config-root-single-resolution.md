# Plan: resolve config root once per run

**Issues:** #60

---

## Goal

The project config root is resolved from disk exactly once per run and threaded through as a value, instead of being independently re-derived (with its full validation, including the both-layouts-present abort) at roughly a dozen call sites scattered across `scripts/run-next-plan.py`.

---

## Context

`resolve_config_root` performs real filesystem checks — including an abort if both supported config-root layouts are simultaneously present — and is currently called fresh from many independent call sites (directly, or via `config_root_rel`, `plans_dir_for`, `logs_rel`, and their callers) rather than once in the entry point. This means a mid-run change to the working tree could trigger the ambiguous-layout abort deep into a run, after other work has already been committed, instead of failing fast at the top. It's also a DRY violation: the same filesystem-derived value is recomputed repeatedly, and the "resolved root as a repo-relative POSIX path" idiom is separately reimplemented at several of those call sites. This is the largest and highest-risk finding in this triage batch, so it gets its own plan rather than being bundled with the smaller fixes in the other clusters.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Resolve the config root once in `main()`; thread the resolved value through every function that currently re-derives it; extract the repeated relative-path-formatting idiom into one helper |
| `scripts/tests/` (orchestration / config-root test files) | Update any tests that call the refactored functions directly, to pass the resolved config root instead of relying on each function re-resolving it |

### Steps

1. In `main()` (or the earliest practical point in the entry point, before any prompt is built or long-running work begins), call the config-root resolution function once and hold the result in a local variable.
2. Change every function that currently calls the resolution function (or one of `config_root_rel` / `plans_dir_for` / `logs_rel` internally) to instead accept the already-resolved config root (or the specific derived value it needs) as a parameter, and pass the value down from `main()`'s call sites. Keep the resolution function itself — its symlink check, both-layouts-present abort, and outside-repo check — unchanged; only *how often* and *where* it's invoked changes.
3. Consolidate the repeated "resolved root as a repo-relative POSIX path" idiom (currently reimplemented at multiple call sites) into a single helper, and have every site that needs that string call the helper instead of reimplementing it.
4. Update any tests that currently call the refactored functions with just a `repo_root` and expect them to resolve the config root internally — pass the resolved root explicitly instead.
5. Run `cd scripts && python3 -m pytest` and `python3 -m ruff check .`. Manually trace through the both-layouts-present abort path and the symlinked-root rejection path to confirm both still fire at the same point in a run (now via the single early call) as they did before.

---

## Acceptance Criteria

- [ ] The config-root resolution function's full validation logic runs exactly once per normal run, at or near the top of `main()`
- [ ] No other function in the script re-invokes the resolution function internally — all receive the resolved value as a parameter
- [ ] The repo-relative-path-formatting idiom exists in exactly one place, reused everywhere it's needed
- [ ] The both-layouts-present abort, symlinked-root rejection, and outside-repo rejection all still fire under the same conditions as before the refactor
- [ ] `cd scripts && python3 -m pytest` passes in full
- [ ] `python3 -m ruff check .` passes

---

## Pre-Implementation Review

Not run for this plan (see triage note — this batch skipped `/plan-iteration` Step 6's dispatch of the four planning-review agents; only Step 5 clustering and the Standard Plan Template were requested). Flagging for the next `/plan-iteration review` pass since this plan touches the security-relevant config-root resolution path across most of the script's call graph.
