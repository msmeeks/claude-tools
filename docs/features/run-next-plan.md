# Run Next Plan (Ralph Wiggum loop)

## Summary

`scripts/run-next-plan.py` is a non-interactive orchestrator that drives an iteration's
`<config-root>/plans/` to completion, where `<config-root>` is `docs/agents/` in the
scaffolding layout or `meta/` in un-migrated repos (resolved once per run, near the top of
`main()`, by `resolve_config_root`, then threaded down as a parameter to every function that
needs it — no other call site re-resolves it; see
[ADR 0001](../adr/0001-scaffolding-layout-with-dual-read-fallback.md)). It repeatedly invokes a headless Claude session, letting Claude pick and implement the highest-priority unblocked plan, until every plan is `done`/`stalled` and a final SDLC review gate has passed. It's the "run" partner to `/plan-iteration`'s "plan" step.

## Users / Use Cases

- **Developer** — kicks off `python3 ~/.claude/scripts/run-next-plan.py` after `/plan-iteration` has written `<config-root>/plans/prd.json`, then lets it run unattended (optionally overnight) through an entire iteration's plans.
- **Worker** — N/A (this script is itself the automation; there is no separate worker role).

## Technologies

- **Python 3 stdlib only** (`argparse`, `fcntl`, `json`, `subprocess`, `re`, `tempfile`, `pathlib`) — no third-party dependencies, matches the repo's minimal-dependency preference
- **`claude` CLI** — invoked headlessly via `claude -p - --permission-mode bypassPermissions --output-format text`, prompt piped over stdin
- **`gh` CLI** — used to file SDLC finding issues and sync `Closes #N` entries on the integration branch's PR
- **`fcntl` file locking** — guards concurrent writes to `prd.json` across attempt-increment/status-set operations

## Technical Overview

The script treats `<config-root>/plans/prd.json` as the single source of truth for plan state (`pending`/`in-progress`/`done`/`stalled`, `attempts`, `blocked_by`) and delegates all prioritization and implementation intelligence to Claude via a constructed prompt — the Python layer only does bookkeeping: selecting *some* eligible (non-terminal) plan as a starting point, incrementing attempt counters, detecting stalls, retrying through rate limits, and escalating model/effort on repeated failures. Once every plan reaches a terminal state, the script gates on an `sdlc_review_status` field in `prd.json` before declaring the iteration truly finished, running a full `/sdlc` review, filing findings as GitHub issues, and triaging them into new plans (which re-enters the loop) or halting for human input.

## Key Files

| File | Purpose |
|---|---|
| `scripts/run-next-plan.py` | The orchestrator itself |
| `<config-root>/plans/prd.json` | Plan registry: `integration_branch`, `pr_number`, `prd_issue`, `plans[]` (file/status/attempts/blocked_by), `sdlc_review_status`, `sdlc_review_rounds` (completed review rounds; capped by `MAX_REVIEW_ROUNDS`), `last_reviewed_sha`, `sdlc_finding_issues` (iteration-cumulative), `sdlc_deferred_issues` (filed but not fixed by this PR: final-round findings and minor rollups; never in `Closes`), `sdlc_round_filed_issues` (per-round scratch), `sdlc_review_completed_agents`, `feature_branches`, `smoke_test` |
| `<config-root>/plans/progress.md` | Human-readable log Claude appends to after each completed plan |
| `<config-root>/sdlc-review-findings.md` | Per-round scratch file the review phase writes findings into before they're filed as issues; rotated at the start of each fresh round |
| `<config-root>/pr-summary.md` | The two-audience PR summary `_generate_pr_summary` writes, spliced into the PR body by `update_pr_description` |
| `<config-root>/plans/implementation-logs/run-next-plan-*.log` | Per-invocation log; scrubs credentials before writing. `_ensure_artifacts_gitignored` ignores (and untracks) this directory, plus `prd.json.lock`, `sdlc-review-findings.md`, and `pr-summary.md`, via the target repo's `.git/info/exclude` at startup |
| `<config-root>/plans/implementation-logs/run-next-plan-*-triage.log` | Per-issue triage outcome log written by the SDLC review gate |
| `scripts/tests/test_orchestration.py`, `test_prd_data_layer.py`, `test_sdlc_gate.py`, `test_pr_description.py`, `test_config_root.py`, `test_ralph_config.py`, `test_review_recipes.py` | Test suite; run via `cd scripts && python3 -m pytest`. `test_orchestration.py` covers `_working_tree_dirty`, `_push_branch`, `ensure_committed`, `flush_push`, `exit_flush`, and `_ensure_artifacts_gitignored` against real throwaway git repos (with a bare "remote"), not mocks. `test_config_root.py` covers `resolve_config_root` layout resolution under both `docs/agents/` and `meta/`, including the dual-layout refusal, the symlink/escape refusals, and an end-to-end `main()` run under each layout. |
| `<config-root>/ralph.json` | Optional per-repo review config (see **Review recipe config**); absent means today's behaviour |
| `skills/close-iteration/skill.md` | Step 2b reads this script's `sdlc_review_status` values (`pending`/`complete`) from `prd.json` as a hard-blocker check before promoting/merging the iteration |

