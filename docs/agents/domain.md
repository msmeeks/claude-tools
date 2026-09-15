# Domain Docs

How the engineering skills should consume this repo's domain documentation.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — this repo is **multi-context**. The map lists one
  `CONTEXT.md` per area (`skills/`, `agents/`, `scripts/`, `custom-llm/`, `statusline/`).
  Read the ones relevant to the topic, not all of them.
- **`docs/adr/`** — read the ADRs that touch the area you are about to work in.
- **`docs/features/<name>.md`** — per-feature reference detail, linked from the map. The
  CONTEXT files give vocabulary and boundaries; the feature docs give mechanics.

`demo-gen/` is a self-contained sub-project that keeps its own `docs/llms.md` and `meta/`.
When working in it, read that instead.

If a file named here does not exist in some other repo, proceed silently — do not flag its
absence or propose creating it upfront.

## File structure

```
/
├── CONTEXT-MAP.md              ← multi-context index
├── CLAUDE.md                   ← repo instructions + the `## Agent skills` block
├── skills/CONTEXT.md
├── agents/CONTEXT.md
├── scripts/CONTEXT.md
├── custom-llm/CONTEXT.md
├── statusline/CONTEXT.md
└── docs/
    ├── adr/                    ← repo-wide decisions
    ├── agents/                 ← this directory (see README.md — partly non-publishable)
    └── features/
```

## Use the glossary's vocabulary

When your output names a domain concept — an issue title, a plan slug, a test name, a
hypothesis — use the term as defined in the relevant `CONTEXT.md`, and avoid the synonyms
each glossary explicitly lists. A concept missing from the glossary is a signal: either you
are inventing language this project does not use, or there is a real gap worth recording.

## Flag ADR conflicts

If your output contradicts an existing ADR, say so explicitly rather than silently overriding
it:

> _Contradicts ADR-0001 (dual-read config root) — but worth reopening because…_
