# Third-Party Skills

## Overview

Several skills installed in `~/.claude/skills/` come from Matt Pocock's engineering skills
collection (AI Hero). These are **not** managed by this repo — they must be installed separately
and are not symlinked by `setup-symlinks.sh`.

---

## Matt Pocock's Engineering Skills

### Installation

Install all skills globally via the `skills` CLI (requires Node.js):

```bash
npx skills add mattpocock/skills -y -g
```

Full catalog and docs: https://www.aihero.dev/skills  
Source: https://github.com/mattpocock/skills

### Per-project setup

After installing the skills globally, run `/setup-matt-pocock-skills` once inside each repo
that will use them. This writes three config files that the other skills read:

| File | Purpose |
|---|---|
| `docs/agents/issue-tracker.md` | Where issues are tracked and how to interact with them |
| `docs/agents/triage-labels.md` | Label strings for the five triage states |
| `docs/agents/domain.md` | Whether the repo uses a single or multi `CONTEXT.md` layout |

It also adds an `## Agent skills` block to `CLAUDE.md` (or `AGENTS.md`) summarising the above.

### The main workflow

Matt's skills form a connected workflow for taking an idea all the way to shipped issues:

```
/grill-with-docs → /to-prd → /to-issues → /implement (per issue)
```

For bug/request intake: `/triage` → produces agent-ready issues → `/implement`

For ad-hoc architecture work: `/improve-codebase-architecture`

See `/ask-matt` for the full routing guide with branches and context-hygiene rules.

### Installed skills

| Skill | Description |
|---|---|
| `/ask-matt` | Router over all Matt's skills — start here if unsure which to use |
| `/codebase-design` | Vocabulary for designing deep modules; used by other skills |
| `/decision-mapping` | Turn a loose idea into sequenced investigation tickets |
| `/design-an-interface` | Generate multiple radically different interface designs via parallel agents |
| `/diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions |
| `/domain-modeling` | Build/sharpen a project domain model and ubiquitous language |
| `/edit-article` | Edit and improve article drafts |
| `/find-skills` | Help discover and install skills for a given need |
| `/grill-me` | Relentless interview to sharpen a plan — stateless, no codebase needed |
| `/grill-with-docs` | Same relentless interview but stateful — writes `CONTEXT.md` and ADRs |
| `/grilling` | Core interview engine used by other skills |
| `/handoff` | Compact a conversation into a file for pickup in a fresh context window |
| `/implement` | Implement a piece of work from a PRD or set of issues |
| `/improve-codebase-architecture` | Scan codebase for deepening opportunities; pick one to improve |
| `/prototype` | Build a throwaway prototype to answer design questions with runnable code |
| `/qa` | Conversational QA session — user reports bugs, skill files GitHub issues |
| `/review` | Review changes against standards and spec in parallel sub-agents |
| `/scaffold-exercises` | Create exercise directory structures with problems, solutions, explainers |
| `/setup-matt-pocock-skills` | Per-project bootstrap — run once before using other skills in a repo |
| `/tdd` | Test-driven development — write failing test first, then implement |
| `/teach` | Teach a concept over multiple sessions using current directory as workspace |
| `/to-issues` | Break a PRD into independently-grabbable vertical-slice issues |
| `/to-prd` | Turn the current conversation into a PRD and publish to issue tracker |
| `/triage` | Move incoming issues through triage state machine; produce agent-ready briefs |
| `/ubiquitous-language` | Extract DDD-style glossary from conversation; save to `UBIQUITOUS_LANGUAGE.md` |
| `/writing-beats` | Shape an article beat-by-beat, choose-your-own-adventure style |
| `/writing-fragments` | Mine raw fragments and half-thoughts as material for a future article |
| `/writing-great-skills` | Reference for writing skills well — vocabulary and principles |
| `/writing-shape` | Turn raw notes/draft into a publishable article conversationally |

### Local modifications

| Skill | Change |
|---|---|
| `/to-prd` | Step 3 now also applies a `prd` label to the created issue (creates the label if absent) |

If Matt's upstream changes a skill that has a local mod, re-apply the mod manually after updating.

---

## Keeping skills up to date

Re-run the install command to pull the latest version:

```bash
npx skills add mattpocock/skills -y -g
```

Local modifications (see above) must be re-applied manually after updating a modified skill.
