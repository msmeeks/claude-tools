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

skills/                   # Slash-command skills (~/.claude/skills/)
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

setup-symlinks.sh         # One-time setup: symlink repo → ~/.claude (see below)
```

## Quick start (new machine)

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

## Updating

```bash
git pull        # pull latest
# changes are live immediately via symlinks
git add -A && git commit -m "..." && git push   # push your edits
```

## Adding a new skill

1. Create `skills/<name>/SKILL.md` with the required frontmatter (`name`, `description`).
2. Add any supporting files in the same directory.
3. Run `setup-symlinks.sh` to link it (or manually `ln -s`).
4. Invoke it in Claude Code with `/<name>`.

## Adding a new agent

1. Create `agents/<name>.md` with frontmatter (`name`, `description`, `model`, `tools`).
2. Run `setup-symlinks.sh` to link it (or manually `ln -s`).
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
| code-reviewer | DRY/SOLID, test coverage, correctness, dependency audit |
| style-reviewer | Naming, comments, idiomatic style, linting |
| security-reviewer | OWASP Top 10, auth/authz, CVEs, injection risks |
| privacy-reviewer | GDPR, PII handling, consent flows, data minimization |
| accessibility-reviewer | WCAG 2.2 AA, keyboard nav, ARIA, color contrast |
| design-reviewer | Design brief adherence, component reuse, spacing/color tokens |
| doc-writer | Maintains `docs/features/`, `CHANGELOG.md`, `docs/llms.md` |
| qa-engineer | Automated tests, smoke tests, regression checks |