## Technical Detail

### Plan loop and attempt tracking

Each pass through the `while True:` loop re-reads `prd.json`, selects a non-terminal plan (`select_next_plan` only screens out fully-`done`/`stalled` plans and fully-circular `blocked_by` graphs — actual priority/dependency judgment is left to Claude, which is instructed to respect `blocked_by` unless it can verify a dependency is already satisfied by reading the plan files), and invokes Claude with a fixed prompt. Plan file content is explicitly framed as untrusted document text in every prompt, not as instructions to follow.

**Attempt accounting is deferred until *after* the session** (`account_attempt`), so it reflects only sessions that actually ran and worked on a given plan:

- **Attribution, not guesswork.** `select_next_plan` returns `eligible[0]`, but the prompt tells Claude to pick the *highest-priority* plan — which may differ — so the runner's guess isn't charged. After the session, `_attribute_worked_plan` charges the plan that demonstrably advanced: the one plan that flipped to `done` this run (primary signal), or, failing that, the plan named in a session-declared `<plan>slug.md</plan>` sigil. The sigil value is untrusted (Claude runs with `bypassPermissions` and can echo injected text) and is only honored when it names a plan in the current eligible set; an unknown/ineligible name is ignored with a warning. If neither signal is present, **nothing** is charged — never `eligible[0]` by default.
- **Rate limits don't burn attempts.** A `rate_limit` outcome did zero work, so `account_attempt` charges nothing — mirroring the loop's treatment of limits as non-failures. Only genuine (non-limit) sessions increment `attempts` (under an `fcntl` lock).

### Stall detection and model escalation

`MAX_ATTEMPTS = 5`. A plan whose charged `attempts` exceeds 5 without reaching `done` is marked `stalled` (`mark_stalled`) and skipped from then on. Because stalls key off the deferred, attributed counter, `mark_stalled` can only fire for a plan a session demonstrably worked on — never for one that merely absorbed a guessed or rate-limit increment. Model/effort escalates by the attempt number of the run about to start (`selected["attempts"] + 1`, since this run's increment hasn't happened yet):

| Attempt about to run | Claude invocation |
|---|---|
| 1–2 | default model/effort |
| 3–4 (`ESCALATION_THRESHOLD = 3`) | `--model sonnet --effort high` |
| 5+ (`MAX_ATTEMPTS`) | `--model opus --effort max` |

### Rate-limit retries

`invoke_claude` returns both the combined stdout/stderr and the CLI's exit code, and `scan_output(text, exit_code)` classifies the result as `complete` (COMPLETE sigil found), `rate_limit`, `error`, or `ok`. Limit detection requires **two** independent signals, because either one alone produces false positives:

1. **A non-zero exit code.** A genuine session/usage limit terminates the `claude` CLI non-zero; a clean exit-0 run never is one. So limit-shaped text on a successful run is Claude *quoting* or discussing a limit — for example a reviewer flagging code as "not rate-limit-aware", or this file's own limit-handling code being read back during review — and is classified `ok`. This gate is what stops those incidental mentions from triggering a spurious wait.
2. **A `RATE_LIMIT_RE` match**, which narrows the non-zero exits that are limits (vs. ordinary errors). It matches only genuine limit *announcements*: a limit noun paired with "reached"/"exceeded", an explicit "resets H(:MM)(am/pm)" / "limit will reset" directive, `429 too many requests`, `overloaded_error`, or `retry-after`. It deliberately does **not** match bare tokens like "rate limit", "usage limit", "429", or "too many requests" on their own.

A non-zero exit *without* a regex match is a plain `error`. The real CLI message this is built against is `You've hit your session limit · resets 8:50pm (America/New_York)`, pinned as a regression test in `test_orchestration.py`.

On `rate_limit`, the script parses a retry delay from the output text via `_parse_retry_after_text`: an explicit "retry after N" / "try again in N", or a "resets [at] H[:MM]am/pm" time interpreted in America/New_York (minutes are optional — an on-the-hour "resets 9pm" parses to a real wait rather than falling through to the default and re-looping tightly until the limit clears). It falls back to `RETRY_WAIT_DEFAULT = 60`s, adds a flat 60s buffer, sleeps, and retries the same attempt — up to `MAX_RETRIES = 20` times before giving up and leaving the plan `in-progress` for a future run to resume.

