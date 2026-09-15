# Scripts

Real code, unlike most of this repo. `run-next-plan.py` is the Ralph Wiggum loop: a
non-interactive orchestrator that drives an iteration's plans to completion by repeatedly
spawning headless Claude sessions, then runs the SDLC review gate. Stdlib only, Python 3.10+,
with a pytest suite under `tests/` and ruff configured in `pyproject.toml`.

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

**Stalled**:
A plan that burned `MAX_ATTEMPTS` without reaching `done`. Terminal for the loop's purposes;
it does not block the gate.
_Avoid_: failed, blocked (`blocked_by` means something else entirely)

**Run log**:
The per-invocation transcript under `<config-root>/plans/implementation-logs/`. Full session
stdout/stderr with best-effort — explicitly not guaranteed — credential scrubbing. Gitignored
under both layouts, and the runner refuses to write one to a path the repo does not ignore.
_Avoid_: output, transcript file

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
