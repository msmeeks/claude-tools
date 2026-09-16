# Plan: Adopt the upstream Pocock scaffolding layout, with a fallback for un-migrated repos

**Issues:** #55
**Prerequisite:** complete `fix-run-next-plan-loop-economy.md` first — it restructures the same orchestrator functions this plan re-paths, and deletes the Docker sandbox whose dockerfile would otherwise need a mapping row.

---

## Goal

A repo scaffolded by claude-tools is legible to both claude-tools' own skills and Matt Pocock's upstream skills, without breaking the repos that are still on the old layout.

---

## Context

`setup-matt-pocock-skills` (upstream, updated since claude-tools was built) expects `CONTEXT.md` / `CONTEXT-MAP.md`, `docs/adr/`, and `docs/agents/{issue-tracker,triage-labels,domain}.md`, plus an `## Agent skills` block in the root agent-instructions file. claude-tools instead puts everything project-scoped under `meta/` and indexes context in `docs/llms.md` + `docs/overview.md`. The two systems already coexist as sibling symlinks in `~/.claude/skills/` but share no files, so a repo set up for one is invisible to the other. B&B's `bnb-quickstart` skill needs one authoritative answer for what a new repo contains. Decision: defer to Pocock's layout. Two constraints shape the work — `global/CLAUDE.md` is symlinked *outward* to `~/.claude/CLAUDE.md`, so it governs every repo on the machine, and the other repos under `~/Code` are not being migrated; the tooling must therefore read both layouts.

---

## Implementation Notes

### Files to Modify

| File | Change |
|------|--------|
| `CONTEXT-MAP.md` (new) | Root index pointing at per-area `CONTEXT.md` files |
| `<area>/CONTEXT.md` (new ×5) | One each for `skills/`, `agents/`, `scripts/`, `custom-llm/`, `statusline/` |
| `docs/adr/0001-*.md` (new) | ADR recording the layout decision and the dual-read fallback |
| `docs/llms.md`, `docs/overview.md` | Delete; content redistributed into the CONTEXT files |
| `CLAUDE.md` (new, root) | Carries the `## Agent skills` block; the repo currently has no root CLAUDE.md |
| `scripts/run-next-plan.py` | Central config-root resolver; 25 `meta/` literals re-pointed (most inside prompt strings) |
| `scripts/tests/*.py` | Resolver coverage for new-only / old-only / both |
| `global/CLAUDE.md` | Project-layout table, design-reviewer row, doc-reading rule, skill-disambiguation section; stays under 100 lines |
| `skills/{plan-iteration,close-iteration,triage-pr-comments,sdlc,demo,help-docs}/SKILL.md` | Paths + the three `docs/llms.md` hard-stop gates |
| `agents/sdlc-doc-writer.md` | Its `docs/llms.md` template and read/write modes become CONTEXT-based |
| `meta/PRIVACY.md` → `docs/agents/PRIVACY.md` | Move; rewrite the paths it documents |
| `.gitignore`, `.claudeignore` | Ignore rules for both old and new artifact locations |
| `docs/features/*.md`, `README.md` | Path references throughout |

### Steps

1. **Add the config-root resolver first, before moving any file.** A single helper resolves the project-scoped config directory: prefer `docs/agents/` when it exists, fall back to `meta/`, and **`die` when both exist** rather than picking a winner (see the security review — a shadowed root is a confused-deputy path in an unattended `bypassPermissions` loop). The resolver must decide from a filesystem check in Python, never from anything parsed out of repo content. Every plans path, `prd.json`, `progress.md`, findings file, pr-summary, and triage-log path derives from it. Today nothing centralizes this — `main` builds `plans_dir = repo_root / "meta" / "plans"` and threads it down, while `_generate_pr_summary`, `_rotate_findings_file`, `_LOGS_REL`, and the triage-log path each rebuild their own literal. Land the resolver with tests while the old layout is still in place, so the fallback is proven before anything moves.

