# claude-tools

Personal Claude Code configuration: skills, agents, scripts, and project `CLAUDE.md` templates.

## Contents

```
agents/                   # Subagent definitions (~/.claude/agents/)
  sdlc-accessibility-reviewer.md
  sdlc-code-reviewer.md
  sdlc-design-reviewer.md
  sdlc-doc-writer.md
  sdlc-privacy-reviewer.md
  sdlc-qa-engineer.md
  sdlc-security-reviewer.md
  sdlc-style-reviewer.md
  sdlc-test-reviewer.md

skills/                   # Slash-command skills
  close-iteration/        # /close-iteration  — merge integration PR, clean up branches/plans
  demo/                   # /demo             — HTML + MP4 demo artifacts
  help-docs/              # /help-docs        — customer-facing docs site
  plan-iteration/         # /plan-iteration   — backlog grooming: triage → cluster → plan files
  pr-image-upload/        # /pr-image-upload  — embed screenshots in PRs (private-repo safe)
  rank-backlog/           # /rank-backlog     — GUS backlog nevering analysis
  sdlc/                   # /sdlc             — full dev lifecycle orchestrator
  triage-pr-comments/     # /triage-pr-comments — turn PR review comments into plan files

scripts/                  # Standalone Python scripts
  run-next-plan.py        # Ralph Wiggum loop: runs Claude against meta/plans/prd.json in a loop
  pyproject.toml          # ruff + pytest config for scripts/
  tests/                  # pytest suite for run-next-plan.py

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

docs/                     # Internal project docs (not customer-facing)
  llms.md                 # index of all doc files
  overview.md             # project purpose, architecture, tech stack
  features/               # one .md per feature area

statusline/               # ccstatusline config (Session/Weekly usage %, context tokens, etc.)
  ccstatusline-settings.json
  install.sh              # installs ccstatusline, symlinks config, points Claude Code at it

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

## Status line

```bash
bash statusline/install.sh
```

Installs [ccstatusline](https://github.com/sirmalloc/ccstatusline) (pinned version), symlinks
`statusline/ccstatusline-settings.json` to `~/.config/ccstatusline/settings.json`, and sets
`statusLine.command` in `~/.claude/settings.json` to `ccstatusline`. Edit
`statusline/ccstatusline-settings.json` to change widgets/colors — changes are live immediately
via the symlink. Re-run the script after bumping `CCSTATUSLINE_VERSION` in `install.sh` to
upgrade.

## Ralph Wiggum loop (`scripts/run-next-plan.py`)

Autonomous plan executor. Reads `meta/plans/prd.json` and runs a non-interactive Claude session
that picks the highest-priority unblocked plan, implements it, and loops until all plans are
done or stalled. The Python layer handles attempt tracking, rate-limit retries, stall detection,
and an SDLC review gate; all task-selection intelligence is delegated to Claude.

```bash
# Run from inside any git repo that has meta/plans/prd.json (created by /plan-iteration)
python3 ~/.claude/scripts/run-next-plan.py [options]

Options:
  --restart            Reset in-progress plan(s) to pending and re-run
  --skip-in-progress   Skip in-progress plan; pick next pending
  --dry-run            Print selected plan, command, and prompt — do not invoke Claude
  --integration-branch Override prd.json's integration_branch
```

**Model escalation:** attempts 1–2 use the default model; attempts 3–4 escalate to
`--model sonnet --effort high` (extended thinking); attempt 5 uses `--model opus --effort max`.
Plans that exceed 5 attempts are marked stalled.

**Docker sandbox:** if `meta/ralph.dockerfile` exists in the repo, Claude runs inside a
container built from it. See `meta/ralph.dockerfile.example` for a template.

**SDLC review gate:** once all plans are done/stalled, the loop automatically runs a full
`/sdlc` review of the integration branch, files findings as GitHub issues, triages them into
new plan files, and resumes the loop. Gated by `prd.json`'s `sdlc_review_status` field so it
only ever runs once per prd lifecycle.

Tests: `cd scripts && python3 -m pytest`

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
| close-iteration | `/close-iteration` | Gate-check completion, merge integration PR, close issues, clean up branches and `meta/plans/` |
| demo | `/demo [feature]` | Generate HTML demo script + MP4 walkthrough video |
| help-docs | `/help-docs` | Generate customer-facing UI guide, API reference, and demo gallery |
| plan-iteration | `/plan-iteration` | Groom backlog: triage issues, cluster into workstreams, write plan files to `meta/plans/` |
| pr-image-upload | `/pr-image-upload [PR#] <files>` | Upload screenshots to GitHub and return markdown image tags (private-repo safe) |
| rank-backlog | `/rank-backlog "Team Name"` | Rank GUS backlog items as candidates for nevering |
| sdlc | `/sdlc` | Full SDLC pipeline: planning reviews → implementation → code review → QA → docs |
| triage-pr-comments | `/triage-pr-comments` | Turn open PR reviewer comments into plan files in `meta/plans/` |

## Agents reference

All SDLC agents are prefixed `sdlc-` to avoid name collisions.

| Agent | Purpose |
|---|---|
| sdlc-code-reviewer | DRY/SOLID, correctness, dependency audit |
| sdlc-style-reviewer | Naming, comments, idiomatic style, linting |
| sdlc-security-reviewer | OWASP Top 10, auth/authz, CVEs, injection risks |
| sdlc-privacy-reviewer | GDPR, PII handling, consent flows, data minimization |
| sdlc-accessibility-reviewer | WCAG 2.2 AA, keyboard nav, ARIA, color contrast |
| sdlc-design-reviewer | Design brief adherence, component reuse, spacing/color tokens |
| sdlc-doc-writer | Maintains `docs/features/` and `docs/llms.md` |
| sdlc-qa-engineer | Automated tests, smoke tests, regression checks |
| sdlc-test-reviewer | Test value, edge cases, branch coverage, 90%+ line coverage, FE+BE parity, boundary cases |

## Third-party skills

Several skills in `~/.claude/skills/` come from Matt Pocock's engineering skills collection and
are **not** managed by this repo. Install them separately:

```bash
npx skills add mattpocock/skills -y -g
```

See `docs/features/third-party-skills.md` for the full list and per-project setup instructions.
