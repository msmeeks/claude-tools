# Run Next Plan (Ralph Wiggum loop)

## Summary

`scripts/run-next-plan.py` is a non-interactive orchestrator that drives an iteration's `meta/plans/` to completion. It repeatedly invokes a headless Claude session, letting Claude pick and implement the highest-priority unblocked plan, until every plan is `done`/`stalled` and a final SDLC review gate has passed. It's the "run" partner to `/plan-iteration`'s "plan" step.

## Users / Use Cases

- **Developer** — kicks off `python3 ~/.claude/scripts/run-next-plan.py` after `/plan-iteration` has written `meta/plans/prd.json`, then lets it run unattended (optionally overnight) through an entire iteration's plans.
- **Worker** — N/A (this script is itself the automation; there is no separate worker role).

## Technologies

- **Python 3 stdlib only** (`argparse`, `fcntl`, `json`, `subprocess`, `re`, `tempfile`, `pathlib`) — no third-party dependencies, matches the repo's minimal-dependency preference
- **`claude` CLI** — invoked headlessly via `claude -p - --permission-mode bypassPermissions --output-format text`, prompt piped over stdin
- **`gh` CLI** — used to file SDLC finding issues and sync `Closes #N` entries on the integration branch's PR
- **Docker** (optional) — sandboxes the Claude session when `meta/ralph.dockerfile` is present
- **`fcntl` file locking** — guards concurrent writes to `prd.json` across attempt-increment/status-set operations

## Technical Overview

The script treats `meta/plans/prd.json` as the single source of truth for plan state (`pending`/`in-progress`/`done`/`stalled`, `attempts`, `blocked_by`) and delegates all prioritization and implementation intelligence to Claude via a constructed prompt — the Python layer only does bookkeeping: selecting *some* eligible (non-terminal) plan as a starting point, incrementing attempt counters, detecting stalls, retrying through rate limits, and escalating model/effort on repeated failures. Once every plan reaches a terminal state, the script gates on an `sdlc_review_status` field in `prd.json` before declaring the iteration truly finished, running a full `/sdlc` review, filing findings as GitHub issues, and triaging them into new plans (which re-enters the loop) or halting for human input.

## Key Files

| File | Purpose |
|---|---|
| `scripts/run-next-plan.py` | The orchestrator itself |
| `meta/plans/prd.json` | Plan registry: `integration_branch`, `pr_number`, `prd_issue`, `plans[]` (file/status/attempts/blocked_by), `sdlc_review_status`, `sdlc_finding_issues`, `sdlc_review_completed_agents`, `feature_branches`, `smoke_test` |
| `meta/plans/progress.md` | Human-readable log Claude appends to after each completed plan |
| `meta/plans/implementation-logs/run-next-plan-*.log` | Per-invocation log (gitignored); scrubs credentials before writing |
| `meta/plans/implementation-logs/run-next-plan-*-triage.log` | Per-issue triage outcome log written by the SDLC review gate |
| `meta/ralph.dockerfile` | Optional sandbox Dockerfile; if present, Claude runs inside a built container instead of on the host |
| `meta/ralph.dockerfile.example` | Template for the above, with a bind-mount security note |
| `scripts/tests/test_orchestration.py`, `test_prd_data_layer.py`, `test_sdlc_gate.py`, `test_docker_sandbox.py`, `test_pr_description.py` | Test suite; run via `cd scripts && python3 -m pytest`. `test_orchestration.py` covers `_working_tree_dirty`, `_push_branch`, and `ensure_committed_and_pushed` against real throwaway git repos (with a bare "remote"), not mocks. |
| `skills/close-iteration/skill.md` | Step 2b reads this script's `sdlc_review_status` values (`pending`/`complete`/`needs-human`) from `prd.json` as a hard-blocker check before promoting/merging the iteration |

## Technical Detail

### Plan loop and attempt tracking

Each pass through the `while True:` loop re-reads `prd.json`, selects a non-terminal plan (`select_next_plan` only screens out fully-`done`/`stalled` plans and fully-circular `blocked_by` graphs — actual priority/dependency judgment is left to Claude, which is instructed to respect `blocked_by` unless it can verify a dependency is already satisfied by reading the plan files), increments that plan's `attempts` counter under an `fcntl` lock, and invokes Claude with a fixed prompt. Plan file content is explicitly framed as untrusted document text in every prompt, not as instructions to follow.