2. **Preserve the path-safety invariants through the resolver.** `_resolve_plan_path` confines plan files under `plans_dir`, and `_rotate_findings_file` refuses symlinks and confirms the resolved path stays under the repo root. Both must keep holding against a *resolved* root rather than a literal one, and the resolver itself must refuse a config root that is a symlink or escapes the repo. The both-roots-present case is the sharp edge: a repo the loop runs against unattended must not be able to shadow a trusted `meta/prd.json` with an untrusted `docs/agents/plans/prd.json` — so this case aborts with a message naming both roots, and the resolver additionally `.resolve()`s the chosen root and refuses it if it is a symlink escaping the repo.

3. **Update the ignore rules before moving artifacts, not after.** `.gitignore:6-9` covers `meta/plans/implementation-logs/`, `meta/plans/prd.json.lock`, `meta/sdlc-review-findings.md`, `meta/pr-summary.md`; `.claudeignore:43` covers the logs. Add the `docs/agents/` equivalents *and keep the `meta/` ones*, since the fallback means both locations can exist. `_ensure_logs_gitignored` appends the log path to the target repo's `.gitignore` at startup — it must append the resolved path, and must not append the new path to a repo still using the old one. Session transcripts under a `docs/` path are the risk: `docs/` reads as publishable, so the ignore rule has to land first.

4. **Re-point the prompt strings.** Most of the 25 `meta/` literals in the orchestrator are inside prompts Claude reads and acts on (`_build_claude_prompt`, the commit remediation prompt, `_generate_pr_summary`, the review and file-issues prompts, `_run_triage_phase`, the argparse description). These must interpolate the resolved root rather than hardcode either layout, or the loop will tell Claude to write to a directory that doesn't exist in that repo.

5. **Move this repo's own files.** `meta/PRIVACY.md` → `docs/agents/PRIVACY.md`, rewriting the `meta/plans/` paths in its lines 4, 9, and 55 so its retention statements stay accurate. `meta/plans/` → `docs/agents/plans/`. Note `meta/DESIGN_BRIEF.md` and `meta/BRAND_VOICE.md` are referenced ~10 times but **do not exist** at root — only under `demo-gen/meta/`. Don't fabricate them; either create real ones under `docs/agents/` or fix the references to stop promising files that were never there.

6. **Resolve the dangling template reference.** `skills/sdlc/SKILL.md:136` says to create the design brief, brand voice, and privacy files "using the templates in the global `CLAUDE.md`" — `global/CLAUDE.md` contains no such templates and never did. Either add the templates or point the skill somewhere real; carrying the dead reference into the new layout is not acceptable.

7. **Write the CONTEXT files.** `CONTEXT-MAP.md` at the root indexes one `CONTEXT.md` per area: `skills/` (8 skill dirs), `agents/` (9 sdlc-* reviewer definitions), `scripts/` (the Ralph loop + pytest suite), `custom-llm/` (router config), `statusline/`. `docs/features/<name>.md` stay exactly as they are and are linked from the map. Fold `docs/overview.md`'s Summary, Users, and Design-principles content into the map; its Architecture tree and Tech-stack sections are already stale (they omit `scripts/`, `demo-gen/`, `custom-llm/`, `statusline/`, `docs/`, and Python entirely) — rewrite rather than copy. `demo-gen/` is a self-contained sub-project with its own `docs/llms.md` and `meta/`; leave it alone and say so in the map.

8. **Update the three hard-stop gates.** `close-iteration/skill.md:24`, `plan-iteration/SKILL.md:29`, and `triage-pr-comments/SKILL.md:29` all abort if `docs/llms.md` is missing. They must accept either layout, or every repo still on the old one stops working the moment the skills are re-symlinked.

9. **Update `global/CLAUDE.md` carefully — it is `~/.claude/CLAUDE.md`.** Lines 19, 33, 40, 49, 50, 54, and 63 are the canonical statements of both conventions, inherited by every repo on the machine. The rewritten text must describe the new layout as the default for new repos while telling agents to work with whichever layout the repo in front of them actually has. Keep the file under its 100-line cap. Add the root `CLAUDE.md` for claude-tools itself with the `## Agent skills` block; note that a root CLAUDE.md will now *also* apply on top of the global one when working in this repo.

