# Plan: run-next-plan.py trust-model hardening

**Issues:** #62, #65

---

## Goal

Operators of the unsandboxed `run-next-plan.py` loop get a clear runtime signal that they're running without isolation, and Claude-generated PR description content gets a code-level credential scrub before publication — both defense-in-depth backstops for the same underlying trust-model gap the recent Docker sandbox removal opened up.

---

## Context

`docs/features/run-next-plan.md` already documents, narratively, that the loop runs `claude --permission-mode bypassPermissions` directly on the host with no isolation boundary, and that this is an accepted, intentional tradeoff (the Docker sandbox removal was deliberate, and was weak protection anyway). Two concrete, achievable gaps remain against that already-stated trust model: (1) no runtime warning is printed to an operator when a real run starts, so the risk lives only in documentation someone may not have read; (2) the existing credential-scrubbing pattern (already applied to run logs and error/warning text) is not applied to the PR-description content Python passes to `gh pr edit` — even though Python holds that Claude-generated string in hand before publishing it. The issue-filing path (`gh issue create`, invoked by the Claude session itself as its own tool call) has no equivalent interception point in the current architecture and is explicitly out of scope here — closing that gap requires restructuring which side actually calls `gh issue create`, a larger change than either issue in this cluster proposes. Grouped together as the two achievable hardening additions arising from the same trust-model finding; the sandbox-restoration option itself is not being pursued (see the triage note on #62).

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `scripts/run-next-plan.py` | Print a one-time unsandboxed-trust-model warning at run start; apply the existing credential-scrubbing function to the body passed to both `gh pr edit` call sites in the PR-description update paths |
| `scripts/tests/` (orchestration / PR-description test files) | Add a test for the startup warning and a test that a credential-shaped string in a Claude-authored PR summary is redacted before `gh pr edit` is called |

### Steps

1. **#62 — startup warning.** Near where the config root or integration branch is first resolved in the entry point, print (via the script's existing warning/info output helper, not a new logging path) a one-time message to stderr on a real (non-`--dry-run`) run: the loop runs unsandboxed with the invoking user's full filesystem/git/`gh` access, plan and issue content is treated as untrusted document text but that's a mitigation and not a boundary, and it should only be run against repositories whose issue tracker is trusted. Gate it so it does not print under `--dry-run` and does not repeat per loop iteration.
2. **#65 — PR-description scrub.** In `update_pr_description` and `sync_pr_closes`, run the `new_body` string through the existing credential-scrubbing function before the `gh pr edit --body` call, in both places that build and pass such a body. Confirm the scrub only redacts secret-shaped substrings and leaves the two-audience summary content and `## Closes` block otherwise intact.
3. Add tests: one asserting the startup warning is emitted on a normal run; one asserting a credential-shaped string embedded in a Claude-authored PR summary is redacted before the `gh pr edit` subprocess call is made (e.g. by mocking `subprocess.run` and inspecting the `--body` argument).
4. Run `cd scripts && python3 -m pytest` and `python3 -m ruff check .`.

---

## Acceptance Criteria

- [ ] A real run prints the unsandboxed-trust-model warning to stderr exactly once; `--dry-run` does not print it
- [ ] Both `gh pr edit` call sites in the PR-description update paths scrub their body text before publishing
- [ ] A test confirms a credential-shaped string in a Claude-authored PR summary is redacted before the `gh pr edit` call
- [ ] Normal (non-secret) PR summary and `## Closes` content is unchanged by the scrub
- [ ] `cd scripts && python3 -m pytest` passes in full
- [ ] `python3 -m ruff check .` passes

---

## Pre-Implementation Review

Not run for this plan (see triage note — this batch skipped `/plan-iteration` Step 6's dispatch of the four planning-review agents; only Step 5 clustering and the Standard Plan Template were requested). Flagging for the next `/plan-iteration review` pass since this plan is itself security-hardening work.