### Stall detection and model escalation

`MAX_ATTEMPTS = 5`. A plan whose `attempts` exceeds 5 without reaching `done` is marked `stalled` (`mark_stalled`) and skipped from then on. Model/effort escalates by attempt count on the *current* invocation:

| Attempts so far | Claude invocation |
|---|---|
| 1–2 | default model/effort |
| 3–4 (`ESCALATION_THRESHOLD = 3`) | `--model sonnet --effort high` |
| 5 (`MAX_ATTEMPTS`) | `--model opus --effort max` |

### Rate-limit retries

`invoke_claude` returns both the combined stdout/stderr and the CLI's exit code, and `scan_output(text, exit_code)` classifies the result as `complete` (COMPLETE sigil found), `rate_limit`, `error`, or `ok`. Limit detection requires **two** independent signals, because either one alone produces false positives:

1. **A non-zero exit code.** A genuine session/usage limit terminates the `claude` CLI non-zero; a clean exit-0 run never is one. So limit-shaped text on a successful run is Claude *quoting* or discussing a limit — for example a reviewer flagging code as "not rate-limit-aware", or this file's own limit-handling code being read back during review — and is classified `ok`. This gate is what stops those incidental mentions from triggering a spurious wait.
2. **A `RATE_LIMIT_RE` match**, which narrows the non-zero exits that are limits (vs. ordinary errors). It matches only genuine limit *announcements*: a limit noun paired with "reached"/"exceeded", an explicit "resets H(:MM)(am/pm)" / "limit will reset" directive, `429 too many requests`, `overloaded_error`, or `retry-after`. It deliberately does **not** match bare tokens like "rate limit", "usage limit", "429", or "too many requests" on their own.

A non-zero exit *without* a regex match is a plain `error`. The real CLI message this is built against is `You've hit your session limit · resets 8:50pm (America/New_York)`, pinned as a regression test in `test_orchestration.py`.

On `rate_limit`, the script parses a retry delay from the output text via `_parse_retry_after_text`: an explicit "retry after N" / "try again in N", or a "resets [at] H[:MM]am/pm" time interpreted in America/New_York (minutes are optional — an on-the-hour "resets 9pm" parses to a real wait rather than falling through to the default and re-looping tightly until the limit clears). It falls back to `RETRY_WAIT_DEFAULT = 60`s, adds a flat 60s buffer, sleeps, and retries the same attempt — up to `MAX_RETRIES = 20` times before giving up and leaving the plan `in-progress` for a future run to resume.

### Commit/push enforcement

Claude is asked to commit (and, since this is the only thing that actually pushes anything, the prompts now say "commit and push") after each plan-implementation session, the docs phase, and the SDLC review gate's triage step. The script does not trust that this happened: `ensure_committed_and_pushed(repo_root, integration_branch, context)` runs after each of those three points and:

1. Checks `git status --porcelain`. If clean, skips straight to step 3.
2. If dirty, invokes Claude once more with a narrow "commit these outstanding changes" prompt. If the tree is still dirty afterward (Claude failed to commit for any reason), auto-commits everything with `git add -A` + a generic `wip: uncommitted changes from <context>` message as a safety net — this never blocks the loop, but does mean an occasional low-quality commit message can show up if Claude didn't commit its own work.
3. Pushes the branch (`_push_branch`): sets upstream via `git push -u origin <branch>` if none exists yet, otherwise pushes only if the local branch is ahead of `@{u}` (a no-op push is skipped rather than shelled out unnecessarily).

This closes the gap where a plan could be marked `done` in `prd.json` while its changes were still sitting uncommitted (or committed-but-unpushed) in the local working tree.

### Docker sandbox