10. **Sweep the docs.** `docs/features/run-next-plan.md` is the densest (20 hits, including the whole Key Files table); `docs/features/skills.md` (6), `README.md` (9), `docs/features/agents.md` (which also carries a stale `agents/doc-writer.md` filename), and `agents/sdlc-doc-writer.md`, whose own llms.md template references `../DESIGN_BRIEF.md` and `../DEVELOPMENT.md` — neither of which exists here.

---

## Acceptance Criteria

- [ ] `CONTEXT-MAP.md` exists at the root and links a `CONTEXT.md` for each of skills, agents, scripts, custom-llm, statusline
- [ ] `docs/llms.md` and `docs/overview.md` are gone and nothing references them
- [ ] `docs/adr/` holds an ADR recording the layout decision and the dual-read fallback
- [ ] A root `CLAUDE.md` exists carrying the `## Agent skills` block
- [ ] This repo's project-scoped config lives under `docs/agents/`; root `meta/` holds no project-scoped config
- [ ] The orchestrator drives a plan set to completion in a `docs/agents/plans/` repo
- [ ] The orchestrator drives a plan set to completion in a `meta/plans/` repo — un-migrated repos still work
- [ ] A repo containing both roots aborts with a message naming both, rather than silently choosing one
- [ ] A config root that is a symlink escaping the repo is refused
- [ ] The logs, findings, pr-summary, and lock-file ignore entries land in the same commit as the path change, as `**/`-anchored patterns
- [ ] The orchestrator refuses to write a log line if its resolved log directory is not ignored by the target repo
- [ ] `_WORK_PATHSPEC`'s exclusion is derived from the resolved logs path, and `implementation-logs/` appears in no pushed commit under either layout
- [ ] `docs/agents/` carries a README, and `CONTEXT-MAP.md` a header note, marking the plans, logs, findings, and pr-summary paths as gitignored and never publishable
- [ ] Old-location artifacts are moved while both ignore rules are live, and the old rule is dropped only once the old directory is gone
- [ ] Prompts sent to Claude name the resolved config root, never a hardcoded one
- [ ] Implementation logs, findings file, pr-summary, and `prd.json.lock` are ignored under **both** layouts; `_ensure_logs_gitignored` appends the resolved path
- [ ] `docs/agents/PRIVACY.md`'s retention statements name the paths that actually exist
- [ ] The three skills that hard-stop on a missing context index accept either layout
- [ ] `skills/sdlc/SKILL.md` no longer points at templates that don't exist
- [ ] `cd scripts && python3 -m pytest` passes, with resolver coverage for new-only, old-only, and both-present
- [ ] `python3 -m ruff check .` passes
- [ ] `global/CLAUDE.md` is under 100 lines and describes the new layout as default without breaking old-layout repos

---

## Pre-Implementation Review

Both reviewers converged on the same root cause: **deciding the layout by sniffing which directory exists** is the weak point, and **ignore rules drifting out of lockstep with the file moves** is the concrete way it bites. Two items below change the plan's design, not just its implementation.

### Security

