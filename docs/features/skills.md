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
| `skills/close-iteration/SKILL.md` | Gate-checks, merges, and cleans up an iteration opened by `/plan-iteration` |
| `skills/plan-iteration/SKILL.md` | Flags untriaged backlog issues for the user, then writes `<config-root>/plans/prd.json` + `<config-root>/plans/<slug>.md` for `run-next-plan.py` to execute |
| `skills/triage-pr-comments/SKILL.md` | Re-opens plans against new PR review comments mid-iteration |

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

#### Headless review contract

`/sdlc review` also serves as a configured review recipe for the Ralph loop's gate (see
[run-next-plan.md](run-next-plan.md) and [ADR 0002](../adr/0002-review-recipe-is-repo-config.md)).
Passing any of these arguments switches it to non-interactive mode; with none, interactive
behaviour is unchanged. Normative text: `skills/sdlc/SKILL.md` and
[#69](https://github.com/msmeeks/claude-tools/issues/69).

| Argument | Meaning |
|---|---|
| `--range <git range>` | Review `git diff <range>`; no scoping questions |
| `--only <id[,id...]>` | Run only these reviewers; several ids run concurrently, one alone. Unknown id prints `UNSUPPORTED: <id>` and reviews nothing |
| `--report-only` | Never edit files or ask questions; no fix pass |
| `--out <file>` | Append `## <title>` finding blocks (severity, reviewer id, body); no GitHub issues |
| `--registry yes\|no`, `--spec <issues\|path>` | Ignored by `/sdlc` (used by other skills implementing the contract) |

Output: `<reviewed>id</reviewed>` on its own line once a reviewer's findings are written
(`SKIPPED: id: <reason>` first for a reviewer that does not apply), and `REVIEW_DONE` last.
The caller records a reviewer complete only from its `<reviewed>` line.

### demo

Produces two artifacts per feature: a styled HTML demo script and an MP4 video. Screenshots are captured via a headless Chrome CDP session (Node.js, no external packages beyond built-in WebSocket). Video is assembled with Pillow (text rendering on PNG frames) + ffmpeg (encoding and concatenation). If `demo-gen` is installed at `~/Code/demo-generator/.venv/bin/demo-gen`, the skill delegates to that CLI instead.

Output paths: `help-docs/demos/features/<name>.html` and `help-docs/demos/features/<name>.mp4`.

### help-docs

Generates the full `help-docs/` tree: `ui/index.html` (non-technical user guide), `api/index.html` (developer API reference), and `demos/index.html` (gallery). Reads `docs/agents/BRAND_VOICE.md` (or `meta/BRAND_VOICE.md` in un-migrated repos) and `docs/` before writing. After generating UI docs, automatically invokes `/demo` for each feature section.

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
warnings for confirmation, checks spec issue coverage, then promotes and merges the
integration PR, closes linked issues, and deletes branches/worktrees.

The hard-blocker check on `sdlc_review_status` treats a transient `pending` reading as
potentially benign, not automatically a stop-the-run failure: because
`run-next-plan.py`'s incremental review gate legitimately cycles
`complete → pending → complete` across rounds (a re-armed round for newly-appended plans),
seeing `pending` here means either the runner is still mid-round (a real blocker — wait
for it to finish) or, contextually, that a round already flipped back. The pass condition
itself is unchanged: `complete` with no remaining eligible plans.

The `Closes` list assembled for the PR body is compiled from **`done` plans only** —
`stalled` plans contributed no work, so their linked issues are deliberately left off (and
therefore left open after merge) rather than silently marked resolved. `sdlc_finding_issues`
is added on top of the done-plan issues so SDLC findings always auto-close on merge. The
closing report's `Issues left open:` line surfaces exactly the issues this exclusion leaves
behind, tying back to the stalled-plan warnings raised earlier in the run.

`<config-root>/plans/` is removed as part of Step 4, committed and pushed on the integration branch
*before* the SDLC findings review and PR-promotion steps and *before* the PR is merged
(Step 8) — this lets the removal commit pass through the same diff-based review as the
rest of the iteration's work, and ride along in the normal merge commit instead of
requiring a separate direct push to the default branch afterward. Post-merge cleanup
(Step 9) only closes spec issues, deletes branches/worktrees, and pulls the default branch
before deleting the local integration branch; it no longer touches `<config-root>/plans/`.

### plan-iteration

Backlog grooming entry point: checks every open issue carries a state label, groups the
`ready-for-agent` ones into logical clusters, and writes `<config-root>/plans/<slug>.md` plan files
plus `<config-root>/plans/prd.json` for `run-next-plan.py` (see
[run-next-plan.md](run-next-plan.md)) to drive to completion.

The plan-review agents in Step 6 and `review` mode come from `plan_review.reviewers` in
`<config-root>/ralph.json` when that file exists (default: security, privacy, accessibility,
design). A configured name that is not an installed agent stops the run rather than being
skipped. See the **Review recipe config** section of [run-next-plan.md](run-next-plan.md).

Every roster agent is always dispatched, whatever the change looks like. Each reply is recorded as one of its findings, `no findings`, `N/A: <reason>` or `ERROR: <reason>`, and `## Pre-Implementation Review` is never omitted, so a skipped reviewer is visible. Design covers UI, CLI and API surfaces; accessibility covers rendered UI, generated HTML, published docs and a narrow terminal-output check, and is N/A for APIs and backend-only changes. `/triage-pr-comments` Step 5 reads the same roster and follows the same rule.

It never triages. `/triage` is user-invoked (`disable-model-invocation`), so no skill or
headless session can call it. Issues are labeled by whoever files them (the "Filing issues"
rule in `global/CLAUDE.md`); any open issue with no state label (or `needs-triage`) is listed
back to the user with the `/triage #N …` command to run, and the skill stops unless the user
chooses to plan only what is already `ready-for-agent`.

When `prd.json` already exists (re-running against a partially-worked iteration), it merges
rather than overwrites: an existing `plans[]` entry for the same `file` keeps its `status`
and `attempts`, and — critically — **every existing top-level key is preserved**, not just
`plans[]`. This includes `last_reviewed_sha`, `sdlc_review_status`, `sdlc_finding_issues`,
`sdlc_review_completed_agents`, and `pr_number`. Dropping any of these would silently break
the SDLC review gate's incremental (per-round) review — e.g. losing `last_reviewed_sha`
stalls the re-arm check on the next round.

Step 8 creates the integration branch with an empty starter commit
(`chore: start iteration <slug> (Refs #N, #M)`) before pushing, because `gh pr create`
rejects a branch with no commits ahead of the base. The commit carries plain `Refs` (not
`Closes`) for every plan issue so `/close-iteration`'s untraceable-commit check passes and no
issue closes before merge.

### triage-pr-comments

Reacts to new PR review comments mid-iteration by re-opening the affected plan(s): resets
the matching `plans[]` entry's `status` to `pending` and `attempts` to `0` so the fix gets
picked back up by the loop. This entry-level reset is sufficient on its own — the skill
must **not** touch the top-level `sdlc_review_status` (or any other top-level `prd.json`
key). `run-next-plan.py`'s incremental-review re-arm already detects the new pending plan
and re-runs the gate scoped to `last_reviewed_sha..HEAD`; a manual `sdlc_review_status`
reset here would either be redundant or fight the gate's own re-arm bookkeeping. Like
`/plan-iteration`, it must preserve every existing top-level `prd.json` key when rewriting
the file — only `plans[]` entries change.

### Adding a new skill

1. Create `skills/<name>/SKILL.md` with at minimum `name` and `description` in the YAML frontmatter.
2. Add any supporting files (scripts, templates) in the same directory.
3. Run `setup-symlinks.sh` (or `ln -s skills/<name> ~/.claude/skills/<name>`).
4. Invoke with `/<name>` in Claude Code.