### Run-log hygiene

The runner writes its live log to `<config-root>/plans/implementation-logs/` *inside the target repo*, and its prompts tell Claude that directory is gitignored. `_ensure_artifacts_gitignored(repo_root)` runs at startup (before the log file is opened) to make that assumption true rather than merely asserted — it also covers `prd.json.lock`, `sdlc-review-findings.md`, and `pr-summary.md`, which have no other backstop against being committed:

1. If `git check-ignore` says the directory isn't ignored, appends the missing artifact paths (with a comment) to the repo's `.git/info/exclude` (resolved with `git rev-parse --git-path`, so linked worktrees work), creating it if absent and preserving existing rules. It deliberately does **not** edit the tracked `.gitignore`: that edit would be swept into the first work commit and appear in the diff the SDLC reviewers see.
2. If `git ls-files` shows logs the repo already committed, runs `git rm -r --cached` on them — files stay on disk (one is being written to right now), they just stop being tracked.

Both steps are no-ops on an already-healthy repo, so a steady-state run prints nothing. The exclude edit is local and untracked, so it never shows up in a commit; staged untrackings of previously committed logs are left uncommitted and the first `ensure_committed` of the run sweeps them into a real commit.

### Commit/push enforcement

Committing and publishing are separate concerns, deliberately. **Claude is never told to push** — every prompt (plan implementation, the commit-remediation prompt, the docs phase, the planning phase) says "commit" and then says "Do not push" explicitly. The instruction is explicit rather than merely absent because plan and issue text is untrusted: silence would leave room for an injected "…and push your work" to reintroduce exactly the behavior this split removes.

`ensure_committed(repo_root, integration_branch, context)` runs after each phase and guarantees nothing is lost:

1. Checks `git status --porcelain -- . ':(exclude)<config-root>/plans/implementation-logs/'`. If clean, it does nothing. The exclusion (`_WORK_PATHSPEC`) matters: the script's own live log lives inside the repo and is appended to *during* these checks — including by `invoke_claude` itself, which writes Claude's transcript to the log after Claude has committed. Without it, a repo that tracks `<config-root>/plans/implementation-logs/` reports dirty on every check, step 2 can never be satisfied, and every plan produces a spurious Claude invocation plus a `wip:` commit containing nothing but log lines.
2. If dirty, invokes Claude once more with a narrow "commit these outstanding changes, do not push" prompt. If the tree is still dirty afterward, auto-commits the same pathspec with a generic `wip: uncommitted changes from <context>` message as a safety net — this never blocks the loop, but does mean an occasional low-quality commit message can show up if Claude didn't commit its own work.

**Commit references.** Every commit the runner makes carries an issue reference so `/close-iteration` Step 3 finds nothing untraceable. The format comes from the first non-empty line under `## Commit references` in `<config-root>/issue-tracker.md` (one `{n}` placeholder), default `Refs #{n}`; a missing file or section is the normal case and silent. The line is validated against a whitelist (`[A-Za-z0-9 #:.,_-]` plus one `{n}`, at most 40 characters, read from the first 64 KB); an invalid template warns once with the path and a reason category (`no {n}`, `multiple {n}`, `too long`, `disallowed characters`), never the content, and falls back to the default. The template is rendered once per issue (`Refs #7, Refs #8`) with `.replace`, never `.format`. Refs come only from `_coerce_refs`: genuine positive ints (no bools or strs), deduped, capped at 20. Plan implementation commits use the chosen plan's `issues`; the docs phase and SDLC review commits use the integration PR number. `exit_flush` is the exception: its wip message carries no ref because resolving one means reading prd.json, which it must never do.

