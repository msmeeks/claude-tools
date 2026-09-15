# Iteration progress

Append-only log. One timestamped entry per completed plan.

## 2026-09-15 — fix-run-next-plan-loop-economy.md

Closed issues #54, #53, #56. Three changes to the Ralph orchestrator, all TDD'd:

- **Commit/push split.** `ensure_committed_and_pushed` became `ensure_committed` (commit only)
  plus `flush_push` (publish only). Every Claude-facing prompt now says "commit" and then
  "Do not push" explicitly — the explicitness matters because plan/issue text is untrusted.
  Pushes are placed deliberately: one per plan iteration, one at the end of a completed review
  round (moved after the docs phase, preceded by a sweep that finally commits
  `meta/pr-summary.md`), and one `atexit`-registered `exit_flush` covering every termination
  path. `exit_flush` is git-only — no Claude, no `prd.json`, no prd lock (it can fire inside
  `_with_prd_lock`) — commits through `_WORK_PATHSPEC`, and swallows failures. Push-failure
  stderr now goes through `_scrub_credentials`. `sync_pr_closes` caches its last-written
  closes set so the four per-pass call sites collapse to at most one `gh` round trip.
- **Review-round cap.** New optional `sdlc_review_rounds` in `prd.json` (validated like
  `attempts`: rejects bools and negatives, defaults to 0 so existing files load), incremented
  under the prd lock at the gate's terminal write; the empty-increment no-op doesn't count.
  `_rearm_sdlc_review_gate` returns `False` at `MAX_REVIEW_ROUNDS` (2, overridable via
  `RALPH_MAX_REVIEW_ROUNDS`) and logs a policy-stop line naming the deferred issues. The final
  round still files and triages findings as issues but writes no plans, no prd entries, and
  nothing into `sdlc_finding_issues` — a PR must not claim to close findings it never fixed.
  Issue bodies are now filed paraphrase-only with a redaction instruction.
- **Docker sandbox deleted.** `build_run_command`, `get_image_tag`, `_IMAGE_TAG_SAFE_RE`, the
  `docker_mode` branch, its `--dry-run` line, `test_docker_sandbox.py`, and
  `meta/ralph.dockerfile.example` are gone. Docs replace the section with an explicit
  statement that the loop runs unsandboxed on the host under `bypassPermissions`.

Docs: `docs/features/run-next-plan.md` (commit/push enforcement, sync suppression, trust
model, round cap, final-round deferral), `README.md` (dropped the sandbox paragraph, corrected
the false "only ever runs once per prd lifecycle" claim), `meta/PRIVACY.md` (the outbound
`gh issue create` path, `sdlc_review_rounds`, deferred-finding retention).

QA: 146 tests pass (`cd scripts && python3 -m pytest`), `ruff check` clean, `--dry-run` smoke
prints no Docker line and pushes nothing, and a pre-cap `prd.json` still loads.

## 2026-09-15 — refactor-scaffolding-layout.md

Closed issue #55. A prior interrupted iteration had already landed the bulk of this XL plan —
`resolve_config_root` (with its both-roots `die`, symlink/escape refusal, and 13 dedicated
tests in `test_config_root.py`), the `docs/agents/` move (`prd.json`, `progress.md`, plan
files, `PRIVACY.md` rewritten in place), `CONTEXT-MAP.md` plus five per-area `CONTEXT.md`
files, `docs/adr/0001-scaffolding-layout-with-dual-read-fallback.md`, a root `CLAUDE.md`, the
name-pattern ignore rules (`**/implementation-logs/`, `**/prd.json.lock`,
`**/sdlc-review-findings.md`, `**/pr-summary.md`), and `docs/agents/README.md`'s
not-publishable warning. `docs/llms.md`/`docs/overview.md` were already deleted and
`global/CLAUDE.md` already rewritten under its 100-line cap.

This session finished the remaining doc/skill sweep:

- **Dangling template reference (step 6).** `skills/sdlc/SKILL.md`'s design-brief section
  claimed templates existed in the global `CLAUDE.md` — they never did. Replaced with an
  instruction to write `DESIGN_BRIEF.md`/`BRAND_VOICE.md`/`PRIVACY.md` from the project's
  actual UI, voice, and data-handling choices, at the resolved config root.
- **Three hard-stop gates (step 8).** `close-iteration/skill.md`, `plan-iteration/SKILL.md`,
  and `triage-pr-comments/SKILL.md` all aborted on a missing `docs/llms.md` alone. Each now
  checks `CONTEXT-MAP.md`/`CONTEXT.md` first, falling back to `docs/llms.md` for un-migrated
  repos, and every `meta/plans/` literal became `<config-root>/plans/` with an explicit
  resolution step.
- **Doc sweep (step 10).** `docs/features/run-next-plan.md` (14 stale `meta/plans/` /
  `meta/PRIVACY.md` references — the two left as written are the deliberate old-layout
  fallback mentions), `docs/features/skills.md`, `README.md` (repo layout tree, Ralph loop
  section, skills/agents reference tables), `agents/sdlc-doc-writer.md` (its read/write modes
  and index template rewritten to prefer `CONTEXT-MAP.md`/`CONTEXT.md`, with the old
  `docs/llms.md` template kept only as the documented un-migrated-repo fallback), and
  `skills/demo/SKILL.md` / `skills/help-docs/SKILL.md` (`meta/BRAND_VOICE.md` →
  `docs/agents/BRAND_VOICE.md` with fallback). Also fixed `docs/features/agents.md`'s stale
  `agents/doc-writer.md`-style filenames throughout its Key Files table — none of the nine
  carried the real `sdlc-` prefix.
- Left untouched, deliberately: `demo-gen/` (self-contained sub-project, own `docs/llms.md` +
  `meta/`) and `sample-projects/hospitality-schedule/CLAUDE.md` (an example template for a
  project that was never migrated).

QA: `cd scripts && python3 -m pytest` — 161 passed (13 in `test_config_root.py`); `ruff check .`
clean; manual grep sweep for stale `meta/plans`, `meta/PRIVACY`, `docs/llms.md`,
`docs/overview.md`, `meta/DESIGN_BRIEF.md`, `meta/BRAND_VOICE.md` outside `demo-gen/` and
`sample-projects/` turned up only intentional dual-layout fallback mentions.
