# Plan: wenyan-ultra file handoff — rollout to remaining 7 reviewer agents

**Issues:** #30

**Prerequisite:** complete and merge `feat/wenyan-handoff-poc` (#28, #29) first — this plan replicates its proven pattern across the other 7 agents rather than re-deriving it.

---

## Goal

All 8 sdlc reviewer/QA agents (`sdlc-code-reviewer` plus the 7 others) uniformly use file-based wenyan-ultra handoff, so a full `/sdlc review` run — including under `--parallel` — produces a complete, correctly-translated set of findings with no filename collisions or cross-agent data leakage.

---

## Context

`feat/wenyan-handoff-poc` proves the file-handoff mechanism on `sdlc-code-reviewer` alone. This plan extends the same schema and orchestrator logic to `sdlc-style-reviewer`, `sdlc-security-reviewer`, `sdlc-privacy-reviewer`, `sdlc-accessibility-reviewer`, `sdlc-design-reviewer`, `sdlc-test-reviewer`, and `sdlc-qa-engineer`. Two agents need special handling: `sdlc-qa-engineer`'s PASS/FAIL + phased test-results output does not fit the `{file,line,summary,failure_scenario}` schema, and `sdlc-security-reviewer`/`sdlc-privacy-reviewer` findings are the most likely to need to reference literal PII/secrets to be actionable — both need explicit design decisions, not a mechanical copy-paste.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `agents/sdlc-style-reviewer.md` | Add `Write` tool; add handoff instructions under `## Output format`, following the merged PoC pattern exactly. |
| `agents/sdlc-security-reviewer.md` | Same, plus the stronger no-verbatim/no-partial-masking PII/secret rule with a worked BAD/GOOD example (this agent's findings are the most likely to need one). Add a distinct finding category for "possible real secret found — do not reproduce value." |
| `agents/sdlc-privacy-reviewer.md` | Same as security-reviewer: stronger PII rule, worked example, distinct "possible real PII in fixture/data" finding category. |
| `agents/sdlc-accessibility-reviewer.md` | Add `Write` tool; add handoff instructions under `## Output format`. |
| `agents/sdlc-design-reviewer.md` | Add `Write` tool; add handoff instructions under `## Output format`. |
| `agents/sdlc-test-reviewer.md` | Add `Write` tool; add handoff instructions under `## Output format`, appended after existing coverage-table content (same relative position as the other files). |
| `agents/sdlc-qa-engineer.md` | Define and document a QA-specific handoff schema (`{agent, status, tests_run, tests_failed:[{name, expected, actual, log_excerpt}]}`) rather than forcing the 4-field finding schema; require redaction of sensitive headers (`Authorization`, `Cookie`, `Set-Cookie`) and PII-shaped body fields from any `log_excerpt` before writing to scratchpad. |
| `skills/sdlc/SKILL.md` | Update Phase 3 (all 6 remaining review agents) and Phase 4 (`sdlc-qa-engineer`) invocation blocks to mint per-agent UUID+path and pass literally, same as the PoC. Add one central field-mapping reference (how domain-specific fields like `attack_scenario`/WCAG-criterion/brief-reference map into `summary`/`failure_scenario`) instead of repeating it per agent file. Add per-slot (not global) retry/hard-fail state tracking so concurrent `--parallel` failures don't cross-contaminate. Add an end-of-phase supervisory cleanup sweep that deletes any remaining `scratchpad/sdlc-*.json` handoff files regardless of success/failure, as defense in depth beyond each agent's own cleanup. |

### Steps

1. **Confirm the PoC pattern is merged.** Diff the merged `agents/sdlc-code-reviewer.md` and `skills/sdlc/SKILL.md` changes from `feat/wenyan-handoff-poc` — use them as the literal template for the 6 straightforward agents (style, security, privacy, accessibility, design, test), not a re-description from memory.
2. **Write a schema-agnostic shared handoff sentence.** The 8 agents use 4 different severity/category taxonomies (Critical→Major→Minor; Critical→High→Medium→Informational; Blocker→Major→Minor; style's non-severity categories). Word the new `## Output format` addition in terms of "for each reported item…" rather than assuming a severity axis, so it drops in unmodified across all of them except `sdlc-qa-engineer`.
3. **Apply the mechanical edit** to `sdlc-style-reviewer.md`, `sdlc-accessibility-reviewer.md`, `sdlc-design-reviewer.md`, `sdlc-test-reviewer.md`: add `Write` to tools, append the handoff instructions under `## Output format` in the same relative position as the PoC (end of section).
4. **Apply the hardened edit** to `sdlc-security-reviewer.md` and `sdlc-privacy-reviewer.md`: same base instructions, plus the explicit no-verbatim/no-partial-value rule with one BAD example (e.g. `"summary": "hardcoded key sk-live-51H2..."`) and one GOOD example (`"summary": "hardcoded cloud API key"`), plus a distinct finding category for suspected real secrets/PII that must be flagged by category+location only, never reproduced even partially.
5. **Design and apply the QA-specific schema** to `sdlc-qa-engineer.md` per the Files table above; do not force the 4-field finding schema onto it.
6. **Update `SKILL.md`:** per-agent UUID/path minting (mirroring the PoC) for all 7 remaining `Agent(...)` invocations in Phase 3 and Phase 4; add the central field-mapping reference; add per-slot retry/hard-fail bookkeeping keyed by (agent, uuid) so independent parallel failures don't share state; add an exact-path (never glob) cleanup step per agent plus an end-of-phase sweep.
7. **Validate collision-safety under `--parallel`:** run `/sdlc review --parallel` and confirm all 7 agents' filenames are distinct, no agent's file is deleted by another agent's cleanup, and a simulated single-agent retry doesn't affect sibling agents' in-flight files.
8. **Confirm planning-phase agents are unaffected** — `sdlc-doc-writer` and the Phase 1 planning invocations of security/privacy/a11y/design reviewers stay plain-text, untouched by this change.

---

## Acceptance Criteria

- [ ] All 8 sdlc reviewer/QA agents write handoff files per their respective schema (4-field for 6 agents, QA-specific for `sdlc-qa-engineer`)
- [ ] Orchestrator's read/decode/retry/hard-fail logic works identically across all 8, including under `--parallel`, with no filename collisions and no cross-agent file deletion
- [ ] A full `/sdlc review` run (series and `--parallel`) produces a complete, correctly-translated set of findings across all 8 agents
- [ ] `sdlc-security-reviewer`/`sdlc-privacy-reviewer` findings never contain verbatim or partially-masked secret/PII values
- [ ] Planning-phase agents (doc-writer, planning-phase security/privacy/a11y/design reviews) are unaffected — still plain-text
- [ ] Retry/hard-fail state is tracked per (agent, uuid) slot, not globally

---

## Pre-Implementation Review

**Security:**
- Grant `Write` to all 7 agents rather than relying on `Bash`/heredoc authoring — heightened injection risk specifically for `sdlc-security-reviewer`/`sdlc-privacy-reviewer` content, which is most likely to contain hazardous strings (backticks, `$()`, unescaped quotes) from the reviewed code.
- Regenerate the filename allow-list regex to enumerate all 8 literal agent names (don't over-broaden to `sdlc-*` or under-match `sdlc-qa-engineer`'s different naming shape); cross-check the in-file `agent` field against the specific dispatched slot to prevent misattribution across differently-trusted agent types.
- Cleanup must delete by exact minted path per agent, never by glob, to avoid a race where one agent's cleanup deletes a concurrent sibling's not-yet-read file.
- Retry/hard-fail bookkeeping must be keyed per (agent, uuid) slot — a shared/global retry counter will cross-contaminate independent parallel failures. Decide and document explicitly whether one agent's hard-fail aborts the whole run or only that agent's slot (silent dropping of a security finding is the wrong default).
- `sdlc-qa-engineer`'s PASS/FAIL+phases output doesn't fit the 4-field schema — resolve with a QA-specific schema (per Files table) rather than forcing conformance and risking silently dropped diagnostic detail.
- Add an aggregate per-run byte/file-count budget across all 8 handoff files (not just per-file limits), given 8x the POC's write volume under `--parallel`.
- On hard-fail, still delete/quarantine the file after capturing diagnostics — don't let the two most sensitive agents' (security/privacy) hard-fail paths be the ones most likely to leave files on disk.

**Privacy:**
- `sdlc-security-reviewer`/`sdlc-privacy-reviewer` need an explicit, example-backed rule (not just inherited from the PoC) since their entire purpose is describing PII/secret problems — ban partial/masked/truncated value reproduction too, not just full literals.
- Add a distinct finding category across privacy/security/QA for "possible real (non-synthetic) PII/secret discovered" that is itself reported by category+location only.
- `sdlc-qa-engineer` must redact sensitive headers and PII-shaped body fields from any raw trace/log excerpt before it reaches the handoff file.
- Add a supervisory cleanup sweep at the end of Phase 3/4 in `SKILL.md` in addition to each agent's self-cleanup, since a crash between phases is more likely at 8x agent count.
- Note in the plan (informational, not blocking): consider a one-paragraph addition to `meta/PRIVACY.md` documenting that the review pipeline processes PII/secret categories as part of its operation.

**Accessibility:** No WCAG-relevant surface. Downstream note carried forward: verify the decode/decompression step exists for all 7 newly-converted agents, not just `sdlc-code-reviewer`, so compressed output never leaks into the user-facing report.

**Design:**
- Land and merge the PoC first — don't hand-author each of the 7 files from a verbal description of the pattern; diff against the merged PoC commit to avoid drift.
- `sdlc-qa-engineer.md`'s structurally different output section is not a mechanical copy-paste target — needs its own schema as scoped above, decided before implementation, not improvised per-file.
- Word the shared handoff addition schema-agnostically so it fits `sdlc-style-reviewer`'s non-severity category taxonomy without rewording.
- Document the field-mapping rule for domain-specific extra fields (attack_scenario, WCAG criterion, brief reference, etc.) once centrally in `SKILL.md`, not re-derived per agent file.
- Keep the *how to read back* description in `SKILL.md` only; keep the *how to write* description in each agent file only — avoid duplicating/conflicting protocol descriptions across the two doc types.
