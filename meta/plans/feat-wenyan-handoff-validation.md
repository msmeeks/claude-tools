# Plan: wenyan-ultra offline validation suite (token/latency/drift)

**Issues:** #31

**Prerequisite:** complete and merge `feat/wenyan-handoff-rollout` (#30) first — this validation gates the full 8-agent rollout before it's treated as production-ready.

---

## Goal

Write a script that, when run by a human, produces a ship/no-ship recommendation for the wenyan-ultra handoff protocol — measured token savings, latency, and a drift/accuracy score comparing baseline (caveman-disabled) vs. wenyan-ultra-enabled sdlc review runs across 5 real past PRs.

---

## Context

Issues #28-#30 build the mechanism; this issue proves it's safe to rely on before it's the default behavior. The comparison runs the full sdlc review pipeline twice per selected PR — once at normal verbosity (temporarily disabling the global `/caveman` CLAUDE.md directive) as baseline, once with wenyan-ultra handoff enabled — and diffs the results. Tokens are the headline metric; drift (count of findings differing in file/line/substance) is the actual ship/no-ship gate; latency is informational only. Both `claude-tools` and the other candidate source repo, `bible-flashcards`, are **public** repositories, which materially constrains how the comparison report can be written.

**Scope of this plan: build the tool, don't run it.** This is a real-run experiment (~80 agent invocations: 5 PRs × 2 modes × 8 sub-reviewers) — expensive, slow, and it touches the user's global `~/.claude/CLAUDE.md` and a second repo. Five prior automated attempts correctly refused to execute this live inside an unattended loop session and stalled asking for authorization each time (see `progress.md` for the full trail). Rather than keep asking a non-interactive session to make that call, this plan's deliverable is changed: **write and test a standalone script that performs the full run when invoked, but do not invoke it as part of this plan.** The user will run it themselves, on their own schedule, with full visibility into cost and timing. This removes the live-authorization question from the agent's plate entirely — the human already approved the run's *design* (5-PR scope, `/caveman` disable, `bible-flashcards` cross-repo read access) in chat; what's left is ordinary tool-building work.

**Human confirmation on record (design, not execution):** full 5-PR scope, temporary `/caveman` disable during baseline passes, and read-only cross-repo `gh` access to `bible-flashcards` were all confirmed directly in chat on 2026-07-01 (see `progress.md`, `2026-07-01T21:20:00Z` entry). That confirmation covers what the *script* is allowed to do when the human later runs it — it is not authorization for this plan's own implementation session to execute the script.

---

## Implementation Notes

### Files to Modify / Create

| File | Change |
|------|--------|
| `scripts/wenyan_validation_run.py` (new) | The script itself: selects the PR corpus (or accepts one via `--prs`), runs baseline + wenyan-ultra passes per PR, computes drift, writes the report. Supports resuming a partially-completed run (see Steps below) since a real invocation may span hours. |
| `scripts/tests/test_wenyan_validation_run.py` (new) | Unit tests per `/tdd` — corpus selection logic, drift computation, redaction, resume/checkpoint logic. Mock all `gh`/`claude` subprocess calls; no test should make a real network call or invoke a real agent. |
| `meta/wenyan-handoff-validation-report.md` (new, written by the script at runtime — not by this plan) | The report format the script must produce: PR selection + rationale, per-PR token/latency/drift numbers, summary ship/no-ship verdict. **Not** under `meta/plans/` — that directory is deleted wholesale by `close-iteration` Step 6a before merge, which would silently destroy the ship/no-ship record. Follows the existing `meta/sdlc-review-findings.md` convention: H1 title, context paragraph, `---`-delimited sections. |

### Steps

1. **Write the script's PR-selection logic.** Given a `claude-tools`/`bible-flashcards` `gh` handle, select (or accept a user-supplied) 5-PR corpus, preferring PRs that already have recorded sdlc findings as drift ground truth, with at least one from `bible-flashcards`. Document rationale (size/type: small fix, medium feature, large refactor, security-touching, UI-touching) per PR in the script's output. For any security-touching PR with a known historical secret, the script must verify (or require the human to confirm) the credential was rotated before including it — never assume from memory.
2. **Write the baseline-pass runner.** Per PR: temporarily disables the global `/caveman` CLAUDE.md directive for the duration of the pass (and reliably restores it afterward, including on error/interrupt — use a try/finally or equivalent, this must never leave the user's global config in a modified state), runs the full sdlc review pipeline, captures total token count (input+output across the 8 agents) and wall-clock latency.
3. **Write the wenyan-ultra-pass runner.** Same pipeline with the merged `feat/wenyan-handoff-rollout` handoff enabled, capturing the same metrics.
4. **Write the drift computation.** Per PR: count and describe findings that differ in file/line/substance between the two runs. Ship/no-ship bar (per the human decision recorded on issue #33): **drift must be 0 substantive mismatches per PR, independently for each of the 5 PRs** — not averaged across the corpus.
5. **Write the checkpoint/resume logic.** The script must be interruptible and resumable: persist per-PR/per-mode completion state and captured metrics to a local file (e.g. under `meta/plans/implementation-logs/`, scratch/transient — nothing sensitive committed there), and on restart, continue from the checkpoint rather than re-running completed passes. The checkpoint file itself must follow the same aggregate-only/no-verbatim/redact-secrets rule as the final report (see Acceptance Criteria) — it may hold real PII/secret-adjacent content transiently on disk across a multi-hour run otherwise.
6. **Write the report generator.** Emits `meta/wenyan-handoff-validation-report.md`, referencing each PR by number/URL/commit SHA — never quoting raw diff hunks or verbatim finding text pulled from the reviewed source. Summarizes findings by category/count only. Any secret-like string surfaced during either run is redacted (`REDACTED`) rather than reproduced. Verdict logic: ship if drift is 0 on all 5 PRs independently, no-ship otherwise (report still generated either way, describing which PR(s) failed and why).
7. **Test the script end-to-end against mocked subprocess calls** (per `/tdd`) — no real `claude`/`gh` invocation as part of this plan's own execution. Include at least one test proving the `/caveman` directive is restored even when a simulated pass raises partway through.
8. **Document invocation.** Add a short usage note (in the script's own `--help`/docstring, and a line in `docs/features/` if one exists for this area) covering: expected runtime, that it touches the user's global CLAUDE.md temporarily, that it requires `gh` auth against both repos, and how to resume an interrupted run.

---

## Acceptance Criteria

- [ ] `scripts/wenyan_validation_run.py` exists, is executable standalone (`python3 scripts/wenyan_validation_run.py [--prs ...] [--resume]`), and is not invoked by this plan's own implementation
- [ ] PR-selection logic documents rationale (size/type, prior recorded findings) for each selected PR; supports requiring at least one `bible-flashcards` PR
- [ ] Baseline pass reliably disables and restores the global `/caveman` directive, including on error
- [ ] Drift computation implements the per-PR (not corpus-averaged) 0-mismatch bar from issue #33
- [ ] Checkpoint/resume logic persists progress and continues from it rather than restarting the corpus; checkpoint file follows the same redaction rule as the final report
- [ ] Report generator produces no verbatim diff content or quoted PII/secret values — only aggregated metrics, finding categories, and PR references (number/URL/commit SHA)
- [ ] Report is written to top-level `meta/` (not `meta/plans/`) so it survives `close-iteration`'s plan cleanup
- [ ] `scripts/tests/test_wenyan_validation_run.py` covers corpus selection, drift computation, redaction, resume logic, and `/caveman` restore-on-error, all against mocked subprocess calls
- [ ] `python3 -m ruff check` clean on both new files

---

## Pre-Implementation Review

**Security:**
- Both source repos are public — the report/checkpoint generation logic must summarize/aggregate rather than reproduce PR diff content or finding snippets verbatim.
- Any PR selected for its "security-touching" characteristic must have its historical secret verified as rotated before inclusion, and any secret-like string surfaced during either run must be redacted in the final report, not reproduced even for illustration.
- Cross-repo access via `gh` must be read-only and same-account — no new PAT/secret storage; the script must never post comments/labels back to the source repos.
- The script must never shell out with PR titles/branch names interpolated into raw command strings — use argument arrays/proper quoting.
- The script itself must not execute during this plan's implementation — verify no test or setup step invokes it against a real repo.

**Privacy:**
- `bible-flashcards` PR content may include real user/PII-adjacent data with different sensitivity assumptions than `claude-tools` — the script should confirm/flag before including such a PR, and describe findings structurally (category, count, file:line) rather than quoting values.
- No DPIA needed for this internal tooling task, but the generated report should include one line noting which repos were sourced and confirming no third-party production user data was reproduced verbatim.
- The checkpoint file (transient, local) must not become a durable unredacted store of PII/secret-adjacent content — same redaction rule as the final report.

**Accessibility:** No WCAG-relevant surface (script + markdown report, no UI).

**Design:**
- Follow the `meta/sdlc-review-findings.md` structural convention (H1, context paragraph, `---`-delimited sections) for the report the script generates, rather than inventing a new report format.
- Report path is top-level `meta/`, not `meta/plans/`, since `meta/plans/*` is deleted by `close-iteration` Step 6a before merge.
- Name the file consistently with existing precedent: `meta/wenyan-handoff-validation-report.md`.
- If `bible-flashcards` has its own recorded sdlc findings file, the script should reference it by path/PR/commit rather than re-deriving findings independently.
