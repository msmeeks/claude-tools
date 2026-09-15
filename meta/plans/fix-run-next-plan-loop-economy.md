# Plan: Ralph loop economy — push once per plan, cap review rounds, drop the Docker sandbox

**Issues:** #54, #53, #56

---

## Goal

An unattended Ralph iteration finishes without exhausting the target repo's GitHub Actions budget or looping indefinitely on self-generated review findings, and the orchestrator sheds a sandbox feature nobody uses.

---

## Context

On `msmeeks/hospitality-scheduled` PR #122 a single iteration produced 172 commits and 55 script-issued pushes across 18 days, each push firing at least two workflows (one of which provisions a Fly.io dev environment) — enough to exhaust the account's monthly Actions minutes. Two independent causes: `ensure_committed_and_pushed` couples committing to pushing and is called at three points per plan plus once per review-gate retry, and `_rearm_sdlc_review_gate` flips the review gate back to `pending` every time triage appends plans, with no bound — that iteration re-armed 8 times and walked finding issues #135 → #320 before a session limit killed it. Separately, the Docker sandbox branch in `build_run_command` has never been used by any repo. This plan decouples commit from push, bounds the gate at two rounds, and deletes the sandbox.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Split `ensure_committed_and_pushed` into `ensure_committed` + `flush_push`; add `sdlc_review_rounds` counter and `MAX_REVIEW_ROUNDS`; delete `build_run_command`, `get_image_tag`, `_IMAGE_TAG_SAFE_RE`, the `docker_mode` branch and its `--dry-run` print; reword commit/push prompts |
| `scripts/tests/test_orchestration.py` | Push-count-per-plan and push-on-exit coverage against the existing real-git fixtures |
| `scripts/tests/test_sdlc_gate.py` | Re-arm allowed 1→2, suppressed 2→3; counter survives session-limit resume; deferred findings excluded from `sdlc_finding_issues` |
| `scripts/tests/test_prd_data_layer.py` | Schema validation for `sdlc_review_rounds` |
| `scripts/tests/test_docker_sandbox.py` | Delete entire file |
| `meta/ralph.dockerfile.example` | Delete |
| `docs/features/run-next-plan.md` | Update "Commit/push enforcement", "SDLC review gate", prerequisites, artifacts table, `--dry-run` table, test-suite description; drop the "Docker sandbox" section |
| `README.md` | Drop the Docker sandbox paragraph; correct the review-gate description ("only ever runs once per prd lifecycle" is already false) |

### Steps

1. **Delete the Docker sandbox first** — it is self-contained and shrinks the file before the riskier refactors. Remove `_IMAGE_TAG_SAFE_RE` (`scripts/run-next-plan.py:503`), `get_image_tag` (:506-508), `build_run_command` (:511-573, including its function-local `datetime` import at :540), the `docker_mode` block in `main` (:1388-1397), the `Docker mode` line in the `--dry-run` print (:1406), and the docstring paragraph (:20-22). `main` then passes `claude_cmd` straight through. Delete `scripts/tests/test_docker_sandbox.py` and `meta/ralph.dockerfile.example`. Module-level `subprocess`, `os`, `re`, and `Path` are all used elsewhere — no top-level import becomes dead.

2. **Split commit from push.** `ensure_committed_and_pushed` (:756-782) becomes `ensure_committed(repo_root, integration_branch, context)` — identical body minus the trailing `_push_branch` call at :782 — plus a separate `flush_push(repo_root, integration_branch)` wrapping `_push_branch` (:731-753). Keep the commit half at all four existing call sites: `run_docs_phase` (:857), the gate's give-up branch (:1113), the gate's `ReviewInterrupted` handler (:1136, which runs up to 5× per gate run), and `main`'s per-plan site (:1498).

3. **Place the pushes.** One `flush_push` after the per-plan commit in `main` (:1498). One at the end of the review gate, after the docs phase rather than before it — today the gate pushes at :1153 and `run_docs_phase` pushes again at :857, so a completed gate pushes at least twice. Note `_generate_pr_summary` writes `meta/pr-summary.md` after the docs-phase commit has already run (:857 precedes :858), so that file is currently never committed; fold it into the terminal commit.