If `meta/ralph.dockerfile` exists in the repo root, `build_run_command` wraps the `claude` invocation in `docker run` instead of running it directly. It refuses a symlinked dockerfile, rebuilds the image (`ralph-<sanitized-repo-slug>:latest`) only if the dockerfile is newer than the last build, and mounts the repo root at `/workspace` with `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `GIT_AUTHOR_NAME`, and `GIT_AUTHOR_EMAIL` passed through as environment variables.

### SDLC review gate

Once `select_next_plan` finds no eligible plans (or Claude emits the `<promise>COMPLETE</promise>` sigil and `prd.json` confirms all plans are terminal), the script checks `prd.json`'s `sdlc_review_status`:

- **`pending`** (default, and the only non-terminal value): runs `run_sdlc_review_gate`, which works through three phases inside a retry loop (`attempt` 1…`MAX_REVIEW_ATTEMPTS`):
  1. **Review** — generates findings into `meta/sdlc-review-findings.md` (`## <title>` + body blocks, no GitHub issues yet) by dispatching the seven `/sdlc` Phase-3 review agents (`SDLC_REVIEW_AGENTS`). For the first `REVIEW_PARALLEL_ATTEMPTS` (2) attempts the outstanding reviewers are dispatched **in parallel** (one Claude call, all-or-nothing); on later attempts they run **one at a time**, and each finished reviewer is appended to `sdlc_review_completed_agents` so a retry resumes only the remaining ones. The phase is skipped entirely once all seven agents are recorded complete.
  2. **File issues** — files each finding as a GitHub issue via `gh issue create`, labeled `sdlc-finding`, printing each new issue number as `ISSUE: #N`. The numbers are persisted to `sdlc_finding_issues` immediately so a later interruption resumes triage against them instead of re-filing (which would duplicate). Skipped if `sdlc_finding_issues` is already populated.
  3. **Triage** — for every filed issue, runs the real `/triage` skill non-interactively — self-answering any grilling-style open questions with a stated recommendation and rationale instead of pausing for user input — then applies `/triage`'s normal state machine. If, after self-answering, the issue still has more than a couple of unresolved material open questions, or the work is architecturally significant / crosses many subsystems / is roughly XL-sized (per `/plan-iteration`'s size key), the issue is deliberately marked `needs-info` (not `ready-for-agent`) with a comment capturing the open questions, rather than being auto-approved. Every issue that does reach `ready-for-agent` is clustered (à la `/plan-iteration` Step 5) into new `meta/plans/<slug>.md` plan files appended to `prd.json`, without opening a new integration branch or PR.

  The triage step logs one line per issue to `meta/plans/implementation-logs/run-next-plan-*-triage.log` and finishes by printing `HUMAN_IN_LOOP_REQUIRED: true` or `false`. If the marker is missing entirely (and the output was not a session-limit interruption), the script fails safe and treats it as `true`.

  On a clean finish, `sdlc_review_status` is set to **`needs-human`** if any issue was flagged `needs-info` for low confidence, or **`complete`** if every issue was confidently resolved to `ready-for-agent` or `wontfix`. `save_prd` additionally refuses to ever revert `sdlc_review_status` from a terminal value (`complete`/`needs-human`) back to `pending`, so the gate cannot silently re-run once resolved.

  **Session-limit resilience.** Every gate Claude call goes through `_gate_invoke`, which raises `ReviewInterrupted` when the invocation both exits non-zero and matches `RATE_LIMIT_RE` — the same two-signal discriminator `scan_output` uses, and for the same reason: review output routinely *discusses* rate limits, and an exit-0 reviewer that merely quoted limit text must not be mistaken for a real limit hit. A session/usage limit is therefore **never** misread as `needs-human`, and a reviewer discussing limits never triggers a spurious wait. Instead — exactly like the main plan loop — the gate parses the reset delay from the output (`_parse_retry_after_text` + 60s buffer), `time.sleep`s until it clears, and retries; the retry escalates the reviewer dispatch parallel→serial per the `attempt` counter (mirroring the per-plan model escalation). Each attempt commits any progress first (`sdlc_review_completed_agents`, `sdlc_finding_issues`), so nothing is lost. Only if the limit persists across all `MAX_REVIEW_ATTEMPTS` (5) attempts does the gate give up, returning `"incomplete"` (status left non-terminal, not `needs-human`); `_run_gate_and_continue` then exits 0 so a later re-run resumes from the persisted progress.

