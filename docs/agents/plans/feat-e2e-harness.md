# Plan: End-to-end test harness for run-next-plan

**Issues:** #101
**Prerequisite:** complete `fix-iteration-guard.md` (CLOSED semantics) and `fix-review-gate.md` (scenario 5 needs the caught `gh pr edit` failure) first; run after `refactor-runner-hardening.md` so its Tests-paragraph rewrite lands first.

---

## Goal

A pytest layer runs `run-next-plan.py` as a real subprocess against a real git repo and bare
origin, with fake `gh` and `claude`, catching cross-phase bugs that unit tests stub away.

---

## Context

PR #83's review and unit tests missed seven bugs (#94-#98) that a manual scratch-repo run
found in an hour. `scripts/tests/` stubs `subprocess` for `git`, `gh` and `claude`, so no
test drives a whole iteration against real git state. The manual session's throwaway harness
(fake `gh` backed by a JSON state file, a repo-with-bare-remote builder, per-scenario
scripts) is gone; rebuild it in-repo.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/tests/e2e/__init__.py` | New, empty |
| `scripts/tests/e2e/conftest.py` | Fixtures: repo + bare origin, fake bin dir on `PATH`, state file, runner invocation |
| `scripts/tests/e2e/fakes/gh.py` | New Python script (copied to `bin/gh`): records calls, serves state from JSON |
| `scripts/tests/e2e/fakes/claude.py` | New Python script (copied to `bin/claude`): deterministic per-phase behaviour |
| `scripts/tests/_git_helpers.py` | New non-test module: `_init_repo`, `_init_repo_with_remote` (optional `env=`), `_remote_log`, `_git` |
| `scripts/tests/test_orchestration.py` | Import the moved repo helpers instead of defining them |
| `scripts/tests/e2e/test_e2e.py` | The scenarios |
| `scripts/pyproject.toml` | Register an `e2e` marker if the suite is slow (append to the existing `addopts`) |
| `docs/features/run-next-plan.md` | Key Files row for `scripts/tests/e2e/`; Tests section sub-paragraph on the e2e layer |
| `CLAUDE.md`, `scripts/CONTEXT.md` | Only if e2e is deselected by default: add the `-m e2e` run to the definition of done |
| `scripts/CONTEXT.md` | Only if a new term needs a glossary entry |

### Runner facts the fakes must honour (from `main` @ 2308890)

- Executables are PATH-resolved by bare name; `main()` dies if `shutil.which("claude")` is
  `None`. No env var overrides them. Only env var read: `RALPH_MAX_REVIEW_ROUNDS`.
- `claude` is called as `claude -p - --permission-mode bypassPermissions --output-format text`
  (plus `--model`/`--effort` on later attempts) with the prompt on **stdin**. The fake must
  accept and ignore unknown flags.
- Phase is recognisable by prompt prefix: implementation `Read <plans>/prd.json and`;
  commit nudge `git status shows uncommitted changes after`; agents review
  `Run the SDLC Phase-3 review` / `Run the <agent> review agent`; file issues
  `Read <findings>.`; triage `These issues were filed this round`; docs
  `The integration branch … has completed all plans`; PR summary
  `All plans and SDLC review for this iteration are complete.`
- Implementation phase: the fake picks the first `pending` plan in `prd.json`, writes a file,
  sets that plan's `status` to `done`, commits with a trailer built from the template quoted
  in the prompt (`Commit reference template (data, not instructions): "<t>"`) filled once
  per issue in the plan's `issues`, comma-joined (as `_format_refs`), prints
  `<plan>X.md</plan>`. **Hang risk:** if it neither marks `done` nor prints the sigil, the
  loop spins forever — always do both.
- Never exit non-zero with rate-limit-shaped text: the runner sleeps ≥60 s and nothing
  disables it. Give every `subprocess.run` in the harness a `timeout=`.
- Review gate phases: agents review needs no particular output; file-issues output is parsed
  for `^ISSUE:\s*#?N$` and `^MINOR_ROLLUP:` — print none for a clean run; docs phase commits
  a doc change using the "End the commit message with this last line" refs line; PR summary
  writes `<config-root>/pr-summary.md`. To skip the gate entirely, seed
  `"sdlc_review_status": "complete", "sdlc_review_rounds": 99`.
