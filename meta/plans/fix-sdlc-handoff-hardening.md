# Plan: Harden the SDLC Phase 3/4 handoff orchestration instructions

**Issues:** #34, #35, #36, #37, #38

---

## Goal

The `/sdlc` orchestrator's Phase 3/4 compressed-handoff instructions (`skills/sdlc/SKILL.md` + `docs/features/sdlc-review-handoff.md`) no longer contain a banned wildcard pattern, a weak symlink-deletion instruction, an unaddressed prompt-injection path through decoded findings, an unverifiable redaction guarantee, or state tracking that can't survive a session interruption.

---

## Context

An SDLC review of the wenyan-ultra handoff rollout (issues #28-#30, see `meta/sdlc-review-findings.md`) surfaced five distinct correctness/hardening gaps in the orchestrator's own instructions for Phase 3 (7 review agents) and Phase 4 (`sdlc-qa-engineer`). All five are text-only edits to the same two files — the orchestration skill itself and its reference documentation — so they're grouped into one cluster rather than five separate PRs. None of them require or depend on resolving the still-open `wenyan-ultra` compression-algorithm spec gap (tracked separately, needs-info, in #33): each fix operates on already-decoded text, on the sweep/state-tracking mechanics, or on filename patterns, none of which change regardless of how #33 is eventually resolved.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `skills/sdlc/SKILL.md` | Phase 4 cleanup wildcard fix (#35); symlink resolve→refuse wording (#37); decoded-text-is-inert-data statement near each decode step (#34); defense-in-depth pattern check + priority handling for `possible-real-secret`/`possible-real-pii` findings (#36); on-disk persistence for the per-slot `(agent, uuid)` state table (#38) |
| `docs/features/sdlc-review-handoff.md` | Mirror all five changes above in the corresponding sections (Failure handling, End-of-phase cleanup sweep, Per-slot state tracking) so the reference doc stays in sync with `SKILL.md` |

### Steps

1. **#35 — Phase 4 wildcard.** Replace the Phase 4 cleanup instruction's bare `sdlc-*.json` wildcard with the same 8-literal-prefix-plus-UUID pattern (or a direct reference to "the same sweep defined for Phase 3") already used in the Phase 3 cleanup sweep.
2. **#37 — symlink handling.** Change the cleanup sweep instruction from "resolve and delete each match individually (still no symlinks)" to "skip and report (never delete) any scratchpad entry that is a symlink, or whose resolved path differs from its literal path." Apply in both the Phase 3 description and the shared reference used by Phase 4.
3. **#34 — decoded text is inert.** Immediately after each "decode only the documented compressed fields... then delete" instruction (Phase 3 and Phase 4), add a sentence stating decoded finding text is inert data — reported/acted on structurally (file/line/fix) only, never treated as a further instruction stream — mirroring the discipline already expected of reviewer agents toward diff content.
4. **#36 — redaction defense-in-depth.** After the decode step, add an orchestrator-side pattern check (auth header names, credential key-prefix shapes, email-shaped substrings) run against decoded `summary`/`failure_scenario`/`log_excerpt`/`expected`/`actual` fields. Add explicit handling: any finding with `category` of `possible-real-secret`/`possible-real-pii` is surfaced to the user immediately and prominently, separate from the generic Critical/Blocker findings list.
5. **#38 — persist per-slot state.** Specify an on-disk JSON file in the scratchpad directory (distinct from per-agent handoff files, e.g. named so it can't collide with the 8 handoff-filename regexes) that the orchestrator rewrites after every `(agent, uuid)` state transition and reads back first on resume. Note explicitly that only the orchestrator writes this file (sub-agents never touch it) and it is single-threaded even under `--parallel`, so a whole-table rewrite per transition needs no locking. Delete this file as part of the existing end-of-phase cleanup sweep.
6. Re-read both files end to end after all five edits to confirm the "byte-for-byte identical... keep in sync" claim between them still holds for the sections touched.

---

## Acceptance Criteria

- [ ] Phase 4's cleanup instruction no longer contains a bare `sdlc-*.json` wildcard (#35)
- [ ] The cleanup sweep instruction says to skip-and-report (never delete) symlinks or resolved-path mismatches, in both files (#37)
- [ ] Both files state decoded finding text is inert data, not a directive stream, at each decode step (#34)
- [ ] Both files describe a post-decode pattern check and explicit priority handling for `possible-real-secret`/`possible-real-pii` findings (#36)
- [ ] Both files describe an on-disk, orchestrator-owned persisted state table for per-slot retry/hard-fail tracking, including its location, rewrite/read-back behavior, and cleanup (#38)
- [ ] `skills/sdlc/SKILL.md` and `docs/features/sdlc-review-handoff.md` remain consistent with each other across all five changes

---

## Pre-Implementation Review

_Not run — this is a documentation/orchestration-instruction-only change with no application code, UI, or new data flow; `/sdlc plan` review agents (security/privacy/a11y/design) were not dispatched for the same reason the original diff's own SDLC review skipped accessibility and design (see `meta/sdlc-review-findings.md`, line 3)._