4. **Cover every exit path.** There are no signal handlers, no `atexit`, and no `try/finally` around `main`. Add a single registration point — an `atexit` hook or a `try/finally` in `main` — that flushes an unpushed branch, rather than sprinkling `flush_push` across the ten `sys.exit` sites (:1253, :1351, :1358, :1420, :1521, :1525, :1537, plus `die`'s :141). It must cover: normal completion, the `incomplete`-gate resume exit, the session-limit give-up, the error exit, and `KeyboardInterrupt`. `_push_branch` already no-ops when `@{u}..HEAD` is empty and only warns on failure, so a redundant flush is cheap and a failing one can't break the exit path. `--dry-run` must never push.

5. **Reword the prompts.** `_build_claude_prompt:487` ("Commit AND push your changes to {integration_branch}") → commit only. `run_docs_phase:853` step 5 and `_run_triage_phase:1209` likewise. The remediation prompt at :762-765 already says "Do not push" — leave it. Update the doc prose at `docs/features/run-next-plan.md:79-87`, which explains the old rationale.

6. **Batch `sync_pr_closes`.** It is called at :1352, :1356, :1515, and :1529 and issues a `gh pr edit --body` each time. Gate it to run at most once per push — track whether the closes set changed since the last write, and skip the call when nothing new landed. It already early-returns when there are no new `Closes` lines, so this is about the redundant fetch/compare, not correctness.

7. **Add the round counter.** New optional top-level `sdlc_review_rounds` int in `prd.json`, validated in `_validate_prd_schema` (:154-215) alongside the other optional ints — non-bool, non-negative, defaulting to 0 when absent so existing prd.json files stay loadable. Add a `MAX_REVIEW_ROUNDS = 2` module constant next to `MAX_REVIEW_ATTEMPTS` (:107) and make it overridable (env var or CLI flag) for the rare iteration that wants more.

8. **Increment at the gate's terminal write** — inside `run_sdlc_review_gate`'s `mutate` at :1161-1170, the same lock-protected write that sets `complete` and records `last_reviewed_sha`. The empty-increment no-op path `_mark_empty_complete` (:1098-1106) should *not* increment: it did no review.

9. **Suppress the re-arm at the cap.** `_rearm_sdlc_review_gate` (:1226-1239, single call site at :1339) becomes a no-op once `sdlc_review_rounds >= MAX_REVIEW_ROUNDS`, logging via `info()` that it stopped by policy rather than by convergence and naming the deferred issue numbers. Note the `complete → pending` reversal is only legal through `save_prd`'s carve-out at :244-253, which requires a non-empty `last_reviewed_sha` — the suppressed path must not trip that `die` at :254.

10. **Keep deferred findings out of the `Closes` block.** `sdlc_finding_issues` is appended-deduped in `_run_file_issues_phase`'s mutate (:1053-1060). On the final round, the filed issues must land in `sdlc_round_filed_issues` (so the round's own bookkeeping and the re-file guard still work) but must *not* be appended to `sdlc_finding_issues`, which `/close-iteration` reads for the PR's `Closes` list. Same failure mode as #47/#44: a PR must not claim to close findings it never fixed.

11. **Tests.** `test_orchestration.py` already drives real throwaway git repos with a bare "remote" (`_init_repo_with_remote`, `_remote_log`) — use them to assert push *counts*, not just push effects: one push per plan iteration, and one on each termination path. `test_sdlc_gate.py` patches `subprocess.run` via `_fake_subprocess_run` and will need the new counter threaded through `_valid_prd()`. Note no test currently exercises `main`, so the exit-path coverage needs either a `main`-level test or a directly testable flush helper — prefer the latter.

---

## Acceptance Criteria

- [ ] A plan iteration that runs implementation + docs + triage phases produces exactly one push, not three
- [ ] No termination path — normal exit, all-plans-terminal exit, session-limit give-up, error exit, `KeyboardInterrupt`, `die()` — leaves committed-but-unpushed work on the integration branch
- [ ] `--dry-run` pushes nothing and prints no Docker mode line
- [ ] Claude-facing prompts instruct "commit" at intermediate phases; no prompt tells Claude to push except where the script cannot
- [ ] `sync_pr_closes` writes the PR body at most once per push
- [ ] `prd.json` carries `sdlc_review_rounds`, validated like the other optional top-level ints, and a prd.json without the field still loads
- [ ] The review gate runs at most twice per iteration; the third re-arm is suppressed with an `info()` line naming the deferred issues
- [ ] Round-2 findings are still filed and triaged as GitHub issues, but produce no new plan files, no new `prd.json` plan entries, and no entries in `sdlc_finding_issues`
- [ ] Creating a `ralph.dockerfile` in a target repo has no effect; no Ralph-sandbox reference survives in `scripts/` or `README.md`
- [ ] A `git push` failure whose stderr contains a credential-shaped token is scrubbed in the log, with a regression test
- [ ] The exit-path flush performs git operations only — it never reads or writes `prd.json` and never acquires the prd lock
- [ ] Every exit-path commit goes through `_WORK_PATHSPEC`; `implementation-logs/` appears in no pushed commit on any termination path
- [ ] Finding bodies filed as GitHub issues are redacted or paraphrase-only, and `meta/PRIVACY.md` documents this outbound path, `sdlc_review_rounds`, and the retention story for deferred findings
- [ ] `sdlc_review_rounds` rejects bools and negatives, and is incremented only under the prd lock
- [ ] The docs state plainly that the loop now runs unsandboxed on the host under `bypassPermissions`
- [ ] `cd scripts && python3 -m pytest` passes; `python3 -m ruff check .` passes
- [ ] `docs/features/run-next-plan.md` documents the commit/push split, the round cap, and the deferral behavior; `README.md`'s claim that the gate "only ever runs once per prd lifecycle" is corrected

