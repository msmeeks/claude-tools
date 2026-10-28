---
name: run-iteration
description: Drives a planned iteration to ready-to-close. Runs run-next-plan.py in a background subagent until it finishes, clears what blocks it, reviews the result, has a second subagent do manual and end-to-end verification, then reports what needs a human and reminds the user to /close-iteration. The step between /plan-iteration and /close-iteration. Use when plans are written and the user wants the iteration run, babysat, or finished.
---

# Run Iteration

The middle of the iteration trio: `/plan-iteration` writes the plans, this skill drives them to
ready-to-merge, `/close-iteration` merges. You are the **coordinator**: hand the long, noisy
work to subagents, keep your own context for judgment and the final report.

Never merge, and never run `/close-iteration` yourself — it is the user's call.

## Usage

```
/run-iteration
```

No arguments. State comes from `<config-root>/plans/prd.json`, so re-running resumes.

**Finished** means every `prd.json.plans` entry is `done` or `stalled` **and**
`sdlc_review_status` is `complete`. Read it from `prd.json`, never from the runner's exit
code: the runner also exits 0 when it gives up on a session limit or an incomplete review.

Subagent means a background `Agent` dispatch; where the host offers separate sessions (the
desktop app), one works too. Brief each one fully — it sees nothing of this conversation.

---

## Step 1 — Bootstrap

1. Read the context index: `CONTEXT-MAP.md` (or a root `CONTEXT.md`), or `docs/llms.md`. If
   neither exists, stop and tell the user to run `/sdlc` first.
2. Resolve `<config-root>`: `docs/agents/` if it exists, else `meta/`. Load
   `<config-root>/plans/prd.json`; if absent, stop and tell the user to run `/plan-iteration`.
3. Record `integration_branch`, `pr_number`, `smoke_test`, and the default branch
   (`git symbolic-ref refs/remotes/origin/HEAD`).
4. If `git status --porcelain` shows changes, stop and ask — never stash or commit the
   user's work.

---

## Step 2 — Run the loop (loop subagent)

Skip to Step 3 if the iteration is already finished.

Dispatch one subagent with this brief, and wait for its report:

> Drive `python3 ~/.claude/scripts/run-next-plan.py` in `<repo root>` until the iteration is
> **finished** (definition above — include it). It runs for hours: start it as a background
> task with output to a file, wait for it to exit, never a foreground timeout or tight poll.
>
> After each exit, if not finished, read the output's tail and the newest log in
> `<config-root>/plans/implementation-logs/`, fix the cause, and re-run:
>
> | Symptom | Action |
> |---|---|
> | Session/usage limit give-up | Wait for the reset time in the output, re-run |
> | `Claude exited with code N`, plan left `in-progress` | Re-run; if the same plan fails again, re-run with `--restart` |
> | Dies naming a malformed `prd.json` / `ralph.json` field | Fix that field, re-run |
> | Dies with "finished" or "unresolved iteration" | Stop and report — not yours to fix |
> | Dies with "consecutive sessions made no attributable progress" | Read the session logs it names for why sessions die early (auth, missing tool, crash on start); fix the cause, re-run |
> | Plan went `stalled` | Read its log. If the cause is fixable (wrong plan step, missing dependency, broken test setup), fix it in the plan file or code, set that entry's `status` to `pending` and `attempts` to `0`, re-run. Once per plan; a second stall stays stalled |
> | Bug in `run-next-plan.py` itself | Don't edit it; work around it if you can, else stop and report with the log line |
>
> In `prd.json`, change only a plan entry's `status`/`attempts`; never a top-level key. Commit
> fixes on the integration branch with the issue reference from `<config-root>/issue-tracker.md`
> (`## Commit references`, default `Refs #{n}`). Stop after two consecutive runs with no
> progress (no plan changed status, no new commit on the integration branch).
>
> Report, briefly and without log dumps: each plan's final status, `sdlc_review_status`,
> `sdlc_deferred_issues`, each fix you made (commit + one line), and anything still blocking
> with its cause.

**Done when** the subagent reports finished, or reports a blocker. On a blocker, go to Step 5
— don't review or verify an unfinished iteration.

---

## Step 3 — Review the work (you)

The runner already ran the SDLC review gate; don't repeat it. Record HEAD as `<pre-fix-sha>`,
then check what the gate doesn't:

1. **CI** — `gh pr checks <pr_number>`. Fix failures.
2. **Conflicts** — `git merge-tree` against `origin/<default>` as in `/close-iteration` Step 2d.
   Resolve with `/resolving-merge-conflicts`.
3. **Plan coverage** — for each `done` plan, every Acceptance Criteria item is met by
   `git diff origin/<default>...HEAD`. For each `stalled` plan, note what is missing.
4. **Smoke test** — run `smoke_test` if set.
5. **Human-labelled findings** — `sdlc_finding_issues` and `sdlc_deferred_issues` still open
   with `ready-for-human` or `needs-info`: note each for the report.

Fix what is small and local yourself, test-first, committed with the issue reference as in
Step 2. Anything bigger: file it per the "Filing issues" rules and list it for the report.

**Done when** each of the five checks is passed, fixed (commit), or listed.

---

## Step 4 — Verify end to end (verification subagent)

A fresh subagent, not the loop one: it should judge the work without the implementer's
assumptions. Brief:

> Verify iteration PR #`<pr_number>` on branch `<integration_branch>` in `<repo root>`. Your
> checklist: the test-plan items in the PR body's *For the Product Manager* and *For the
> Engineer* sections (`gh pr view <pr_number> --json body`), plus the Acceptance Criteria of
> each `done` plan in `<config-root>/plans/`. Each item is one check.
>
> Exercise the real thing: start the app (`/run` if the project has it), drive the UI in a
> browser, call the API, run the CLI, try the edge cases named. Local or test environments and
> test data only — never production, never real messages, payments, or other people's accounts.
>
> Give every item one verdict: **verified** (how, with evidence), **fixed** (what failed,
> commit), or **needs a human** (why: physical device, third-party account, credentials you
> lack, subjective visual or UX judgment). Fix failures you can — failing test first — and
> commit on the integration branch with the issue reference from
> `<config-root>/issue-tracker.md` (`## Commit references`, default `Refs #{n}`). Don't push.
>
> Report the per-item verdicts as a table, plus your commits.

**Done when** every checklist item has a verdict.

---

## Step 5 — Settle and report

If Steps 3–4 made commits, dispatch `sdlc-code-reviewer` and `sdlc-test-reviewer` over
`<pre-fix-sha>..HEAD` — the runner's gate never saw them — fix what they find, re-run
`smoke_test`, and `git push` once.

Then print:

```
=== Iteration ready to close ===        (or: === Iteration blocked ===)

PR:            #<N> <title> (<url>)
Plans:         <done> done, <stalled> stalled
Loop:          <runs> runs; fixes: <commit — one line each, or none>
Review:        CI <state>; fixes: <…>
Verification:  <v> verified, <f> fixed, <h> need a human

Needs your input:
- <decision, with the options>
Needs a human to verify or complete:
- <checklist item> — <why>
Left open after merge:
- #N — <stalled plan / deferred finding / filed this run>
```

Omit an empty section. End with exactly one of:

- Finished: `When the items above are settled, run /close-iteration.`
- Blocked: what would unblock it, and that `/run-iteration` resumes from there.