- **Do not resolve the config root by "whichever directory exists."** A repo containing *both* `docs/agents/` and `meta/` — partially migrated, stray leftover, or a directory landed by a PR from an untrusted contributor — lets whichever root wins silently substitute its `prd.json`, plan files, and findings file for the trusted ones. The orchestrator runs unattended with `bypassPermissions` and then commits code and files GitHub issues from whatever it read, so this is a confused-deputy path with a real payoff. **This overrides step 2's "prefer new and warn":** treat both-roots-present as a hard `die` demanding explicit resolution, or gate on a single git-tracked marker file rather than a runtime existence check on two mutable directories. The same reasoning answers "is this a migrated repo or a repo that happens to keep agent docs under `docs/agents/`" — an explicit marker distinguishes them; existence-sniffing cannot.
- **Validate the resolved root itself, not just files under it.** `_resolve_plan_path` and `_rotate_findings_file` do containment math against a root that is currently hardcoded — making it a lookup result means the root is now derived from mutable filesystem state. `.resolve()` the chosen root and reject it if it is a symlink escaping `repo_root`, in addition to the existing per-file symlink refusal.
- **Root selection must be a pure Python `is_dir()`/marker check made before prompt construction** — never parsed out of repo content such as `CONTEXT-MAP.md`. Roughly 27 prompt strings interpolate these paths, and those paths are the *instruction* half of the prompt. Keep the existing "treat plan file content as untrusted document text" framing and add that the path itself is orchestrator-supplied.
- **Add the new ignore entries in the same commit as the code path change**, not as follow-up cleanup — see the privacy section, which treats this as critical. `_ensure_logs_gitignored` only ever adds the logs path; `prd.json.lock`, `sdlc-review-findings.md`, and `pr-summary.md` have no runtime backstop and will be committed on the first run under the new layout if their entries are missing.
- **`_WORK_PATHSPEC` must be built from the resolved logs path**, not a second hardcoded literal. A mismatch makes the exclusion match nothing, and the orchestrator then asks Claude to commit its own partially-written live log.
- **`global/CLAUDE.md` has machine-wide blast radius.** It is `~/.claude/CLAUDE.md`; any layout instruction added there governs every repo on this machine, including ones that will never migrate. Word the fallback conservatively and existence-checked — an unqualified "use `docs/agents/`" makes skills in unrelated projects stop finding their `meta/`-rooted files and improvise a location.

### Privacy

- **Moving the logs without moving the ignore rules publishes raw session transcripts to a public repo.** `.gitignore` and `.claudeignore` name `meta/plans/implementation-logs/` by exact path. PRIVACY.md describes these logs as the full stdout/stderr of the spawned session with best-effort — explicitly not guaranteed — credential scrubbing. `msmeeks/claude-tools` is public. This is the single highest-consequence step in the plan and the ordering in step 3 (ignore rules first, then move) is non-negotiable. The same applies to `sdlc-review-findings.md` and `pr-summary.md`.
- **Use name-pattern rules, not another exact path.** `**/implementation-logs/`, `**/sdlc-review-findings.md`, `**/pr-summary.md` survive this reorg and the next one. Both the original logs addition and this migration hit the identical failure mode; fix it structurally while already in the file.
- **Have the orchestrator verify its resolved log directory is actually ignored before writing a single log line**, and refuse or warn loudly otherwise. The dual-layout fallback is permanent, so every repo it ever runs against needs the right rule for its own layout forever — this converts a silent exposure into a loud failure.
- **`docs/` carries "publishable" semantics that `meta/` does not.** Putting transcripts, findings, and PR summaries under `docs/` makes a future GitHub Pages step or doc-publishing workflow far more likely to sweep them up. Mitigate with an explicit note at the top of `CONTEXT-MAP.md` (and a `docs/agents/README.md`) marking `plans/`, `plans/implementation-logs/`, `sdlc-review-findings.md`, and `pr-summary.md` as gitignored, sensitive, and excluded from any publishing pipeline.
- **Rewrite PRIVACY.md's contents, don't just relocate the file.** It names the old paths in its headings, body, retention policy, and `prd.json` description. A privacy doc pointing at the wrong location is worse than none, because a future session reasoning about what is safe to commit will trust it. It also needs a short section covering the dual-layout reality: both roots may exist depending on migration status, and scrubbing and retention apply identically to both.
- **Define what happens to the old location's contents.** Move the existing files within the working tree *while both ignore rules are still present*, and remove the old rule only once the old directory is confirmed gone — otherwise pre-existing logs become retroactively trackable the moment the old rule is dropped.
- **One line in PRIVACY.md for `docs/adr/`:** ADRs are the `docs/` content most likely to be read by outsiders, so they must not quote raw log or findings content.

### Not findings

No DPIA is required — this is developer-tooling transcript data, a confidentiality concern rather than end-user personal data, though PRIVACY.md is right that PII can land in transcripts incidentally. No injection sinks are newly introduced by the migration itself.