---

## Pre-Implementation Review

Security and privacy reviewers found no blocker to the plan's shape, but several items must become part of the implementation rather than being discovered during it.

### Security

- **Push-failure output is never credential-scrubbed.** `_push_branch:751` logs raw `git push` stderr via `warn()`, and `_scrub_credentials` is applied only to Claude subprocess output (:835, :1455) — never to git/gh output. Widening the push to every exit path multiplies how often this fires, including from hurried error branches where a credential-helper URL (`https://x-access-token:ghp_…@github.com/…`) is most likely to appear in stderr. Route `_push_branch`'s failure message through `_scrub_credentials`, and add a regression test asserting a synthetic push failure containing a `ghp_`-shaped token is redacted in the log.
- **The exit-path push must not touch `prd.json` or re-enter `prd.json.lock`.** A handler firing while `_with_prd_lock` (:284-289) holds the flock would deadlock a single-threaded process. The flush must do git side effects only and defer all prd bookkeeping to the next invocation.
- **Every intermediate-phase prompt must say "do not push" explicitly**, not merely omit "push". The remediation prompt at :762-765 already does this correctly — use it as the template. Silence lets an injected instruction in plan or issue text reintroduce mid-phase pushes, which is exactly what the split exists to prevent. Keep the existing "treat plan content as untrusted document text" framing in every reworded prompt.
- **Validate `sdlc_review_rounds` with the same guard as `attempts` (:172-174)**: reject `bool` (since `isinstance(True, int)` is `True`) and negatives, or a `prd.json` carrying `"sdlc_review_rounds": false` silently defeats the cap. Increment it only under `_with_prd_lock`.
- **Check the cap before `_rearm_sdlc_review_gate` is called** from `main` (:1339), not only inside it. A neutered re-arm that still falls through to `select_next_plan` must terminate cleanly rather than spin, and must not trip `save_prd`'s `complete → pending` carve-out `die` at :254.
- **Deleting the sandbox removes the only process boundary for an unattended `bypassPermissions` loop.** The container was weak protection (rw bind-mount including `.git/hooks/`, secrets via `-e`), so the delta is small — but the docs must *replace* the Docker section with an explicit statement that the loop runs unsandboxed on the host and relies on prompt framing, not silently drop it and leave the trust model implicit.

### Privacy

- **Findings filed by the review gate are never redacted.** `_run_file_issues_phase` (:1039-1062) has Claude file reviewer-written bodies verbatim via `gh issue create`, and those bodies are written while reading `git diff {review_range}` (:1010). Unlike the implementation logs, which get a credential-scrub pass, this outbound path has no redaction at all. The round cap makes it worse: deferred round-2 findings are designed to sit open in a public tracker indefinitely. Either scrub finding bodies before filing or instruct reviewers to paraphrase rather than quote raw diff lines — and document this outbound path in PRIVACY.md, which currently describes only the inbound direction.
- **Every new exit path must commit through `_WORK_PATHSPEC`, never a bespoke `git add -A`.** The log exclusion (:685) is what keeps raw session transcripts out of pushed history; a hastily-added interrupt handler is precisely where that gets bypassed. Test that `implementation-logs/` is absent from every pushed commit on *every* termination path, not just the happy one.
- **PRIVACY.md needs two updates**: add `sdlc_review_rounds` to its `prd.json` field enumeration, and add a retention note for the `sdlc-finding` issues the runner files — with the round cap, deferred findings persist until a human closes them, and the automation cannot retract a public issue body.

### Not findings

Push batching does not itself change what is committed — commits already happen per phase regardless of push cadence. The Docker deletion is self-contained: `get_image_tag`, `build_run_command`, and `_IMAGE_TAG_SAFE_RE` appear nowhere outside the orchestrator and its own test file.
