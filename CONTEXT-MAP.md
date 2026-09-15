# Context Map

`claude-tools` is a personal configuration repository for the Claude Code CLI. It is
developer tooling, not a product: everything here is consumed by the CLI on the developer's
own machine, mostly through symlinks created by `setup-symlinks.sh`.

> **Not publishable.** `docs/agents/` holds this repo's project-scoped agent config. Four
> paths under it are gitignored, may contain raw session transcripts, and must never be
> committed, published, or swept into a docs pipeline: `docs/agents/plans/`,
> `docs/agents/plans/implementation-logs/`, `docs/agents/sdlc-review-findings.md`, and
> `docs/agents/pr-summary.md`. See [docs/agents/README.md](./docs/agents/README.md) and
> [docs/agents/PRIVACY.md](./docs/agents/PRIVACY.md).

## Contexts

- [skills](./skills/CONTEXT.md) — slash-command skill definitions (`/sdlc`, `/plan-iteration`, …)
- [agents](./agents/CONTEXT.md) — the `sdlc-*` subagent definitions the skills dispatch
- [scripts](./scripts/CONTEXT.md) — the Ralph loop orchestrator and its pytest suite
- [custom-llm](./custom-llm/CONTEXT.md) — routing Claude Code at non-Anthropic backends
- [statusline](./statusline/CONTEXT.md) — ccstatusline configuration and installer

`demo-gen/` is a self-contained sub-project with its own `docs/llms.md` and `meta/`. It is
deliberately left on its own conventions — treat it as a separate repo that happens to live
in this tree, and read `demo-gen/docs/llms.md` rather than anything here when working in it.

`global/CLAUDE.md` is not a context: it is symlinked *outward* to `~/.claude/CLAUDE.md`, so
it governs every repo on the machine. Change it with that blast radius in mind.

## Relationships

- **skills → agents**: `/sdlc` dispatches the seven `sdlc-*` reviewers in parallel; the other
  skills reference agent files by name for their checklists.
- **skills → scripts**: `/plan-iteration` writes the plans; `scripts/run-next-plan.py` is the
  "run" half that drives them to completion and re-enters `/sdlc`, `/triage`, and
  `/sdlc-doc-writer` through headless Claude sessions.
- **scripts → docs/agents**: the orchestrator's entire state lives under the resolved config
  root — `prd.json`, `progress.md`, the plan files, logs, findings, and PR summary.
- **setup-symlinks.sh → everything**: symlinks `agents/`, `skills/`, `global/CLAUDE.md`, and
  `scripts/` into `~/.claude/`, so an edit here is live immediately with no deploy step.

## Repo layout

```
claude-tools/
  CONTEXT-MAP.md     this file
  CLAUDE.md          repo-scoped instructions + the `## Agent skills` block
  agents/            sdlc-* subagent definitions  → ~/.claude/agents/
  skills/            skill directories            → ~/.claude/skills/
  scripts/           run-next-plan.py + tests     → ~/.claude/scripts/
  global/            machine-wide CLAUDE.md       → ~/.claude/CLAUDE.md
  custom-llm/        claude-code-router launcher
  statusline/        ccstatusline settings + installer
  demo-gen/          self-contained Python CLI sub-project
  sample-projects/   example project-level CLAUDE.md templates
  docs/
    adr/             architecture decision records
    agents/          project-scoped agent config (see the warning above)
    features/        per-feature reference docs
```

## Feature docs

Per-feature reference lives in `docs/features/` and is unchanged by the context split — read
the CONTEXT file for vocabulary and boundaries, the feature doc for detail.

- [features/agents.md](./docs/features/agents.md) — subagent definitions and how to use them
- [features/skills.md](./docs/features/skills.md) — what each skill does
- [features/run-next-plan.md](./docs/features/run-next-plan.md) — the Ralph loop, the SDLC review gate, session-limit handling, the two-audience PR description
- [features/setup.md](./docs/features/setup.md) — `setup-symlinks.sh` and the Desktop variant
- [features/third-party-skills.md](./docs/features/third-party-skills.md) — the upstream engineering skills, their install, and local mods
- [features/custom-llm.md](./docs/features/custom-llm.md) — Ollama / Gemini / OpenAI routing
- [features/demo-gen.md](./docs/features/demo-gen.md) — the demo artifact generator

## Decisions

`docs/adr/` records decisions that were hard to reverse and surprising without context. Read
the ones touching your area before changing it, and say so explicitly if your change
contradicts one.

## Design principles

1. **Symlink-first** — editing here equals editing live. No deploy step, no copy step.
2. **Markdown-native** — agents and skills are prose with frontmatter, read by the CLI.
3. **Portable** — clones to `~/Code/claude-tools` on any macOS/Linux machine; the setup
   script does the rest.
4. **Layout-tolerant** — tooling here reads both the `docs/agents/` and `meta/` layouts,
   because the other repos on the machine are not being migrated. See
   [ADR 0001](./docs/adr/0001-scaffolding-layout-with-dual-read-fallback.md).
5. **This repo defines how to do things**, not an app that does things — the one exception is
   `scripts/` and `demo-gen/`, which are real programs with real tests.

## Tech stack

- **Markdown** — every agent, skill, and doc; the primary artifact of the repo
- **Python 3.10+** — `scripts/run-next-plan.py` (stdlib only) with pytest + ruff; `demo-gen/`
- **Shell (bash)** — `setup-symlinks.sh`, `setup-symlinks-desktop.sh`, `custom-llm/`, `statusline/install.sh`
- **`gh` CLI** — every issue and PR interaction
- **Git** — version control, and the orchestrator's own commit/push surface