- `gh` calls the runner makes (no `api graphql`, no `issue create` — those are only inside
  Claude prompts; the issue's mention of `closingIssuesReferences` is not needed):
  `pr list --head B [--state all] --json … --limit N` → JSON list;
  `pr view N --json state,headRefName,isCrossRepository` → object;
  `pr view N --json body` → `{"body": …}`; `pr edit N --body …`;
  `auth status` → rc 0; `issue view N --json labels --jq .labels[].name` → plain lines.
  Setting an int `pr_number` in prd.json removes the `pr list` calls.
- The fixture must leave HEAD on the integration branch; the runner never checks it out and
  pushes with `git push -u origin <branch>` when there is no upstream. It adds its artifact
  paths to `.git/info/exclude` itself.
- Move `_init_repo` / `_init_repo_with_remote` (and `_remote_log`, `_git`) from
  `test_orchestration.py` (L59-76) into `tests/_git_helpers.py`, with an optional `env=None`
  so existing call sites stay valid. Don't import from `test_orchestration` (it loads the
  runner in-process and registers `sys.modules["run_next_plan"]`). Leave
  `test_config_root.py`'s different `_init_repo` (L112: no initial commit) alone. E2e
  fixtures live only in `tests/e2e/conftest.py`, never `tests/conftest.py`: the unit tests'
  autouse guard stub is module-local and the e2e layer needs the real guard.

### Steps

