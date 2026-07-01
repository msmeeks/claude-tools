# Plan: wenyan-ultra offline validation suite (token/latency/drift)

**Issues:** #31

**Prerequisite:** complete and merge `feat/wenyan-handoff-rollout` (#30) first — this validation gates the full 8-agent rollout before it's treated as production-ready.

---

## Goal

Produce a ship/no-ship recommendation for the wenyan-ultra handoff protocol, backed by measured token savings, latency, and a drift/accuracy score comparing baseline (caveman-disabled) vs. wenyan-ultra-enabled sdlc review runs across 5 real past PRs.

---

## Context

Issues #28-#30 build the mechanism; this issue proves it's safe to rely on before it's the default behavior. The offline pass runs the full sdlc review pipeline twice per selected PR — once at normal verbosity (temporarily disabling the global `/caveman` CLAUDE.md directive) as baseline, once with wenyan-ultra handoff enabled — and compares. Tokens are the headline metric; drift (count of findings differing in file/line/substance) is the actual ship/no-ship gate; latency is informational only. Both `claude-tools` and the other candidate source repo, `bible-flashcards`, are **public** repositories, which materially constrains how the comparison report can be written.

---

## Implementation Notes

### Files to Modify / Create

| File | Change |
|------|--------|
| `meta/wenyan-handoff-validation-report.md` (new) | The final report: PR selection + rationale, per-PR token/latency/drift numbers, summary ship/no-ship verdict. **Not** under `meta/plans/` — that directory is deleted wholesale by `close-iteration` Step 6a before merge, which would silently destroy the ship/no-ship record. Follows the existing `meta/sdlc-review-findings.md` convention: H1 title, context paragraph, `---`-delimited sections. |
| `meta/plans/implementation-logs/` (scratch, transient) | Any intermediate run logs/scripts used to drive the comparison can live here temporarily; nothing sensitive or final should be committed here. |

### Steps

1. **Select the 5-PR corpus.** Prefer PRs (from `claude-tools` and other same-account repos) that already have recorded sdlc findings under `meta/plans/` or equivalent as drift ground truth. Include at least one PR from `bible-flashcards`. Document rationale (size/type: small fix, medium feature, large refactor, security-touching, UI-touching) for each. Before including any security-touching PR with a known historical secret, verify the credential was actually rotated — don't assume from memory.
2. **Confirm repo sensitivity.** Both `claude-tools` and `bible-flashcards` are public — treat all PR content as subject to redaction rules below regardless of source repo.
3. **Run baseline pass** per PR: temporarily disable the global `/caveman` CLAUDE.md directive, run the full sdlc review pipeline, capture total token count (input+output across the 8 agents) and wall-clock latency.
4. **Run wenyan-ultra pass** per PR: same pipeline with the merged `feat/wenyan-handoff-rollout` handoff enabled, capture the same metrics.
5. **Compute drift score** per PR: count and describe findings that differ in file/line/substance between the two runs.
6. **Write the report** at `meta/wenyan-handoff-validation-report.md`, referencing each PR by number/URL/commit SHA — never quoting raw diff hunks or verbatim finding text pulled from the reviewed source. Summarize findings by category/count only. If a finding legitimately surfaced a secret-like string during either run, redact it (`REDACTED`) in the report rather than reproducing it.
7. **Summarize verdict:** ship/no-ship recommendation based on drift being ~0 substantive mismatches, with token savings reported as the headline number and latency as a secondary/informational figure.

---

## Acceptance Criteria

- [ ] 5 real past PRs selected and documented, with rationale for each (size/type, whether it had prior recorded sdlc findings as ground truth)
- [ ] At least one PR sourced from `bible-flashcards`
- [ ] Baseline and wenyan-ultra runs completed for all 5 PRs
- [ ] Per-PR report: token count for both runs (with % reduction), latency for both runs, drift score (count + description of mismatches)
- [ ] Report contains no verbatim diff content or quoted PII/secret values — only aggregated metrics, finding categories, and PR references (number/URL/commit SHA)
- [ ] Report is committed at `meta/wenyan-handoff-validation-report.md` (top-level `meta/`, not `meta/plans/`) so it survives `close-iteration`'s plan cleanup
- [ ] Summary ship/no-ship verdict based on drift ~0, with token savings as the headline number

---

## Pre-Implementation Review

**Security:**
- Both source repos are public — the report must summarize/aggregate rather than reproduce PR diff content or finding snippets verbatim.
- Any PR selected for its "security-touching" characteristic must have its historical secret verified as rotated before inclusion, and any secret-like string surfaced during either run must be redacted in the final report, not reproduced even for illustration.
- Cross-repo access via `gh` is read-only and same-account — no new PAT/secret storage; confirm the measurement script never posts comments/labels back to the source repos.
- If the measurement script shells out with PR titles/branch names interpolated into commands, use argument arrays/proper quoting rather than string-built shell commands.

**Privacy:**
- `bible-flashcards` PR content may include real user/PII-adjacent data with different sensitivity assumptions than `claude-tools` — confirm before inclusion, and describe findings structurally (category, count, file:line) rather than quoting values.
- No DPIA needed for this internal tooling task, but the report should include one line noting which repos were sourced and confirming no third-party production user data was reproduced verbatim.

**Accessibility:** No WCAG-relevant surface (script + markdown report, no UI).

**Design:**
- Follow the `meta/sdlc-review-findings.md` structural convention (H1, context paragraph, `---`-delimited sections) rather than inventing a new report format.
- Place the report at top-level `meta/`, not `meta/plans/`, since `meta/plans/*` is deleted by `close-iteration` Step 6a before merge — placing the ship/no-ship record there would destroy it.
- Name the file consistently with existing precedent: `meta/wenyan-handoff-validation-report.md`.
- If `bible-flashcards` has its own recorded sdlc findings file, reference it by path/PR/commit rather than re-deriving findings independently.
