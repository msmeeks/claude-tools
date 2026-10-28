# Scripts

Real code, unlike most of this repo. `run-next-plan.py` is the Ralph Wiggum loop: a
non-interactive orchestrator that drives an iteration's plans to completion by repeatedly
spawning headless Claude sessions, then runs the SDLC review gate. Stdlib only, Python 3.10+,
with a pytest suite under `tests/` and ruff configured in `pyproject.toml`.

Per-repo review configuration lives in `<config-root>/ralph.json` (see
[ADR 0002](../docs/adr/0002-review-recipe-is-repo-config.md)); `load_ralph_config` validates it
once in `main()` and passes it down like `config_root`.

Run the suite with `cd scripts && python3 -m pytest`; lint with `python3 -m ruff check .`
(the `ruff` binary may not be on PATH). Full reference:
[../docs/features/run-next-plan.md](../docs/features/run-next-plan.md).

## Language

**Config root**:
The repo-relative directory holding a project's agent config — `docs/agents/` in the
scaffolding layout, `meta/` in the original one. Resolved per repo by `resolve_config_root`
from a filesystem check in Python, never from repo content. A repo carrying both is refused.
Every plans path, `prd.json`, log, findings file, and PR summary derives from it.
_Avoid_: meta dir, plans root, project dir

**Layout**:
Which of the two config roots a repo uses. Both are read, permanently — the other repos on
this machine are not being migrated. See
[ADR 0001](../docs/adr/0001-scaffolding-layout-with-dual-read-fallback.md).
_Avoid_: scheme, convention, mode

**prd.json**:
The loop's state file at `<config-root>/plans/prd.json`: the plan list with each plan's
status, attempts, and `blocked_by`, plus the integration branch, PR number, and review-gate
bookkeeping. Mutated only under the prd lock.
_Avoid_: manifest, index, db

**Attempt**:
One genuine Claude session against a plan. Charged *after* the session and to the plan the
session actually advanced — a session-limit death does no work and must not burn one.
_Avoid_: retry, try (a rate-limited retry is explicitly not an attempt)

**Gate**:
The SDLC review gate: the phase that runs once every plan is terminal — review, file issues,
triage, docs, PR description. Latched through `prd.json`'s `sdlc_review_status` so an
interrupted run resumes rather than repeats.
_Avoid_: review step, final check

**Recipe**:
How the Gate's review phase produces findings, chosen per repo by `review.recipe` in
`<config-root>/ralph.json`. `agents` (default) dispatches the roster's `sdlc-*` agents straight
from Python; `skill` calls a named review skill that follows the headless review contract
(see [issue #69](https://github.com/msmeeks/claude-tools/issues/69)). A repo with no
`ralph.json` gets `agents` with the original seven reviewers.
_Avoid_: mode, strategy, backend

**Roster**:
The ordered reviewer ids a Recipe runs (`review.reviewers`; `plan_review.reviewers` for
`/plan-iteration`). Ids are agent names, plus bare `spec` / `compliance` for skills that offer
them. A reviewer is recorded complete only from its `<reviewed>id</reviewed>` line (skill
recipe) or after its dispatch returns (agents recipe) — never from having been requested.
_Avoid_: reviewer list, agent set

**Stalled**:
A plan that burned `MAX_ATTEMPTS` without reaching `done`. Terminal for the loop's purposes;
it does not block the gate.
_Avoid_: failed, blocked (`blocked_by` means something else entirely)

**Run log**:
The per-invocation transcript under `<config-root>/plans/implementation-logs/`. Full session
stdout/stderr with best-effort — explicitly not guaranteed — credential scrubbing. Gitignored
under both layouts, and the runner refuses to write one to a path the repo does not ignore.
_Avoid_: output, transcript file

**Commit reference**:
The `Refs #N` trailer every runner-made commit carries, rendered from the `## Commit references`
template in `<config-root>/issue-tracker.md` (default `Refs #{n}`). Only validated ints ever
reach it. Each attempt's prd.json bookkeeping is committed with the charged plan's refs, so
`exit_flush` — the one commit without one — only fires after an interrupted run.
_Avoid_: issue link, footer

**Deferred issue**:
A filed review finding this PR will not fix — final-round findings and minor rollups — recorded
in `prd.json`'s `sdlc_deferred_issues`, never in `sdlc_finding_issues`, so it can't reach a
`Closes` line.
_Avoid_: leftover, backlog item

**Finished iteration**:
A `prd.json` whose same-repo integration PR was merged, or whose pushed branch is gone from
origin (a `[gone]` upstream after a pruning fetch still counts as pushed). With no
`pr_number`, the PR is found by a same-repo `--state all` lookup on the branch name.
`_iteration_state` makes the runner refuse it; `/plan-iteration` backs it up to
`prd.json.<date>.bak` and writes a fresh one. A PR closed unmerged is not finished: the runner
stops with a reopen-or-archive message, and `/plan-iteration` asks before archiving.
_Avoid_: stale prd, old run

## Boundaries

- **Python decides mechanics; Claude decides work.** The script tracks attempts, detects
  stall and session-limit conditions, and owns every git and `gh` side effect. Which plan to
  implement and how is delegated entirely to the spawned session.
- **Plan and issue text is untrusted document text.** Prompts say so explicitly. Paths
  interpolated into prompts are orchestrator-supplied and must never be parsed out of repo
  content — that is the whole reason `resolve_config_root` is a pure filesystem check.
- **The runner pushes; Claude does not.** Every prompt says "commit" and "do not push"; the
  script publishes once per plan iteration, once per completed review round, and once at exit.
- **Path safety is checked against resolved paths**, not literals: the config root itself,
  plan files (`_resolve_plan_path`), and the findings file (`_rotate_findings_file`) all refuse
  symlinks and anything escaping the repo.
- The loop runs unsandboxed on the host under `bypassPermissions`. There is no container.