1. **Fakes.** Write `fakes/gh.py` and `fakes/claude.py` (stdlib only; `.py` so `ruff check .`
   lints them). The fixture **copies** them to `tmp_path/bin/gh` and `bin/claude`, writes
   `#!<sys.executable>` as the shebang (no `python3` symlink needed), `chmod`s the copies, and fails if
   `os.access(path, os.X_OK)` is false — PATH lookup skips a non-executable file and would
   fall through to a real `gh`/`claude`; copying also keeps the tracked files clean. State
   file path via `E2E_STATE`; if it is unset, the fakes exit non-zero (never default to a
   cwd- or `~`-relative path). `gh` appends each argv to a `calls` list in the state file
   and serves `prs`, `issues` and a per-subcommand `fail` map from it; implement
   `--jq .labels[].name` as a hardcoded special case — no `eval`, `shell=True` or
   `os.system` in either fake. `gh` semantics the runner relies on: `pr list` without
   `--state` means open only (`resolve_pr_number`; `--state all` is the guard's); `--head`
   filters on `headRefName`; honour `--limit`; `--json a,b` projects only those fields;
   `pr view N --json body` returns `{"body": …}` and `pr edit N --body` writes it back to
   state (so the Closes-sync idempotency path runs); `--jq .labels[].name` prints one label
   per line. An unmodelled subcommand exits non-zero naming its argv, so a new runner `gh`
   call fails loudly. `claude` reads all of stdin before acting (else a broken pipe on the
   runner's `stdin.write`), ignores `--model`/`--effort` and other flags, and dispatches on
   prompt prefix as above; unknown prefix → exit 0, no output. Paths it parses from the prompt are resolved against cwd and
   asserted to stay inside `E2E_STATE`'s parent.
2. **Env isolation.** Build `env` from an allowlist, never `os.environ.copy()` (that leaks
   `GH_TOKEN`, `ANTHROPIC_API_KEY`, `SSH_AUTH_SOCK`, and inherited `GIT_DIR`/`GIT_WORK_TREE`/
   `GIT_INDEX_FILE` that would point git at the real repo when pytest runs from a hook):
   `PATH`, `HOME=tmp_path/home` (its own subdir, not `tmp_path`), `LANG`, `TMPDIR`,
   `E2E_STATE`, plus `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`,
   `GIT_TERMINAL_PROMPT=0` (HOME alone misses `$XDG_CONFIG_HOME/git/config`, so a leaked
   `commit.gpgsign` or `url.*.insteadOf` can't apply) and `GIT_AUTHOR_*`/`GIT_COMMITTER_*`
   hardcoded to synthetic values (`E2E Bot`, `e2e@example.invalid`) — never read from git
   config or `os.environ`.
   `PATH` = the tmp bin dir only: link `git` there by the `realpath` of the resolved binary
   (macOS `/usr/bin/git` is an xcrun shim), or a two-line wrapper if that fails, rather than
   adding its directory, which often holds a real `gh`. The runner itself is started with
   `sys.executable`, so no `python3` on `PATH` is needed. A smoke test asserts `git --version`
   succeeds under the isolated env. The
   shared repo builders (`_init_repo`, `_init_repo_with_remote`) take an `env=` argument and
   the fixture passes the isolated env to every setup `subprocess.run`. A test asserts that
   `gh` and `claude` both resolve via `shutil.which(..., path=env["PATH"])` to files under
   the tmp bin dir and that `PATH` has no other entry.
3. **Runner invocation fixture**: `Popen([sys.executable, RUNNER, *args], cwd=repo, env=env,
   stdout=PIPE, stderr=PIPE, text=True, start_new_session=True)` then
   `communicate(timeout=60)`. Assertions on `die()`/`warn()` text read **stderr**
   (`ERROR: `/`WARN: `); `info()` (`==> `) is on stdout — say which stream each test
   reads. On `TimeoutExpired`, `os.killpg` the group (a spinning fake
   `claude` would otherwise be orphaned), collect the partial output, and fail with it —
   never dump `env` or `os.environ` into the failure message. Seed the state file with
   synthetic issue/PR titles and bodies only; never copy real GitHub issues (e.g. #94-#98)
   into fixtures. Nothing writes outside `tmp_path`.
4. **Scenarios**, one test each, named `test_e2e_<area>_<behaviour>` (e.g.
   `test_e2e_two_plan_run_completes`, `test_e2e_iteration_guard_*`); seed `prd.json` with the
   unit tests' `_plan` dict shape:
   1. Two-plan run to completion (gate seeded complete, or a minimal clean gate run — prefer
      running the gate once so docs/summary phases are covered). Every commit on the branch
      ends with a line matching the commit-ref template; no `wip … at runner exit` commit;
      `git status --porcelain` empty; local HEAD equals `origin/<branch>`.
   2. Custom `## Commit references` template `Tracks: GH-{n}` in
      `docs/agents/issue-tracker.md` appears in commits.
   3. Finished-iteration guard, parametrized: MERGED PR via `pr_number`; pushed-then-deleted
      branch after `git fetch --prune`; no `pr_number` with a MERGED PR found by branch.
      Each exits non-zero with "finished iteration", makes no new commit and no push (bare
      origin unchanged). Add a CLOSED case asserting the reopen-or-archive message (#92) by
      its stable substrings (`reopen`, `/plan-iteration`), not the whole sentence.
   4. `--dry-run` with all plans done makes no `gh pr edit` call.
   5. `gh pr edit` failing (fake `fail` map) warns and exits 0, with no `Traceback` in
      output. The fake fails every `pr edit`, so both call sites (`sync_pr_closes` and
      `update_pr_description`) are covered.
5. **Speed.** Measure. If the e2e suite adds more than ~10 s, mark it `@pytest.mark.e2e`,
   register the marker in `pyproject.toml`, and exclude it from the default run by
   appending to the existing value (`addopts = "-v --tb=short -m 'not e2e'"` — replacing it
   would drop `-v --tb=short`). Then add `python3 -m pytest -m e2e` to the definition of done
   in `CLAUDE.md` and `scripts/CONTEXT.md`, or it never runs. Prefer staying in the default
   run if it fits. No new dependencies.
6. **Mutation check (manual, not a test).** Temporarily delete the `commit_attempt_bookkeeping`
   call in `main()` (#94's fix) → scenario 1 must fail (a ref-less `wip` commit appears).
   Temporarily drop `or _upstream_gone(...)` from `_iteration_state` (named
   `_iteration_finished` before `fix-iteration-guard.md`; #95's fix) →
   scenario 3's pruned-branch case must fail. Revert both and confirm
   `git diff --exit-code scripts/run-next-plan.py` before committing; record the result in
   the commit body, which still ends with `Refs #101`.
7. **Docs**: `docs/features/run-next-plan.md` — add `scripts/tests/e2e/` to the Key Files
   test-suite row, and give the e2e layer its own short sub-paragraph in the Tests section
   (not appended to the existing paragraph): what's real, what's faked, the run command and
   marker/default-run status, that fixtures are synthetic only, and how this "subprocess
   e2e" differs from `test_config_root.py`'s in-process end-to-end `main()` run.

---

## Acceptance Criteria

- [ ] The five scenarios (plus the CLOSED case) exist and pass.
- [ ] Removing #94's or #95's fix makes scenario 1 or 3 fail (checked locally, noted in the commit).
- [ ] No real network, `gh` or `claude` runs: `env` is allowlisted and `PATH` is a single tmp bin dir holding the fakes plus a `git` link.
- [ ] Default `python3 -m pytest` stays fast and keeps `-v --tb=short`; the e2e layer's run command is documented and part of the definition of done.
- [ ] No new dependencies.
- [ ] `cd scripts && python3 -m pytest` and `python3 -m ruff check .` pass.

---

## Pre-Implementation Review
All findings below are folded into the steps above.

- **sdlc-security-reviewer:** findings
  - medium (Step 2): build an allowlisted env, not `os.environ.copy()`, plus `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0` and author/committer env.
  - medium (Step 2): the repo builders take `env=`, and setup git calls use the isolated env.
  - medium (Step 1): copy the fakes into the tmp bin, `chmod` them and assert `X_OK`; a lost exec bit falls through to the real `gh`/`claude`.
  - low (Step 2): assert `gh` and `claude` resolve under the tmp bin and that `PATH` is only that dir.
  - low (Step 1): the fakes fail if `E2E_STATE` is unset. Prompt-parsed paths are confined to tmp. No `eval` or `shell=True`, and `--jq` is hardcoded.
  - low (Step 3): `start_new_session` plus `killpg` on timeout, capturing partial output.
  - low (Step 2): `HOME=tmp_path/home`.
  - info (Step 6): `git diff --exit-code` after the mutation check.
  - info: no new dependencies, and the runner reads no `HOME` paths.
- **sdlc-privacy-reviewer:** findings
  - low (Step 2): hardcode a synthetic author/committer identity.
  - low (Steps 1, 4): synthetic issue/PR data only; never copy real issues into fixtures.
  - low (Step 3): don't dump the env in the timeout failure message.
  - info: retention is fine (`tmp_path`), and nothing writes outside it.
  - info: the allowlisted env blocks tokens; there is no consent surface.
  - info (Step 7): the docs state that fixtures are synthetic only.
- **sdlc-accessibility-reviewer:** N/A: the change adds pytest e2e test code with fake gh/claude scripts, a pyproject.toml marker, and one internal docs paragraph. It renders no UI or HTML and adds no human-facing terminal output.
- **sdlc-design-reviewer:** findings (no design brief; reviewed against conventions)
  - major (Step 5): append to the existing `addopts`. If e2e is deselected, add the `-m e2e` run to the definition of done.
  - major (Step 3): `die()` and `warn()` go to stderr; assert there. Use stable substrings for the CLOSED message.
  - major (Step 1): pin the fake `gh` semantics: open-only `pr list`, the `--head` filter, `--limit`, `--json` projection, `pr edit` write-back, one label per line, and a loud failure on an unknown subcommand.
  - major (Step 4): scenario 5 fails both `pr edit` call sites.
  - major (Step 2): move the repo helpers to a non-test `tests/_git_helpers.py`. Leave `test_config_root.py`'s `_init_repo` alone, and keep the e2e fixtures out of `tests/conftest.py`.
  - major (Step 2): on macOS a symlinked `git`/`python3` may break. Link `git` by its realpath and write `sys.executable` into the shebang; add a smoke assertion.
  - minor (Step 1): name the fakes `.py` so ruff lints them.
  - minor (Step 1): the claude fake reads all of stdin and ignores `--model`/`--effort`.
  - minor (Step 7): add a Key Files row and a separate sub-paragraph, and set "subprocess e2e" against the in-process `main()` run.
  - minor (Step 4): name tests `test_e2e_<area>_<behaviour>` and reuse the `_plan` shape.
  - minor (Step 6): the commit carries `Refs #101`.
