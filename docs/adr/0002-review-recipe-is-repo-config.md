# The review recipe is per-repo config, and review skills share one contract

The Ralph loop's review gate dispatched the seven `sdlc-*` agents straight from Python, and
`/plan-iteration` hard-coded four plan-review agents. Some repos want a different review
skill, and there was nowhere to say so.

**Decision: an optional `<config-root>/ralph.json` names the recipe and the roster.** It sits
beside `prd.json` and is trusted the same way (plain schema validation, no extra hardening).
No file, or a missing key, means today's behaviour — an unconfigured repo is byte-identical.
Config is per repo, not global, because the right review differs by repo and
`~/.claude/CLAUDE.md` already governs every project on the machine.

**Decision: two recipes.** `agents` keeps direct dispatch from Python and is the default.
`skill` calls a named review skill. `plan_review.reviewers` configures plan-review agents
only; there is no plan-review skill option.

**Decision: every review skill implements one headless contract**, specified in
[issue #69](https://github.com/msmeeks/claude-tools/issues/69) rather than restated here.
Any skill that follows it — `/sdlc review` is the reference — is a valid recipe. Python keeps
parallel-to-serial escalation and per-reviewer resume by choosing what to pass as `--only`,
so skills stay stateless about the gate.

**Decision: the roster lives in config, not in the skill, and completion is evidence-based.**
The gate records a reviewer complete only from its `<reviewed>id</reviewed>` line. A skill
that silently skips a reviewer would otherwise let the gate pass with a hole in it; instead it
fails loudly, naming the reviewer.

## Consequences

- Adding a reviewer is a config edit; removing one is visible in the repo's diff.
- A skill that drifts from the contract surfaces as `UNSUPPORTED` or a missing-sigil failure,
  not as quietly thinner reviews.
- Retrying a parallel call that was cut off before any reviewer completed discards the findings
  file first; otherwise partial output would be appended twice.
