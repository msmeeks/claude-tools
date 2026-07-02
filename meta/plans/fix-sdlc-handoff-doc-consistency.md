# Plan: Fix stale/inconsistent wenyan-ultra handoff documentation and add drift enforcement

**Issues:** #39, #40, #41

---

## Goal

`docs/features/agents.md` and `docs/features/skills.md` accurately describe the shipped 8-agent handoff rollout (not the earlier PoC), the agent-count phrasing in `skills/sdlc/SKILL.md` and `docs/features/sdlc-review-handoff.md` matches, and an automated check catches future drift between the 9 files that duplicate the handoff finding schemas.

---

## Context

The same SDLC review that produced `fix-sdlc-handoff-hardening.md` (issues #34-#38) also found the wenyan-ultra handoff protocol's documentation has fallen out of sync with the code/config that shipped it: two feature docs never got updated for the #30 rollout and still describe a `sdlc-code-reviewer`-only PoC (#39); two other docs describe the same 8-agent schema split with different, confusing agent-count phrasing (#41); and the schema blocks themselves are duplicated near-verbatim across 9 files with nothing but a prose reminder keeping them in sync (#40). These three are grouped separately from the hardening cluster because they're pure documentation/tooling fixes with no behavioral change to the orchestrator, and #40 in particular is best done last, once the reference wording from #39/#41 has settled, so the new consistency check is written against the corrected text rather than needing a second pass.

---

## Implementation Notes

### Files to Modify / Create

| File | Change |
|------|--------|
| `docs/features/agents.md` | Replace "Exception (PoC): `sdlc-code-reviewer`... other six review agents are unaffected" with a statement that all 8 Phase 3/4 agents use handoff mode (#39) |
| `docs/features/skills.md` | Replace "`sdlc-code-reviewer` alone currently uses a compressed file-handoff protocol... (PoC)" the same way (#39) |
| `skills/sdlc/SKILL.md` | Rewrite the field-mapping reference's agent-grouping sentence to use one consistent count phrasing matching `sdlc-review-handoff.md` (#41) |
| `docs/features/sdlc-review-handoff.md` | Rewrite its schema-table grouping to match the same consistent phrasing (#41) |
| `scripts/check_sdlc_schema_consistency.py` (new) | Extracts the fenced schema JSON block from each of the 9 source files (`skills/sdlc/SKILL.md`, `docs/features/sdlc-review-handoff.md`, and all 7 `agents/sdlc-*.md` files) and asserts structural equality per schema variant (plain 4-field, 4-field+`category`, QA schema) (#40) |
| `scripts/tests/test_sdlc_schema_consistency.py` (new) | Wraps the checker as an automated test, following the existing convention in `scripts/tests/test_sdlc_gate.py`, so drift is caught by the normal test run (#40) |

### Steps

1. **#39 — fix stale PoC-only docs.** In `docs/features/agents.md` and `docs/features/skills.md`, replace the "PoC / other six unaffected" language with a statement that all 8 Phase 3/4 review-and-QA agents use the compressed handoff protocol, matching `docs/features/sdlc-review-handoff.md`.
2. **#41 — unify agent-count phrasing.** In `skills/sdlc/SKILL.md`'s field-mapping reference and in `docs/features/sdlc-review-handoff.md`'s schema table, use one consistent phrasing for the split, e.g. "5 agents use the plain 4-field schema; 2 (security, privacy) add `category`; 1 (`sdlc-qa-engineer`) uses a separate PASS/FAIL schema — 8 total." Check the 7 `agents/sdlc-*.md` files for any restated count and fix any that conflict.
3. **#40 — write the consistency checker.** Add a script that: (a) locates each of the 9 source files, (b) extracts the fenced JSON schema block(s) from each, (c) classifies each block by schema variant (plain 4-field / 4-field+`category` / QA schema) based on its key set, and (d) asserts all blocks of the same variant are structurally identical (same keys, same nesting, same which-fields-are-compressed markers), failing with a message naming the divergent file(s) if not.
4. Wrap the checker in a pytest test alongside `scripts/tests/test_sdlc_gate.py` so it runs with this project's existing test invocation.
5. Run the new test against the post-#39/#41 state of the repo to confirm it passes, then deliberately break one copy locally (not committed) to confirm the test fails with a useful message, before finalizing.

---

## Acceptance Criteria

- [ ] Neither `docs/features/agents.md` nor `docs/features/skills.md` describes the handoff protocol as limited to `sdlc-code-reviewer` alone (#39)
- [ ] Both docs state all 8 Phase 3/4 agents use handoff mode, consistent with `docs/features/sdlc-review-handoff.md` (#39)
- [ ] `skills/sdlc/SKILL.md` and `docs/features/sdlc-review-handoff.md` describe the same agent grouping with matching counts (#41)
- [ ] No `agents/sdlc-*.md` file restates a conflicting count (#41)
- [ ] Running the new consistency check passes against the current (post-fix) state of all 9 files (#40)
- [ ] Deliberately editing one copy's schema causes the check to fail, naming the diverging file(s) (#40)
- [ ] The new check is wired into this project's existing automated-test invocation (#40)

---

## Pre-Implementation Review

_Not run — this is a documentation/tooling-only change with no application code, UI, or new data flow affected._
