# Setup and Bootstrap

## Summary

`setup-symlinks.sh` is a one-time bootstrap script that wires this repo into Claude Code by replacing the live files in `~/.claude/` with symlinks back into the repo. After running it, every edit to this repo is immediately live in Claude Code — no copy step, no restart.

## Users / Use Cases

- **Developer (new machine)** — runs the script once after cloning to activate all agents, skills, and the global `CLAUDE.md`.
- **Developer (ongoing)** — runs `git pull` to pick up updates; changes are live immediately via symlinks.

## Technologies

- **Bash** — the script itself (`set -euo pipefail`)
- **Git** — version control; the repo is the source of truth for all Claude Code configuration

## Technical Overview

The script iterates over `skills/*/` and `agents/*.md`, creating a symlink at `~/.claude/skills/<name>` and `~/.claude/agents/<name>.md` respectively for each entry. It also links `global/CLAUDE.md` → `~/.claude/CLAUDE.md`. Before creating a symlink it checks: if the destination is already a symlink it skips it; if it is a real file it moves it to `<file>.bak` first. The script is idempotent — safe to re-run.

## Key Files

| File | Purpose |
|---|---|
| `setup-symlinks.sh` | Bootstrap script; creates all symlinks in `~/.claude/` |
| `global/CLAUDE.md` | Global Claude Code standards; symlinked to `~/.claude/CLAUDE.md` |
| `sample-projects/hospitality-schedule/CLAUDE.md` | Example project-level `CLAUDE.md` to copy into new projects |

## Technical Detail

### Link logic

```bash
link() {
  if [[ -L "$dst" ]];   then skip          # already a symlink
  elif [[ -e "$dst" ]]; then backup + link  # real file → move to .bak, then link
  else                       link           # nothing there → create symlink
  fi
}
```

Three passes:
1. Skills: `skills/*/` → `~/.claude/skills/<name>` (directory symlinks)
2. Agents: `agents/*.md` → `~/.claude/agents/<name>.md` (file symlinks)
3. Global: `global/CLAUDE.md` → `~/.claude/CLAUDE.md` (file symlink)

### First-time setup on a new machine

```bash
git clone <this-repo> ~/Code/claude-tools
cd ~/Code/claude-tools
bash setup-symlinks.sh
```

### Updating

```bash
git pull          # pull latest; changes are live immediately via symlinks
```

To push local edits back:
```bash
git add agents/my-agent.md
git commit -m "Add my-agent"
git push
```

### Adding a new agent or skill after initial setup

Option A — re-run the script (idempotent, safe):
```bash
bash setup-symlinks.sh
```

Option B — manual one-liner:
```bash
# Agent
ln -s ~/Code/claude-tools/agents/new-agent.md ~/.claude/agents/new-agent.md

# Skill
ln -s ~/Code/claude-tools/skills/new-skill ~/.claude/skills/new-skill
```

### What ~/.claude/ looks like after setup

```
~/.claude/
  CLAUDE.md               → ~/Code/claude-tools/global/CLAUDE.md
  agents/
    code-reviewer.md      → ~/Code/claude-tools/agents/code-reviewer.md
    ... (one symlink per agent)
  skills/
    sdlc/                 → ~/Code/claude-tools/skills/sdlc/
    ... (one symlink per skill)
```

### Backup files

If a real (non-symlink) file existed at any destination before the script ran, the script renames it to `<file>.bak`. These can be deleted once the new symlinks are confirmed working.