`flush_push(repo_root, integration_branch)` is the only thing that publishes. `_push_branch` sets upstream via `git push -u origin <branch>` if none exists, otherwise pushes only when the local branch is ahead of `@{u}`, and on failure *warns* (scrubbed through `_scrub_credentials`, since git's stderr can echo the credential-helper URL) rather than raising.

**Why the split.** `ensure_committed_and_pushed` used to do both, at three points per plan plus once per review-gate retry. One real iteration produced 55 script-issued pushes, each firing at least two GitHub Actions workflows — enough to exhaust the account's monthly Actions minutes. Pushes are now placed deliberately:

| Where | Pushes |
|---|---|
| After each plan iteration (`main`) | 1 |
| End of a completed review-gate round, after the docs phase | 1 |
| Process exit (`exit_flush`, registered via `atexit`) | 1, usually a no-op |

The gate's terminal push sits *after* `run_docs_phase` rather than before it, and is preceded by one more `ensure_committed` — `update_pr_description` writes `<config-root>/pr-summary.md` after the docs-phase commit has already run, so without that sweep the file was never committed at all.

**Exit-path coverage.** `main` registers `exit_flush` once, via `atexit`, immediately after resolving the integration branch. One registration covers every termination path — normal completion, the `incomplete`-gate resume exit, the session-limit give-up, the error exit, `KeyboardInterrupt`, and `die()` — rather than sprinkling `flush_push` across ten `sys.exit` sites. `exit_flush` is deliberately narrow:

- **git side effects only.** It never reads or writes `prd.json` and never takes the prd lock: it can fire while `_with_prd_lock` holds the flock, which would deadlock a single-threaded process.
- **Commits through `_WORK_PATHSPEC`**, like every other commit path, so an interrupt can't sweep the run log into pushed history.
- **Never invokes Claude**, and **swallows every exception** — an exit path is the worst possible place to raise.
- **Never registered under `--dry-run`**, which pushes nothing at all.

### Redundant-sync suppression

`sync_pr_closes` is called from four points per loop pass, and each call used to issue a `gh pr view` + `gh pr edit` round trip. It now caches the closed-issue set it last wrote (`_synced_closes`) and returns immediately when the current set is a subset of it, so the PR body is written at most once per genuinely new completion.

### Trust model: no sandbox

There is none. The loop runs `claude --permission-mode bypassPermissions` **directly on the host**, with the invoking user's filesystem access, git credentials, and `gh` token. An earlier optional Docker mode (`meta/ralph.dockerfile`) was removed: no repo ever adopted it, and it was weak protection anyway — a read-write bind-mount of the repo (including `.git/hooks/`) with secrets passed through as environment variables.

The only thing between an attacker-controlled plan or issue body and arbitrary code execution is prompt framing: every prompt the runner constructs marks plan and issue content as untrusted document text rather than instructions. That is a mitigation, not a boundary. Run this only against repositories whose issue tracker you trust. See `docs/agents/PRIVACY.md` (`meta/PRIVACY.md` in un-migrated repos) for the full residual-risk discussion.

Two defense-in-depth backstops, neither a boundary in itself: a one-time warning (`warn`, so it's stderr and the run log) is printed at the start of every non-`--dry-run` invocation, restating the no-sandbox trust model so it isn't something an operator only learns from documentation they may not have read; and the PR-description body Python builds and passes to `gh pr edit` — both in `update_pr_description` and `sync_pr_closes` — is run through `_scrub_credentials` immediately before that call, matching the scrub already applied to run logs and push-failure stderr. The `gh issue create` call in the file-issues phase has no equivalent interception point (the Claude session invokes it directly as its own tool call, not Python), so it stays out of scope; that path is covered instead by the paraphrase-only, redaction-instructed issue-filing prompt.

### SDLC review gate

Once `select_next_plan` finds no eligible plans (or Claude emits the `<promise>COMPLETE</promise>` sigil and `prd.json` confirms all plans are terminal), the script checks `prd.json`'s `sdlc_review_status`:

- **`pending`** (default, and the only non-terminal value): runs `run_sdlc_review_gate`, which works through three phases inside a retry loop (`attempt` 1…`MAX_REVIEW_ATTEMPTS`):
  At each **fresh round's** start (no reviewer recorded complete yet) the gate rotates away any stale `<config-root>/sdlc-review-findings.md` via `_rotate_findings_file` — a path-safe unlink (refuses symlinks, confirms the resolved path stays under the repo root) — so a prior round's leftover findings can't be re-filed as duplicate issues. Rotation is once-per-round, never per-attempt, so a within-round resume after a session-limit give-up keeps the findings its completed reviewers already appended.
  1. **Review** — generates findings into `<config-root>/sdlc-review-findings.md` (`## <title>` + body blocks, no GitHub issues yet) by dispatching the seven `/sdlc` Phase-3 review agents (`SDLC_REVIEW_AGENTS`) over an **incremental** git range (`_compute_review_range`): `<last_reviewed_sha>..HEAD` when a review baseline is recorded (only the commits added since the last completed review), falling back to the whole PR `<default_branch>...HEAD` on the first-ever review (no baseline). For the first `REVIEW_PARALLEL_ATTEMPTS` (2) attempts the outstanding reviewers are dispatched **in parallel** (one Claude call, all-or-nothing); on later attempts they run **one at a time**, and each finished reviewer is appended to `sdlc_review_completed_agents` so a retry resumes only the remaining ones. The phase is skipped entirely once all seven agents are recorded complete.
  2. **File issues** — first checks open `sdlc-finding` issues and skips any finding one already covers (printed as `DUPLICATE: #N`) — except issues this PR claims to fix (done plans' **Issues:** lines plus `sdlc_finding_issues`, via the same `done_plan_issue_numbers` helper `sync_pr_closes` uses): those stay open until merge, so a finding that one is still broken is filed, not deduped, or the PR would close an unfixed issue. Each remaining finding at Blocker/Critical/High/Major/Medium is filed as its own GitHub issue via `gh issue create`, labeled at filing — `sdlc-finding`, a category (`bug`/`enhancement`) and a state (`ready-for-agent`, `ready-for-human`, or `needs-info`) — with an agent-brief body, and cosmetic churn is never filed on its own; it prints each new issue number as `ISSUE: #N`. Everything lower (Minor/Low/Nit/Informational) goes into a single checklist **rollup issue**, printed as `MINOR_ROLLUP: #N` — deliberately not an `ISSUE:` line, so it is never planned or claimed in the PR's `Closes` block; a human schedules it. Why: one issue per finding at every severity filed 100 issues across a two-round iteration, mostly nits, and each nit fixed in round 1 was new code for round 2 to nitpick. This round's numbers are written to the per-round scratch field `sdlc_round_filed_issues` **and** appended (deduped) to the iteration-cumulative `sdlc_finding_issues`, immediately, so a later interruption resumes planning against them instead of re-filing (which would duplicate). The "already filed this round" guard reads `sdlc_round_filed_issues` — **not** the cumulative list — so a re-armed round with prior findings still files its own issues exactly once, while a within-round resume skips re-filing. Planning runs against this round's `sdlc_round_filed_issues` only, and is skipped entirely when that list is empty (every finding was minor or a duplicate).
  3. **Plan** (`_run_triage_phase`) — nothing re-triages the filed issues: `/triage` is user-invoked and refused in a headless session, which is why filing labels them. The session reads each issue's labels and comments, acts on the state it already carries without relabeling, and clusters every `ready-for-agent` issue (à la `/plan-iteration` Step 5) into new `<config-root>/plans/<slug>.md` plan files appended to `prd.json`, without opening a new integration branch or PR. Afterwards the runner reads each filed issue's labels itself (`_unlabeled_issues`, via `gh issue view`) and, for any with no state label, prints a `WARN:` naming them and the `/triage #N …` command to run — the non-interactive way of handing them back to the user. An issue whose labels can't be read is skipped rather than flagged.

  The triage prompt spells out the exact entry shape (`"status": "pending"`, `"attempts": 0`, `blocked_by` list). As a backstop, `_fill_new_plan_defaults` runs after triage, under the prd lock and in a `finally` so it also runs when triage hits a session limit. It fills a missing or null `status`/`attempts`/`blocked_by` on plans triage *appended*, with a `WARN`. Without it, a null status made the next `load_prd` die between triage and the `complete` latch, so the round couldn't finish and would re-triage on resume (#66). Entries that existed before triage are left alone, so corrupting one still fails loudly.

  The triage step logs one line per issue to `<config-root>/plans/implementation-logs/run-next-plan-*-triage.log` and finishes by printing `TRIAGE_DONE`.

  On a clean finish, `sdlc_review_status` is set to **`complete`**. The same terminal write also records `last_reviewed_sha = HEAD` (the reviewed commit, captured after the triage push) and clears the per-round scratch (`sdlc_review_completed_agents`, `sdlc_round_filed_issues`) so the next round starts fresh. `sdlc_finding_issues` is **not** cleared — it stays cumulative across every round of the iteration so `/close-iteration`'s `Closes` block and "findings addressed" gate see the whole set. See **Incremental (per-round) review** below.

  `save_prd` guards `sdlc_review_status` against reverting from `complete` back to `pending`, with exactly one carve-out: a `complete` status that carries a `last_reviewed_sha` may be re-armed to `pending` (the intentional new-round transition). A baseline-less `complete` stays latched — preserving the original protection against an accidental blank reset that would otherwise re-run the whole gate.

- **Incremental (per-round) review.** After the first round completes, appending new `pending` plans (PR-comment fixes, or newly-planned finding issues folded into the same PR) must not slip past review. On the next loop pass, when eligible plans exist but `sdlc_review_status == "complete"`, `main` calls `_rearm_sdlc_review_gate`: it flips the latch back to `pending` (permitted by the carve-out above) and clears the per-round scratch (`sdlc_review_completed_agents`, `sdlc_round_filed_issues`), keeping both `last_reviewed_sha` (the boundary) and the cumulative `sdlc_finding_issues` (the iteration record). Once those plans finish, the gate runs again but reviews only `last_reviewed_sha..HEAD` — the new commits — instead of re-scanning (and re-filing findings on) the whole PR. It then advances `last_reviewed_sha` to the new HEAD for the round after. Bookkeeping is cleared at the *end* of each round (rather than only on re-arm), so a round resumed by hand — by editing `sdlc_review_status` back to `pending`, which bypasses `save_prd` — also starts clean. If a re-armed round turns out to have no new commits (`last_reviewed_sha == HEAD`, e.g. the appended plan stalled without committing), the gate no-ops: it marks `complete` immediately without invoking any reviewer. A stale baseline no longer reachable in the repo (after a rebase/force-push) falls back to the whole-PR range. The **docs phase and PR-summary generation deliberately stay whole-iteration** (`<default_branch>...HEAD`), since docs should reflect the entire iteration, not just the latest increment.

  **Round cap.** Re-arming is bounded. Each completed round increments `sdlc_review_rounds` (under the same lock that latches `complete`; the empty-increment no-op reviewed nothing and does not count), and `_rearm_sdlc_review_gate` returns `False` without touching `prd.json` once the count reaches `MAX_REVIEW_ROUNDS` (2, overridable via the `RALPH_MAX_REVIEW_ROUNDS` env var). Review findings beget plans beget commits beget findings; unbounded, the chain stops by session limit rather than by convergence — one real iteration re-armed 8 times and walked 185 finding issues before dying. At the cap the gate stays latched `complete` (it is never written back to `pending`, which would also trip `save_prd`'s revert guard), `main` latches a local `rearm_suppressed` flag so the policy-stop line is logged once, the remaining plans still run, and the loop terminates through the normal all-terminal exit.

  **Final-round deferral.** The round that will hit the cap is flagged `final_round`, which changes two things. The planning prompt swaps its "cluster into plan files" instructions for explicit "do NOT write plan files, do NOT add prd.json entries" — findings are filed with their labels, then left for a human. And `_run_file_issues_phase` writes that round's issue numbers to the per-round scratch (so the re-file guard still works on a session-limit resume) but *not* to `sdlc_finding_issues`; they go to `sdlc_deferred_issues` instead (as does every round's `MINOR_ROLLUP` number, via `parse_minor_rollup` — last match wins, `0` rejected), and the cap message lists that key — `/close-iteration` turns that list into the PR's `Closes` block, and a PR must not claim to close findings it never fixed (#47/#44). Deferred findings persist as open issues; `docs/agents/PRIVACY.md` (`meta/PRIVACY.md` in un-migrated repos) covers their retention.

  **Session-limit resilience.** Every gate Claude call goes through `_gate_invoke`, which raises `ReviewInterrupted` when the invocation both exits non-zero and matches `RATE_LIMIT_RE` — the same two-signal discriminator `scan_output` uses, and for the same reason: review output routinely *discusses* rate limits, and an exit-0 reviewer that merely quoted limit text must not be mistaken for a real limit hit. A reviewer discussing limits therefore never triggers a spurious wait. Instead — exactly like the main plan loop — the gate parses the reset delay from the output (`_parse_retry_after_text` + 60s buffer), `time.sleep`s until it clears, and retries; the retry escalates the reviewer dispatch parallel→serial per the `attempt` counter (mirroring the per-plan model escalation). Each attempt commits any progress first (`sdlc_review_completed_agents`, `sdlc_finding_issues`), so nothing is lost. Only if the limit persists across all `MAX_REVIEW_ATTEMPTS` (5) attempts does the gate give up, returning `"incomplete"` (status left non-terminal); `_run_gate_and_continue` then exits 0 so a later re-run resumes from the persisted progress.

- **`complete`**: the docs phase runs (`run_docs_phase`: `/sdlc-doc-writer` scoped to the iteration's changed files, then `/help-docs` and `/demo` for new/changed features, committed to the integration branch), then `update_pr_description` writes the final PR summary (see below), then the script exits 0 — the iteration is genuinely finished.


If new plans were created by the triage step, the loop simply `continue`s and picks them up like any other pending plan on the next pass.

### Review recipe config (`ralph.json`)

Optional `<config-root>/ralph.json`, same trust level as `prd.json` (plain schema validation).
`load_ralph_config` runs once in `main()`, before any Claude call, and a malformed file dies
with a message naming the field (or, for unparseable JSON, the file). A missing file or key means today's defaults, and with no
file the `agents` recipe's prompts are byte-identical to before (regression-tested).

```json
{
  "review": {
    "recipe": "skill",
    "skill": "<skill-name>",
    "reviewers": ["sdlc-security-reviewer", "sdlc-code-reviewer", "spec"],
    "registry": true
  },
  "plan_review": { "reviewers": ["sdlc-security-reviewer", "sdlc-privacy-reviewer"] }
}
```

| Key | Rule |
|---|---|
| `review.recipe` | `agents` (default) or `skill` |
| `review.skill` | Required and non-empty iff `recipe` is `skill`; rejected otherwise |
| `review.reviewers` | Non-empty, duplicate-free list of ids matching `^[a-z0-9][a-z0-9-]*$`; default is the seven `sdlc-*` agents |
| `review.registry` | Bool, default `false`; passed to the skill as `--registry yes\|no` |
| `plan_review.reviewers` | Same list rules; default the four plan-review agents. Read by `/plan-iteration` and `/triage-pr-comments`, not by this script |

Unknown top-level keys warn and are ignored; unknown keys inside `review`/`plan_review` are silently ignored.

**`agents` recipe.** The original dispatch, over the configured roster instead of the fixed
`SDLC_REVIEW_AGENTS`.

**`skill` recipe.** The review phase calls `/<skill> --range R --only <ids> --report-only --out <findings> --registry yes|no [--spec <issue numbers>]` against a skill that follows the headless review contract ([#69](https://github.com/msmeeks/claude-tools/issues/69) defines it; this doc does not restate it). `--spec` is the PRD issue plus the done plans' issue numbers, integers only; it is omitted when there are none. Python still owns escalation and resume:

- Parallel attempts make one call with every outstanding id; serial attempts one call per id.
- A reviewer is recorded complete **only** from a `<reviewed>id</reviewed>` line on its own line. Ids outside the roster are ignored with a warning.
- If a parallel call omits some ids, the gate runs the unreported ones singly in the same attempt; one that still does not report fails the gate loudly, naming it. Nothing is marked complete on trust.
- A line starting `UNSUPPORTED:` in the output dies with a message pointing at the skill version.
- A parallel call cut off by a session limit with no reviewer yet complete rotates the findings file before the retry (the retry would otherwise append partial duplicates). If any reviewer is already complete the file is kept; the file-issues phase merges same-problem findings.

`/close-iteration` is unaffected: it reads `sdlc_review_status` and the findings file, both recipe-agnostic. Rationale: [ADR 0002](../adr/0002-review-recipe-is-repo-config.md).

### `/close-iteration` integration

`/close-iteration` also reconciles review findings against open `sdlc-finding` issues and `sdlc_deferred_issues` before filing anything, and lists still-open deferred issues under "Issues left open". Its Step 2b hard-blocker check reads `prd.json`'s `sdlc_review_status` directly to decide whether an iteration is eligible to promote/merge: `pending` blocks the merge; only `complete` clears this check.

### Finished-iteration guard

`_iteration_finished(data, integration_branch)` returns a reason when the iteration is over: the integration PR (`pr_number`, else a lookup by branch) is `MERGED` with a matching `headRefName`, or `git ls-remote --exit-code --heads origin refs/heads/<branch>` exits 2 (branch gone). Lookup failures warn and return `None`, so offline runs proceed. `main()` calls it after resolving the integration branch and *before* `_register_exit_flush` (the atexit push would otherwise recreate a deleted branch), and dies with `prd.json at <path> belongs to a finished iteration (<reason>); run /plan-iteration to start a new one`. It also covers `--dry-run`. `/plan-iteration` Step 1.2 applies the same rule: a finished `prd.json` is moved to `prd.json.<date>.bak` and a fresh one written (no `sdlc_*` keys, `last_reviewed_sha` or `pr_number`); an open iteration is merged into as before, even when every plan is `done` and review is `complete`.

`/close-iteration` Step 4 uses `git rm -r --ignore-unmatch` and commits only if something was staged. Plans that were never tracked are archived, not deleted, to `<config-root>/plans/archive/<branch-slug>/` (kept out of git via `info/exclude`), and the report says `archived to <path>`.

### CLI options

| Flag | Effect |
|---|---|
| `--restart` | Resets any `in-progress` plan(s) back to `pending` before selecting |
| `--skip-in-progress` | Treats `in-progress` plan(s) as `pending` for selection purposes only (local view, not persisted) |
| `--dry-run` | Prints the selected plan, `blocked_by` graph, attempts, and full Claude command/prompt without invoking Claude, writing logs, or pushing anything |
| `--integration-branch BRANCH` | Overrides `prd.json`'s `integration_branch` (which is otherwise authoritative) |

### PR `Closes #N` sync

After every plan-selection pass (success, stall, or gate completion), `sync_pr_closes` scans `done` plans' `**Issues:**` lines for issue numbers and appends any missing `Closes #N` entries to the integration branch's open PR body via `gh pr edit`, so the PR always reflects which issues its merged plans close.

Any PR lookup goes through `resolve_pr_number(data, integration_branch)`: it prefers `prd.json`'s captured `pr_number` (written by `/plan-iteration` when it opens the draft PR) and falls back to a `gh pr list --head <branch>` lookup, returning `None` if there is no open PR. Both `sync_pr_closes` and the PR-description phase use it.

### Two-audience PR description

At the tail of `run_docs_phase` (once the iteration is genuinely complete), `update_pr_description` generates a PR summary aimed at two audiences and splices it into the PR body:

- `_generate_pr_summary` prompts Claude to write the summary to `<config-root>/pr-summary.md`, grounded in the changed-file list, `progress.md`, and the closed-issue titles (full diff as backup). Each change is classified **user-facing** (observable product/UI/CLI/API/customer-doc behavior) or **backend/engineering** (everything else).
  - **For the Product Manager**: the spec it implements (linked from `prd_issue`, or "No PRD issue linked" when absent), a brief overview, a bulleted list of user-facing changes, and a `- [ ]` GitHub-checklist test plan for those changes.
  - **For the Engineer**: the same shape for non-customer-facing/backend changes. Its test plan is deliberately *not* a re-run of the automated suite or CI — the prompt forbids "run pytest/ruff/lint", "check CI", and coverage items — and instead steers Claude to manual-reviewer verification: edge cases hard to exercise via UI/API (concurrency/locking, partial-failure and retry paths, boundary inputs), integration seams where a contract could drift, and architectural/schema/migration changes worth a design-level read, each naming the specific risk and where to look.
  - An audience with no changes gets an explicit "No … changes in this iteration." line rather than a missing section.
- The summary is wrapped in `<!-- PR-SUMMARY:START -->` / `<!-- PR-SUMMARY:END -->` markers; `splice_summary_block` inserts it at the top of the PR body, replacing any prior block (idempotent) and leaving the `## Closes` section untouched. Body order is PM → Engineer → `## Closes`.
- If there is no open PR, or Claude writes no summary, the step warns and leaves the body unchanged — it never fails the run at the finish line.

### Tests

Run from `scripts/`: `python3 -m pytest`. Suite is split across `test_orchestration.py` (loop/attempt/escalation behavior), `test_prd_data_layer.py` (schema validation — including `prd_issue`/`pr_number`/`last_reviewed_sha`/`sdlc_review_rounds`, the last with bool and negative rejection — locking, status transitions), `test_sdlc_gate.py` (review-gate prompt construction and status transitions, the `sdlc_review_rounds` cap (increment on a real round, none on an empty increment, re-arm allowed at 1 and suppressed at 2, the `RALPH_MAX_REVIEW_ROUNDS` override, final-round finding deferral, and the one-push-per-round guarantee), including the parallel→serial retry escalation, session-limit `incomplete`/resume behavior, and the incremental-review machinery: `_compute_review_range` first-run-vs-baseline-vs-stale-baseline selection, baseline recording + round-scratch clearing on completion, the empty-increment no-op, the `save_prd` re-arm carve-out, `_rearm_sdlc_review_gate`, the cumulative-vs-per-round finding-issue accounting (append/dedupe, re-arm preservation, the round-scratch re-file guard), and findings-file rotation including the fresh-round-vs-mid-round-resume distinction and symlink refusal), `test_pr_description.py` (`resolve_pr_number` field-vs-branch resolution, `splice_summary_block` idempotent marker splicing, and `update_pr_description` orchestration including the no-PR skip), and `test_config_root.py` (`resolve_config_root` under `meta/`, `docs/agents/`, both-present refusal, symlink/escape refusal, and the unscaffolded-repo default; derived-path helpers (`config_root_rel`, `plans_dir_for`, `logs_rel`, `work_pathspec`, `findings_path`, `pr_summary_path`) — all of which now take an already-resolved `config_root` rather than re-deriving it — under both layouts; `_ensure_artifacts_gitignored` covering all four runtime artifacts under both layouts, including the unignorable-log hard-refusal; one end-to-end `main()` run per layout driving a single-plan `prd.json` to completion; and a dedicated end-to-end run asserting `resolve_config_root` is called exactly once per `main()` invocation). `test_orchestration.py` also covers the finished-iteration guard (`test_iteration_guard_*`: merged/open PR, head mismatch, branch gone, gh/ls-remote failures, ordering before `_register_exit_flush`, `--dry-run`); existing `main()` tests stub `_iteration_finished` via an autouse fixture so they never touch the network.
