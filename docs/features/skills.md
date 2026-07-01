# Skills

## Summary

The `skills/` directory contains slash-command skill definitions that extend Claude Code with project-level commands. Each skill is a directory containing a `SKILL.md` that describes what the command does and how to execute it. Skills are invoked in Claude Code with `/<name>` and can orchestrate multiple agents, run shell commands, and produce file artifacts.

## Users / Use Cases

- **Developer** — types `/<skill-name>` in Claude Code to trigger a multi-step workflow that would otherwise require many manual instructions.

## Technologies

- **Markdown with YAML frontmatter** — `SKILL.md` files; same format as agents but for commands rather than sub-sessions
- **Bash** — `pr-image-upload` skill ships a companion shell script (`pr-image-upload.sh`)
- **GitHub CLI (`gh`)** — used by `pr-image-upload` for release asset uploads
- **GUS MCP servers** (`mcp__gus__*`, `mcp__gus-mcp__*`) — used by `rank-backlog` for Salesforce GUS integration
- **Pillow + ffmpeg** — used by `demo` for MP4 video generation
- **Node.js CDP** — used by `demo` for headless Chrome screenshot capture

## Technical Overview

Skills live at `~/.claude/skills/<name>/` (symlinked from this repo). When the developer types `/<name>`, Claude Code loads `SKILL.md` as the instruction set for that command and executes the workflow described within it. Skills can dispatch agents, call MCP tools, write files, and run shell commands. They are not programs — they are structured natural-language workflows.

## Key Files

| File | Purpose |
|---|---|
| `skills/sdlc/SKILL.md` | Full SDLC pipeline: planning → implementation → review → QA → docs |
| `skills/demo/SKILL.md` | Generates HTML demo script + MP4 walkthrough video per feature |
| `skills/help-docs/SKILL.md` | Generates customer-facing UI guide, API reference, and demo gallery |
| `skills/pr-image-upload/SKILL.md` | Uploads screenshots to GitHub as release assets; returns markdown image tags |
| `skills/pr-image-upload/pr-image-upload.sh` | Shell implementation for the upload workflow |
| `skills/rank-backlog/SKILL.md` | GUS backlog analysis and nevering-candidate ranking; outputs CSV |
| `skills/close-iteration/skill.md` | Gate-checks, merges, and cleans up an iteration opened by `/plan-iteration` |

## Technical Detail

### sdlc

The central workflow orchestrator. Divides work into four phases invocable independently:

| Phase flag | What runs |
|---|---|
| (none) | Full pipeline |
| `plan` | doc-writer context load + security, privacy, a11y, design planning reviews |
| `review` | All 7 review agents in parallel |
| `qa` | qa-engineer agent |
| `docs` | doc-writer update |

On first use in a project, `/sdlc` bootstraps `docs/` via `doc-writer` before anything else. The checklist at the bottom of `SKILL.md` serves as a definition of done.

### demo

Produces two artifacts per feature: a styled HTML demo script and an MP4 video. Screenshots are captured via a headless Chrome CDP session (Node.js, no external packages beyond built-in WebSocket). Video is assembled with Pillow (text rendering on PNG frames) + ffmpeg (encoding and concatenation). If `demo-gen` is installed at `~/Code/demo-generator/.venv/bin/demo-gen`, the skill delegates to that CLI instead.

Output paths: `help-docs/demos/features/<name>.html` and `help-docs/demos/features/<name>.mp4`.

### help-docs

Generates the full `help-docs/` tree: `ui/index.html` (non-technical user guide), `api/index.html` (developer API reference), and `demos/index.html` (gallery). Reads `meta/BRAND_VOICE.md` and `docs/` before writing. After generating UI docs, automatically invokes `/demo` for each feature section.

### pr-image-upload

Uploads local PNG/JPEG files as assets on a permanent `pr-assets` prerelease in the current GitHub repo, then returns `![alt](url)` markdown lines. Uses `releases/download` URLs rather than `raw.githubusercontent.com` because the latter 404s on private repos. The companion `pr-image-upload.sh` handles the `gh release upload` call with `--clobber` support.

Usage: `/pr-image-upload [PR#] <file1> [file2 ...]`

### rank-backlog

Analyzes a GUS team's backlog for nevering candidates. Two modes:

- **Automatic** (preferred): requires `gus-mcp` MCP server; discovers team members and retrieves backlog via natural language query (`query_gus_records`).
- **Manual fallback**: requires `--users=email1,email2` flag; queries each member individually via `gus_work_list`.

Scoring algorithm weights: epic completed/nevered (+100), zero customer impact (+80), low impact + old (+60), age > 365 days (+20), inactivity > 180 days (+15). Output is a ranked CSV file in the current working directory.

### close-iteration

The bookend to `/plan-iteration`. Verifies hard blockers (all plans terminal, SDLC review
complete, findings addressed, no merge conflicts, smoke test passes), surfaces soft
warnings for confirmation, checks PRD issue coverage, then promotes and merges the
integration PR, closes linked issues, and deletes branches/worktrees.

`meta/plans/` is removed as part of Step 4, committed and pushed on the integration branch
*before* the SDLC findings review and PR-promotion steps and *before* the PR is merged
(Step 8) — this lets the removal commit pass through the same diff-based review as the
rest of the iteration's work, and ride along in the normal merge commit instead of
requiring a separate direct push to the default branch afterward. Post-merge cleanup
(Step 9) only closes PRD issues, deletes branches/worktrees, and pulls the default branch
before deleting the local integration branch; it no longer touches `meta/plans/`.

### Adding a new skill

1. Create `skills/<name>/SKILL.md` with at minimum `name` and `description` in the YAML frontmatter.
2. Add any supporting files (scripts, templates) in the same directory.
3. Run `setup-symlinks.sh` (or `ln -s skills/<name> ~/.claude/skills/<name>`).
4. Invoke with `/<name>` in Claude Code.

