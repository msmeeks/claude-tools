# Agents

Subagent definitions the CLI can dispatch as specialist workers. Each file is frontmatter
(name, description, tools) plus a review checklist in prose. `setup-symlinks.sh` symlinks this
directory into `~/.claude/agents/`.

Nine agents: the seven `sdlc-*` reviewers dispatched in parallel by `/sdlc` Phase 3
(`code`, `style`, `security`, `privacy`, `accessibility`, `design`, `test`), plus
`sdlc-qa-engineer` (runs the tests and smoke checks) and `sdlc-doc-writer` (reads and writes
the context and feature docs). Detail in
[../docs/features/agents.md](../docs/features/agents.md).

## Language

**Agent**:
A single-purpose subagent with its own tool allowlist, dispatched by a skill or by the
orchestrator. Returns a report; never commits.
_Avoid_: reviewer bot, worker, assistant

**Reviewer**:
One of the seven `sdlc-*` agents that inspect a diff and report findings. The set is
enumerated in `scripts/run-next-plan.py` as `SDLC_REVIEW_AGENTS` — adding a file here without
adding it there means the Ralph loop never runs it.
_Avoid_: linter (the style reviewer *runs* a linter; it is not one)

**Checklist**:
The body of an agent file: what to look for, in what order, with what severity. The agent's
actual behaviour, since there is no code.
_Avoid_: rules, config

**Round**:
One complete pass of the review gate: all reviewers run, findings are filed as issues, issues
are triaged. Capped — see `MAX_REVIEW_ROUNDS`.
_Avoid_: iteration (that word means the whole plan-then-run cycle), pass

## Boundaries

- Agents read and report; they do not commit, push, or file issues. The dispatching skill or
  the orchestrator owns every side effect.
- Each agent's tool list is deliberately narrow. Widening one is a real decision — the
  reviewers run unattended inside the Ralph loop under `bypassPermissions`.
- `sdlc-doc-writer` is the only agent that writes files, and its targets are the context and
  feature docs.
