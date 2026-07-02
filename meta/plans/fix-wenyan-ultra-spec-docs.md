# Plan: Document that wenyan-ultra is a lossy compression level, not a codec

**Issues:** #33

---

## Goal

`docs/features/sdlc-review-handoff.md` and `skills/sdlc/SKILL.md` state plainly, near their first substantive use of the term, that `wenyan-ultra` is the compression intensity level defined in `~/.claude/skills/caveman/SKILL.md` (description + illustrative examples only) — not a formal grammar, character set, or deterministic codec — and that fidelity is enforced empirically via `scripts/wenyan_validation_run.py`'s drift gate (0 substantive mismatches per PR, independently across 5 PRs), not by a formal spec.

---

## Context

An SDLC review of the wenyan-ultra handoff rollout (#28-#30) found that every file referencing `wenyan-ultra` used codec-shaped language ("compression scheme," "decode") without ever stating where the scheme is actually defined. The maintainer resolved the underlying strategic question via a grilling session on #33: no formal grammar/codec will be written; the term stays; compression is accepted as lossy and LLM-approximated; fidelity is verified empirically by the validation script's drift gate rather than structurally. This plan is the narrow, purely mechanical documentation fix left over from that decision — the validation script itself (issue #31, now `scripts/wenyan_validation_run.py`) already implements the drift gate this plan's docs will point to.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `docs/features/sdlc-review-handoff.md` | Near the first use of `wenyan-ultra`, add: source citation (`~/.claude/skills/caveman/SKILL.md`), explicit "lossy, LLM-approximated, not a deterministic codec" statement, and a pointer to `scripts/wenyan_validation_run.py`'s drift gate as how fidelity is actually verified. |
| `skills/sdlc/SKILL.md` | Same clarification, near its own first use of the term. |

### Steps

1. Add the citation + lossy/non-codec statement to `docs/features/sdlc-review-handoff.md`.
2. Add the same statement to `skills/sdlc/SKILL.md`.
3. In both files, note that per the `caveman` skill's own rules, technical specifications, identifiers, code, and error strings are never compressed at any level — only prose fields are.
4. Re-read both files to confirm they don't otherwise imply a formal grammar/character set/deterministic decode procedure exists elsewhere.

---

## Acceptance Criteria

- [ ] `docs/features/sdlc-review-handoff.md` states `wenyan-ultra`'s definition source and lossy/non-codec nature
- [ ] `skills/sdlc/SKILL.md` states the same
- [ ] Both reference `scripts/wenyan_validation_run.py`'s drift gate (0 mismatches per PR, independently across 5 PRs) as how fidelity is actually verified
- [ ] Neither file is left implying a formal grammar, character set, or deterministic decode procedure exists

---

## Pre-Implementation Review

_Not run — documentation-only change, no application code, UI, or new data flow._
