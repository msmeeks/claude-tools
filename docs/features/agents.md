# Agents

## Summary

The `agents/` directory contains subagent definitions that Claude Code can dispatch as specialist reviewers or workers. Each agent is a focused, narrow expert — it reads code, runs shell commands, and produces a structured finding report. Agents are called by the `/sdlc` skill and can also be dispatched manually.

## Users / Use Cases

- **Developer** — invokes agents indirectly via `/sdlc` during code review and QA phases, or directly with `Agent(subagent_type="<name>", ...)` in Claude Code.

## Technologies

- **Markdown with YAML frontmatter** — the format Claude Code uses to parse agent metadata (name, description, model, allowed tools)
- **Claude Sonnet** — the model used by all agents (`model: sonnet` in frontmatter)

## Technical Overview

Each file in `agents/` is a standalone `.md` with a YAML frontmatter block followed by a natural-language system prompt. The frontmatter declares the agent's name, a description used for routing, the model to use, and the subset of tools it is allowed to call. Claude Code reads these files from `~/.claude/agents/` and makes them available for dispatch. Agents run in isolated sub-sessions and return their output as text.

## Key Files

| File | Purpose |
|---|---|
| `agents/code-reviewer.md` | DRY/SOLID, correctness, third-party dependency audit |
| `agents/style-reviewer.md` | Naming, comments, idiomatic constructs, linting compliance |
| `agents/security-reviewer.md` | OWASP Top 10, auth/authz, CVEs, injection risks; has WebFetch + WebSearch tools |
| `agents/privacy-reviewer.md` | GDPR, PII handling, consent flows, data minimization |
| `agents/accessibility-reviewer.md` | WCAG 2.2 AA, keyboard navigation, ARIA, color contrast |
| `agents/design-reviewer.md` | Design brief adherence, component reuse, spacing/color tokens |
| `agents/doc-writer.md` | Creates/updates docs/features/ and docs/llms.md |
| `agents/qa-engineer.md` | Runs automated tests, lint, API smoke tests, regression checks |
| `agents/test-reviewer.md` | Test value, edge cases, branch coverage, 90%+ line coverage target |

## Technical Detail

### Frontmatter schema

```yaml
---
name: <agent-name>           # identifier used in Agent() dispatch call
description: <string>        # used by Claude to route the right agent
model: sonnet                # always sonnet for these agents
tools:                       # whitelist of tools the agent may call
  - Read
  - Glob
  - Grep
  - Bash
---
```

`security-reviewer` additionally has `WebFetch` and `WebSearch` to enable CVE lookups. `doc-writer` has `Write` and `Edit` to create and modify files. `rank-backlog` uses MCP tools (`mcp__gus__*`) and sets `disable-model-invocation: true` to run tool-only workflows.

### Dispatch pattern

Agents are dispatched as parallel sub-sessions:

```
Agent(subagent_type="code-reviewer"): Review src/foo.py for DRY/SOLID and correctness.
Agent(subagent_type="security-reviewer"): Review src/foo.py for OWASP Top 10.
```

All review agents (code, style, security, privacy, accessibility, design, test) are designed to run in parallel. The `/sdlc` skill orchestrates this in Phase 3.

### Output format conventions

Each agent reports findings grouped by severity. The severity vocabulary differs by domain:
- Code/style/test: **Critical** → **Major** → **Minor**
- Security: **Critical** → **High** → **Medium** → **Informational**
- QA: **PASS / FAIL** banner followed by section-by-section results

**Phase 3/4 handoff mode:** all 8 Phase 3/4 review-and-QA agents (the seven review agents above plus `sdlc-qa-engineer`), when dispatched with a literal scratchpad path by `/sdlc` Phase 3/4, write findings as compressed JSON via `Write` instead of returning prose. See [sdlc-review-handoff.md](sdlc-review-handoff.md).

### Adding a new agent

1. Create `agents/<name>.md` with valid frontmatter (`name`, `description`, `model`, `tools`).
2. Write the system prompt body below the frontmatter `---` separator.
3. Run `setup-symlinks.sh` (or `ln -s`) to make it available at `~/.claude/agents/<name>.md`.
4. Dispatch with `Agent(subagent_type="<name>", ...)`.

