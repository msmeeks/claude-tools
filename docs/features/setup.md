# Setup and Bootstrap

## Summary

Two installer scripts wire this repo into Claude:

| Script | Target | Platform |
|---|---|---|
| `setup-symlinks.sh` | Claude CLI (`~/.claude/`) | Any OS |
| `setup-symlinks-desktop.sh` | Claude Desktop app | **macOS only** |

Both are idempotent — safe to re-run. They back up any real file they replace as `<file>.bak`
and skip destinations that are already symlinks.

---

## `setup-symlinks.sh` — Claude CLI

### Users / Use Cases

- **Developer (new machine)** — runs once after cloning to activate all agents, skills, and the
  global `CLAUDE.md` in Claude Code.
- **Developer (ongoing)** — runs `git pull`; changes are live immediately via symlinks.

### What it does

Three passes:

1. **Skills** — `skills/*/` → `~/.claude/skills/<name>` (directory symlinks)
2. **Agents** — `agents/*.md` → `~/.claude/agents/<name>.md` (file symlinks)
3. **Global** — `global/CLAUDE.md` → `~/.claude/CLAUDE.md` (file symlink)

### First-time setup

```bash
git clone <this-repo> ~/Code/claude-tools
cd ~/Code/claude-tools
bash setup-symlinks.sh
```

### What `~/.claude/` looks like after setup

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

---

## `setup-symlinks-desktop.sh` — Claude Desktop (macOS only)

### Users / Use Cases

- **macOS developer using the Claude Desktop app** — runs once to install skills into the
  Desktop app's skills-plugin and wire up agents + `CLAUDE.md`.

### Prerequisites

Open Claude Desktop at least once before running. The app must have initialized the
skills-plugin directory (`~/Library/Application Support/Claude/local-agent-mode-sessions/
skills-plugin/`) before the script can find it.

### What it does

1. **Skills** — symlinks each `skills/*/` directory into the Desktop app's skills-plugin
   directory and upserts an entry in the plugin's `manifest.json` (the registry the Desktop
   app reads to discover and display skills). The `description` field is parsed automatically
   from each skill's `SKILL.md` frontmatter.
2. **Agents** — symlinks `agents/*.md` → `~/.claude/agents/<name>.md` (same as CLI).
3. **Global** — symlinks `global/CLAUDE.md` → `~/.claude/CLAUDE.md` (same as CLI).

### Skills plugin path

```
~/Library/Application Support/Claude/
  local-agent-mode-sessions/
    skills-plugin/
      <plugin-uuid>/
        <session-uuid>/
          manifest.json       ← skill registry (updated by the script)
          skills/
            sdlc/             → ~/Code/claude-tools/skills/sdlc/
            ... (one symlink per skill)
```

The two UUIDs are assigned by the Desktop app; the script finds them dynamically.

### First-time setup

```bash
git clone <this-repo> ~/Code/claude-tools
cd ~/Code/claude-tools
bash setup-symlinks-desktop.sh
# Restart Claude Desktop for skills to appear in the UI
```

### After adding a new skill

Re-run `setup-symlinks-desktop.sh` to create the symlink and add the manifest entry, then
restart Claude Desktop.

---

## Shared behaviour

### Link logic (both scripts)

```bash
link() {
  if [[ -L "$dst" ]];   then skip          # already a symlink
  elif [[ -e "$dst" ]]; then backup + link  # real file → move to .bak, then link
  else                       link           # nothing there → create symlink
  fi
}
```

### Updating

```bash
git pull   # pull latest; CLI changes are live immediately via symlinks
           # Desktop: restart Claude Desktop to pick up skill changes
```

### Backup files

If a real (non-symlink) file existed at any destination before the script ran, it is renamed
to `<file>.bak`. These can be deleted once the new symlinks are confirmed working.

---

## Key Files

| File | Purpose |
|---|---|
| `setup-symlinks.sh` | CLI bootstrap; creates symlinks in `~/.claude/` |
| `setup-symlinks-desktop.sh` | Desktop bootstrap (macOS); links skills into Desktop app + updates manifest |
| `global/CLAUDE.md` | Global Claude standards; linked to `~/.claude/CLAUDE.md` |
| `sample-projects/hospitality-schedule/CLAUDE.md` | Example project-level `CLAUDE.md` to copy into new projects |