- **`complete`**: the docs phase runs (`run_docs_phase`: `/sdlc-doc-writer` scoped to the iteration's changed files, then `/help-docs` and `/demo` for new/changed features, committed to the integration branch), then `update_pr_description` writes the final PR summary (see below), then the script exits 0 — the iteration is genuinely finished.

- **`needs-human`**: the script does **not** re-run the gate or claim completion. It calls `_die_needs_human()`, which exits 1 with a message pointing at the most recent `run-next-plan-*-triage.log` and instructing a human to resolve the flagged `needs-info` issue(s) via a normal `/triage` pass; `run-next-plan.py` will resume automatically once `sdlc_review_status` is manually/externally updated to `complete`.

If new plans were created by the triage step, the loop simply `continue`s and picks them up like any other pending plan on the next pass.

### `/close-iteration` integration

`/close-iteration`'s Step 2b hard-blocker check reads `prd.json`'s `sdlc_review_status` directly to decide whether an iteration is eligible to promote/merge: `pending` or `needs-human` block the merge (the latter requiring human triage resolution first), only `complete` clears this check.

### CLI options

| Flag | Effect |
|---|---|
| `--restart` | Resets any `in-progress` plan(s) back to `pending` before selecting |
| `--skip-in-progress` | Treats `in-progress` plan(s) as `pending` for selection purposes only (local view, not persisted) |
| `--dry-run` | Prints the selected plan, `blocked_by` graph, attempts, Docker mode, and full Claude command/prompt without invoking Claude or writing logs |
| `--integration-branch BRANCH` | Overrides `prd.json`'s `integration_branch` (which is otherwise authoritative) |

### PR `Closes #N` sync

After every plan-selection pass (success, stall, or gate completion), `sync_pr_closes` scans `done` plans' `**Issues:**` lines for issue numbers and appends any missing `Closes #N` entries to the integration branch's open PR body via `gh pr edit`, so the PR always reflects which issues its merged plans close.

Any PR lookup goes through `resolve_pr_number(data, integration_branch)`: it prefers `prd.json`'s captured `pr_number` (written by `/plan-iteration` when it opens the draft PR) and falls back to a `gh pr list --head <branch>` lookup, returning `None` if there is no open PR. Both `sync_pr_closes` and the PR-description phase use it.

### Two-audience PR description

At the tail of `run_docs_phase` (once the iteration is genuinely complete), `update_pr_description` generates a PR summary aimed at two audiences and splices it into the PR body:

- `_generate_pr_summary` prompts Claude to write the summary to `meta/pr-summary.md`, grounded in the changed-file list, `progress.md`, and the closed-issue titles (full diff as backup). Each change is classified **user-facing** (observable product/UI/CLI/API/customer-doc behavior) or **backend/engineering** (everything else).
  - **For the Product Manager**: the PRD it implements (linked from `prd_issue`, or "No PRD issue linked" when absent), a brief overview, a bulleted list of user-facing changes, and a `- [ ]` GitHub-checklist test plan for those changes.
  - **For the Engineer**: the same shape for non-customer-facing/backend changes. Its test plan is deliberately *not* a re-run of the automated suite or CI — the prompt forbids "run pytest/ruff/lint", "check CI", and coverage items — and instead steers Claude to manual-reviewer verification: edge cases hard to exercise via UI/API (concurrency/locking, partial-failure and retry paths, boundary inputs), integration seams where a contract could drift, and architectural/schema/migration changes worth a design-level read, each naming the specific risk and where to look.
  - An audience with no changes gets an explicit "No … changes in this iteration." line rather than a missing section.
- The summary is wrapped in `<!-- PR-SUMMARY:START -->` / `<!-- PR-SUMMARY:END -->` markers; `splice_summary_block` inserts it at the top of the PR body, replacing any prior block (idempotent) and leaving the `## Closes` section untouched. Body order is PM → Engineer → `## Closes`.
- If there is no open PR, or Claude writes no summary, the step warns and leaves the body unchanged — it never fails the run at the finish line.

### Tests

Run from `scripts/`: `python3 -m pytest`. Suite is split across `test_orchestration.py` (loop/attempt/escalation behavior), `test_prd_data_layer.py` (schema validation — including `prd_issue`/`pr_number` — locking, status transitions), `test_sdlc_gate.py` (review-gate prompt construction and status transitions, including the `needs-human` path, the parallel→serial retry escalation, and session-limit `incomplete`/resume behavior), `test_docker_sandbox.py` (Docker wrapping logic), and `test_pr_description.py` (`resolve_pr_number` field-vs-branch resolution, `splice_summary_block` idempotent marker splicing, and `update_pr_description` orchestration including the no-PR skip).
