# claude-tools Overview

## Summary

claude-tools is a personal configuration repository for the Claude Code CLI. It stores reusable subagent definitions (`agents/`), slash-command skills (`skills/`), and a global `CLAUDE.md` that enforces consistent development standards across every project on a developer's machine. It is not a product — it is developer tooling.

## Users

- **Individual developer** — the sole user. Clones this repo once per machine, runs `setup-symlinks.sh`, and gains an opinionated, consistent Claude Code environment across all projects.

## Architecture

The repo is a plain directory tree. No build system, no runtime, no server. Every file is either a Markdown configuration file consumed by the Claude Code CLI or a shell script.

```
claude-tools/
  agents/           Subagent .md files → symlinked to ~/.claude/agents/
  skills/           Skill directories  → symlinked to ~/.claude/skills/
  global/           Global CLAUDE.md   → symlinked to ~/.claude/CLAUDE.md
  sample-projects/  Example project-level CLAUDE.md templates
  setup-symlinks.sh One-time bootstrap script
```

`setup-symlinks.sh` creates symlinks from `~/.claude/` into the repo. After that, every `git pull` or local edit to this repo takes effect in Claude Code immediately — no copy step.

## Tech stack

- **Shell (bash)** — `setup-symlinks.sh` only; no other runtime
- **Markdown** — all agent and skill definitions; consumed by Claude Code
- **Git** — version control and sync across machines

## Design principles

1. **Symlink-first** — editing here equals editing live. No deploy step.
2. **Markdown-native** — Claude Code reads `.md` frontmatter for agent metadata; skill files are plain Markdown prose.
3. **Portable** — the repo clones to `~/Code/claude-tools` on any macOS/Linux machine and `setup-symlinks.sh` handles the rest.
4. **No code-generation at repo level** — this repo defines *how to do things*, not an app that *does things*.

