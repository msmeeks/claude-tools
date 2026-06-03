# claude-tools

Personal Claude Code configuration: skills, agents, and project `CLAUDE.md` templates.

## Contents

```
agents/                   # Subagent definitions (~/.claude/agents/)
  accessibility-reviewer.md
  code-reviewer.md
  design-reviewer.md
  doc-writer.md
  privacy-reviewer.md
  qa-engineer.md
  security-reviewer.md
  style-reviewer.md
  test-reviewer.md

skills/                   # Slash-command skills
  demo/                   # /demo  — HTML + MP4 demo artifacts
  help-docs/              # /help-docs  — customer-facing docs site
  pr-image-upload/        # /pr-image-upload  — embed screenshots in PRs
  rank-backlog/           # /rank-backlog  — GUS backlog nevering analysis
  sdlc/                   # /sdlc  — full dev lifecycle orchestrator

global/
  CLAUDE.md               # Global Claude Code instructions (~/.claude/CLAUDE.md)

sample-projects/
  hospitality-schedule/
    CLAUDE.md             # Example project-level CLAUDE.md

custom-llm/               # Route `claude` to Ollama / Gemini / OpenAI via claude-code-router
  README.md
  install.sh              # one-time bootstrap: installs ccr
  claude-byom             # launcher: ./claude-byom <profile>
  configs/                # per-backend config templates (.example.json)
  network/                # Tailscale / SSH / Caddy options for remote Ollama
  deploy/                 # fly.io + AWS recipes for self-hosted Ollama

demo-gen/                 # Python CLI invoked by the /demo skill
  install.sh              # idempotent bootstrap: creates .venv, pip install -e '.[kokoro]'
  demo_gen/               # Python package source
  tests/                  # pytest suite
  pyproject.toml
  meta/                   # BRAND_VOICE.md / DESIGN_BRIEF.md / PRIVACY.md
  help-docs/              # reference example output

setup-symlinks.sh         # Claude CLI setup: symlink repo → ~/.claude (see below)
setup-symlinks-desktop.sh # Claude Desktop setup (macOS): symlink repo → Desktop app (see below)
```

## Quick start — Claude CLI (new machine)

```bash
git clone <this-repo> ~/Code/claude-tools
cd ~/Code/claude-tools
bash setup-symlinks.sh
```

`setup-symlinks.sh` replaces the live files in `~/.claude/skills/`, `~/.claude/agents/`, and
`~/.claude/CLAUDE.md` with symlinks back into this repo. After running it, editing any file here
takes effect in Claude Code immediately — no copy or restart required.

The script backs up any existing file it replaces as `<file>.bak` and skips anything that is
already a symlink.

## Quick start — Claude Desktop (macOS)

```bash
git clone <this-repo> ~/Code/claude-tools
cd ~/Code/claude-tools
bash setup-symlinks-desktop.sh
```

`setup-symlinks-desktop.sh` is the macOS-only variant for the Claude Desktop app. It:

- Symlinks each skill into the Desktop app's skills-plugin directory
  (`~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/…/skills/`)
  and registers each skill in the plugin's `manifest.json` so it appears in the Desktop UI.
- Symlinks agents into `~/.claude/agents/` (same location as the CLI).
- Symlinks `global/CLAUDE.md` to `~/.claude/CLAUDE.md` (same location as the CLI).

**Prerequisites:** Open Claude Desktop at least once before running the script so it can
initialize the skills-plugin directory. After running, restart Claude Desktop for skills to
appear.

To run Claude Code against a non-Anthropic backend (Ollama, Gemini, OpenAI), see `custom-llm/`.

The `/demo` skill delegates to a Python CLI, `demo-gen`, in `demo-gen/`. Bootstrap once with `bash demo-gen/install.sh` (creates `.venv` and `pip install -e '.[kokoro]'`; safe to re-run). See `docs/features/demo-gen.md`.

## Updating

```bash
git pull        # pull latest
# changes are live immediately via symlinks (CLI)
# restart Claude Desktop after pulling to pick up skill changes
git add -A && git commit -m "..." && git push   # push your edits
```

## Adding a new skill

1. Create `skills/<name>/SKILL.md` with the required frontmatter (`name`, `description`).
2. Add any supporting files in the same directory.
3. **CLI:** run `setup-symlinks.sh` to link it (or manually `ln -s`).
   **Desktop (macOS):** run `setup-symlinks-desktop.sh` to link it and register it in
   `manifest.json`, then restart Claude Desktop.
4. Invoke it with `/<name>`.

## Adding a new agent

1. Create `agents/<name>.md` with frontmatter (`name`, `description`, `model`, `tools`).
2. Run `setup-symlinks.sh` or `setup-symlinks-desktop.sh` to link it (or manually `ln -s`).
3. Dispatch it with `Agent(subagent_type="<name>", ...)`.

## Skills reference

| Skill | Invoke | Purpose |
|---|---|---|
| sdlc | `/sdlc` | Full SDLC pipeline: planning reviews → implementation → code review → QA → docs |
| demo | `/demo [feature]` | Generates HTML demo script + MP4 walkthrough video |
| help-docs | `/help-docs` | Generates customer-facing UI guide, API reference, and demo gallery |
| pr-image-upload | `/pr-image-upload [PR#] <files>` | Uploads screenshots to GitHub and returns markdown image tags |
| rank-backlog | `/rank-backlog "Team Name"` | Ranks GUS backlog items as candidates for nevering |

## Agents reference

| Agent | Purpose |
|---|---|
| code-reviewer | DRY/SOLID, correctness, dependency audit |
| style-reviewer | Naming, comments, idiomatic style, linting |
| security-reviewer | OWASP Top 10, auth/authz, CVEs, injection risks |
| privacy-reviewer | GDPR, PII handling, consent flows, data minimization |
| accessibility-reviewer | WCAG 2.2 AA, keyboard nav, ARIA, color contrast |
| design-reviewer | Design brief adherence, component reuse, spacing/color tokens |
| doc-writer | Maintains `docs/features/` and `docs/llms.md` |
| qa-engineer | Automated tests, smoke tests, regression checks |
| test-reviewer | Test value, edge cases, branch coverage, 90%+ line coverage, FE+BE parity, boundary cases |
