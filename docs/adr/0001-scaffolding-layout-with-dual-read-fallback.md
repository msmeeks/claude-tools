# Adopt the upstream scaffolding layout, and read the old one forever

Matt Pocock's engineering skills — installed as siblings in `~/.claude/skills/` — expect
`CONTEXT.md` / `CONTEXT-MAP.md`, `docs/adr/`, `docs/agents/{issue-tracker,triage-labels,domain}.md`,
and an `## Agent skills` block in the root agent-instructions file. claude-tools had put all
project-scoped config under `meta/` and indexed context in `docs/llms.md` + `docs/overview.md`.
The two systems shared no files, so a repo set up for one was invisible to the other, and
`bnb-quickstart` needed one authoritative answer for what a new repo contains.

**Decision: defer to the upstream layout.** This repo's project-scoped config now lives under
`docs/agents/`, context is indexed by `CONTEXT-MAP.md` plus a per-area `CONTEXT.md`, and
decisions live here in `docs/adr/`. `docs/llms.md` and `docs/overview.md` are gone.

**Decision: the tooling reads both layouts, permanently.** The other repos under `~/Code` are
not being migrated, and `global/CLAUDE.md` is symlinked to `~/.claude/CLAUDE.md`, so it
governs every repo on the machine — an unqualified "use `docs/agents/`" would make skills in
unrelated projects stop finding their `meta/`-rooted files and improvise a location.
`scripts/run-next-plan.py` resolves the config root per repo, and the skills that hard-stop on
a missing context index accept either.

## Consequences

- **A repo carrying both roots is refused, not resolved.** The orchestrator runs unattended
  under `bypassPermissions` and commits code and files issues from whatever it read, so a
  second root could shadow the trusted `prd.json`, plan files, or findings file with untrusted
  ones — a confused deputy with a real payoff. `resolve_config_root` dies naming both paths and
  demands explicit resolution. This is why the migration moved `meta/` away entirely rather
  than leaving a compatibility copy behind.
- **Root selection is a pure filesystem check in Python, made before prompt construction.**
  Around 27 prompt strings interpolate these paths, and those paths are the *instruction* half
  of the prompt. Deriving the root from repo content — `CONTEXT-MAP.md`, a plan file, anything
  — would hand prompt authorship to untrusted text. The resolved root is also `.resolve()`d and
  refused if it is a symlink or escapes the repo.
- **`docs/` now carries content that must never be published.** `meta/` read as private;
  `docs/` reads as publishable, and a future Pages or doc-publishing step would plausibly sweep
  up session transcripts. Mitigated by name-pattern ignore rules covering both layouts
  (`**/implementation-logs/`, `**/prd.json.lock`, `**/sdlc-review-findings.md`,
  `**/pr-summary.md`), a runtime guard that refuses to write a log line to a path the repo does
  not ignore, and explicit warnings in `CONTEXT-MAP.md`, `docs/agents/README.md`, and
  `docs/agents/PRIVACY.md`.
- Every repo the loop ever runs against needs the right ignore rule for its own layout,
  forever. That is why the rules are name patterns rather than exact paths: the original
  addition and this migration hit the identical failure mode.
