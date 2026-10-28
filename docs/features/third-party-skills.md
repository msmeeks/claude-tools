# Third-Party Skills

## Overview

Several skills installed in `~/.claude/skills/` come from Matt Pocock's engineering skills
collection (AI Hero). These are **not** managed by this repo — they must be installed separately
and are not symlinked by `setup-symlinks.sh`.

---

## Matt Pocock's Engineering Skills

### Installation

Installing is a human step, on each machine. Reviewed upstream commit: `5beb35b` (plugin v1.3.1).

#### Plugin (current)

Run in a shell:

```bash
claude plugin install mattpocock-skills@claude-plugins-official
```

The plugin auto-updates and `claude plugin install`/`marketplace` expose no way to pin a version
or turn that off. An upstream change therefore lands as live prompt text in every repo before
anyone reviews it. After each update, compare `claude plugin list` (prints the installed
version) against the reviewed baseline above and re-run the supply-chain review before trusting
a newer version. Whether its skills resolve bare (`/tdd`) or namespaced
(`/mattpocock-skills:tdd`) is not verified here; this repo's prompts keep the bare names.

#### skills.sh (June install, legacy)

Run in a shell (requires Node.js). Unpinned; add `-y` only if you have already reviewed the source:

```bash
npx skills add mattpocock/skills -g
```

If both installs are present, remove one. Which wins is not guaranteed, so don't rely on it.

#### Supply-chain review

Plugin skills run with the session's full permissions, and the Ralph runner uses
`bypassPermissions`. Before the first install and on each update, read the plugin source:
`hooks/`, `.mcp.json`, scripts and `allowed-tools`, looking for network or `curl | sh` calls.
Check that the marketplace entry resolves to `github.com/mattpocock/skills`; that is a
check, not a claim the marketplace is vetted. Pin a version if the marketplace allows it.

Links:

- [Skills catalog and docs (AI Hero)](https://www.aihero.dev/skills)
- [Source repository (mattpocock/skills)](https://github.com/mattpocock/skills)

### Per-project setup

After installing the skills globally, run `/setup-matt-pocock-skills` once inside each repo
that will use them. This writes three config files that the other skills read:

| File | Purpose |
|---|---|
| `docs/agents/issue-tracker.md` | Where issues are tracked and how to interact with them |
| `docs/agents/triage-labels.md` | Label strings for the five triage states |
| `docs/agents/domain.md` | Whether the repo uses a single or multi `CONTEXT.md` layout (upstream now says `GLOSSARY.md`; see below) |

It also adds an `## Agent skills` block to `CLAUDE.md` (or `AGENTS.md`) summarising the above.

### The main workflow

Matt's skills form a connected workflow for taking an idea all the way to shipped issues:

```text
/grill-with-docs → /to-spec → /to-tickets → /implement (per ticket)
```

Older installs call these `/to-prd` and `/to-issues`.

For bug/request intake: `/triage` → produces agent-ready issues → `/implement`

For ad-hoc architecture work: `/improve-codebase-architecture`

See `/ask-matt` for the full routing guide with branches and context-hygiene rules.

#### Renamed upstream

Single source of truth for the rename map; other docs link here.

| June name (skills.sh) | Current name (plugin) | Notes |
|---|---|---|
| `/to-prd` | `/to-spec` | Applies `ready-for-agent`, no `prd` label |
| `/to-issues` | `/to-tickets` | Writes a `## Parent` section |
| `CONTEXT.md` | `GLOSSARY.md` | Upstream rename; this repo keeps `CONTEXT.md` (see #84) |
| `/qa` | Removed upstream | skills.sh install only; use the `sdlc-qa-engineer` agent otherwise |
| `/review` | `/code-review` | Replaced upstream |
| `/resolving-merge-conflicts` | Removed upstream | skills.sh install only |

In this repo "spec" is the new term; the identifiers `prd_issue` and `prd.json` keep their names.

### Skills

New name first, June name in parentheses.

| Skill | Description |
|---|---|
| `/ask-matt` | Router over all Matt's skills — start here if unsure which to use |
| `/code-review` (`/review`) | Review changes against standards and spec |
| `/codebase-design` | Vocabulary for designing deep modules; used by other skills |
| `/diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions |
| `/domain-modeling` | Build/sharpen a project domain model and ubiquitous language |
| `/grill-me` | Relentless interview to sharpen a plan — stateless |
| `/grill-with-docs` | Stateful interview — writes the glossary (`GLOSSARY.md`; `CONTEXT.md` on older installs) and ADRs |
| `/grilling` | Core interview engine used by other skills |
| `/handoff` | Compact a conversation into a file for a fresh context window |
| `/implement` | Implement a piece of work from a spec or set of tickets |
| `/implement-spec` | Implement the result of `/to-spec` and `/to-tickets` (new upstream) |
| `/improve-codebase-architecture` | Scan for deepening opportunities; pick one |
| `/pr` | Write a PR body (new upstream) |
| `/prototype` | Throwaway prototype to answer design questions |
| `/research` | Research a question against primary sources into a Markdown file (new upstream) |
| `/retro` | Retrospective on a coding session (new upstream) |
| `/setup-matt-pocock-skills` | Per-project bootstrap — run once before using other skills in a repo |
| `/tdd` | Test-driven development — failing test first |
| `/teach` | Teach a concept over multiple sessions |
| `/to-spec` (`/to-prd`) | Turn the conversation into a spec and publish it to the issue tracker |
| `/to-tickets` (`/to-issues`) | Break a spec into vertical-slice tickets |
| `/triage` | Move incoming issues through the triage state machine |
| `/wayfinder` | Plan huge work as a map of decision tickets (new upstream) |
| `/wizard` | Generate a bash wizard for human-only steps (new upstream) |
| `/qa` | skills.sh install only; removed upstream |
| `/resolving-merge-conflicts` | skills.sh install only; removed upstream |

The June install also carries writing and utility skills (`/edit-article`, `/writing-*`,
`/scaffold-exercises`, `/ubiquitous-language`, `/design-an-interface`) that the plugin no longer ships.

### Local modifications

None. A plugin update would silently overwrite any local edit, so don't make them; put
behaviour changes in this repo's own skills instead. (`/plan-iteration` and `/close-iteration`
find the parent spec via `## Parent` and accept the legacy `prd` label.)

---

## Keeping skills up to date

Review the source diff first (see Supply-chain review), then update.

The plugin also updates itself unpinned (see Plugin (current)): run `claude plugin list`,
compare the version against the reviewed baseline (`5beb35b`, v1.3.1), and review the diff
before relying on anything newer.

Plugin, in a shell:

```bash
claude plugin update mattpocock-skills@claude-plugins-official
```

skills.sh, in a shell:

```bash
npx skills add mattpocock/skills -g
```
