---
name: sdlc
description: Full software development lifecycle orchestrator. Dispatches parallel subagent reviews (code quality, style/lint, security, privacy, accessibility, design, tests, QA, documentation) for any code change. Use this skill whenever making non-trivial code changes. Also use during planning phase to run doc review plus security, privacy, accessibility, and design reviews before implementation.
---

# SDLC Orchestrator

This skill manages the full review and QA pipeline for code changes. Always invoke it for non-trivial changes.

<!--
BASELINE VARIANT — used only inside a disposable git worktree during
scripts/wenyan_validation_run.py baseline passes, never in the real repo.

This is a surgical patch of the real skills/sdlc/SKILL.md: Phase 3/4 dispatch
agents for direct plain-English prose (as the pipeline worked before the
wenyan-ultra handoff-file protocol, issues #28-#30), instead of minting a
scratchpad path and writing/reading/decoding a compressed JSON handoff file.
Every other phase (0, 1, 2, linter reference, design brief, checklist, demo,
brand compliance) is identical to current HEAD, so the only variable this
isolates is "compressed file-handoff vs. plain prose" — not any of the later
hardening/schema-drift fixes, which apply equally to both conditions.
-->

## Usage

```
/sdlc [phase] [--parallel]
```

- `/sdlc` — full pipeline (all phases), agents run **in series**
- `/sdlc plan` — planning/design phase only (docs + security + privacy + a11y + design)
- `/sdlc review` — code + style + security + privacy + a11y + design + test reviews only
- `/sdlc qa` — QA phase only
- `/sdlc docs` — documentation update only (run after changes, before merging)
- `--parallel` — dispatch review agents in parallel instead of series (faster, but findings may be redundant)

## Phase 0: Doc bootstrap (first time in a project)

If `docs/` does not exist in the project root, dispatch first:

```
Agent(sdlc-doc-writer): The docs/ directory does not exist for this project. Create it with docs/llms.md, docs/overview.md, and docs/features/ stubs for each major feature area. Read the codebase to understand the project before writing.
```

## Phase 1: Planning (run before implementation)

**Step 1 — Read docs first.** Dispatch the doc-writer to load context before touching code:

```
Agent(sdlc-doc-writer): Read docs/llms.md and load the feature doc(s) relevant to [feature/task description]. Summarize what's documented, flag any gaps or outdated sections, and identify the key files and patterns I should know before implementing.
```

**Step 2 — Dispatch planning reviews in series** (after reading doc summary). Run each agent and wait for its result before dispatching the next. With `--parallel`, dispatch all four simultaneously:

```
Agent(sdlc-security-reviewer): Analyze threat model for the planned feature. What attack surfaces does this introduce? What auth/authz patterns are needed?

[wait for result, then:]

Agent(sdlc-privacy-reviewer): Review the data design. What PII will be collected/stored? What consent flows are needed? What retention/deletion policies apply?

[wait for result, then:]

Agent(sdlc-accessibility-reviewer): Review the planned UI. What WCAG 2.2 AA requirements apply? What keyboard/screen reader patterns are needed?

[wait for result, then:]

Agent(sdlc-design-reviewer): Review the planned UI against the design brief. What existing components should be reused? What new patterns need to be defined?
```

Address all findings before writing implementation code.

## Phase 2: Implementation

Follow these rules during implementation:

1. Run the linter after every file change — fix errors before moving on
2. Write tests as you write code (TDD preferred; test-alongside acceptable)
3. Cover edge cases and error paths, not just happy paths
4. Keep third-party imports minimal — justify every new package

## Phase 3: Review (run after implementation, before QA)

Dispatch the seven review agents **in series** — wait for each result before starting the next. With `--parallel`, dispatch all seven simultaneously.

Each agent returns its findings directly as plain-English prose in its response — no scratchpad file, no JSON schema, no compression. Report only issues that genuinely matter (confidence > 70%), grouped by severity (Critical/Major/Minor or each agent's own severity axis), each with file, line range, what the problem is, and a concrete fix suggestion.

```
Agent(sdlc-code-reviewer): Review [files changed] for DRY/SOLID, correctness, and third-party usage. Report findings as prose: file, line, issue, fix.

[wait, then:]

Agent(sdlc-style-reviewer): Review [files changed] for naming, comment quality, idiomatic constructs, and linting compliance. Report findings as prose: file, line, issue, fix.

Agent(sdlc-security-reviewer): Review [files changed] for OWASP Top 10, auth/authz, injection risks, and dependency CVEs. Report findings as prose: file, line, issue, fix. Any suspected real (non-synthetic) secret must be described by type and location only, never quoted verbatim or masked.

Agent(sdlc-privacy-reviewer): Review [files changed] for GDPR compliance, PII handling, and data minimization. Report findings as prose: file, line, issue, fix. Any suspected real (non-synthetic) PII must be described by type and location only, never quoted verbatim or masked.

Agent(sdlc-accessibility-reviewer): Review [files changed] for WCAG 2.2 AA compliance. Report findings as prose: file, line, issue, fix.

Agent(sdlc-design-reviewer): Review [files changed] for design brief adherence and component consistency. Report findings as prose: file, line, issue, fix.

Agent(sdlc-test-reviewer): Review [files changed] for test quality: genuine-value assertions, edge cases, branch coverage, line coverage (target 90%+), frontend+backend unit-test parity, and boundary cases for conditionals and range comparisons. Report findings as prose: file, line, issue, fix.
```

Fix all Critical/Blocker issues. Fix Major issues unless there is a documented reason not to. Minor issues may be deferred to a follow-up.

## Phase 4: QA + Documentation

Run QA and documentation update **in series** after all review fixes are applied. With `--parallel`, dispatch both simultaneously.

```
Agent(sdlc-qa-engineer): Run automated tests, lint, API smoke tests, and regression check for [feature description]. Report PASS/FAIL, tests run, and any failures (name, expected, actual, log excerpt) as prose directly in your response. Redact sensitive headers and PII-shaped fields from any log excerpt before including it.

[wait, then:]

Agent(sdlc-doc-writer): Update documentation for [feature changed]. Create or update the relevant docs/features/<name>.md, and update docs/llms.md if any new doc files were created.
```

QA must **PASS** before marking the task complete. Any QA failure must be fixed and QA re-run. Documentation must be updated before the task is marked done.

**Planning-phase agents are unaffected.** `sdlc-doc-writer` and the Phase 1 planning-time invocations of `sdlc-security-reviewer`, `sdlc-privacy-reviewer`, `sdlc-accessibility-reviewer`, and `sdlc-design-reviewer` stay plain-text prose, same as in the current (non-baseline) pipeline.

## Linter reference

Always run linters on changed files:

```bash
# Frontend (TypeScript)
cd frontend && npm run lint

# Backend (Python) — ruff is in pyproject.toml dev deps
cd backend && python3 -m ruff check .

# Auto-fix safe issues
cd backend && python3 -m ruff check . --fix

# Type check Python (install if needed: pip install mypy)
cd backend && python3 -m mypy app/ --ignore-missing-imports
```

## Design brief

Before any UI work, verify `meta/DESIGN_BRIEF.md` exists. If not, create the `meta/` directory and populate `meta/DESIGN_BRIEF.md`, `meta/BRAND_VOICE.md`, and `meta/PRIVACY.md` using the templates in the global `CLAUDE.md`.

## Summary checklist

- [ ] `docs/` directory exists; `docs/llms.md` index is current
- [ ] Doc review done at planning start (doc-writer read relevant feature docs)
- [ ] Planning reviews done (security, privacy, a11y, design)
- [ ] Implementation follows DRY/SOLID, minimal deps, TDD
- [ ] Linter clean throughout
- [ ] All 7 review agents run (series by default; `--parallel` if speed needed)
- [ ] All Critical/Blocker findings fixed
- [ ] QA agent run and PASS
- [ ] Doc update done (feature doc + llms.md)
- [ ] Design brief up to date

## Demo & Help-Docs Phase (run after docs phase on significant features)

After completing the docs update, determine whether the change is user-visible (new feature, significant enhancement, UI change). If yes:

**Step 1 — Generate demo artifact:**
```
/demo <feature-name>
```
This produces `help-docs/demos/features/<name>.html` and `help-docs/demos/features/<name>.mp4`.

**Step 2 — Update help docs:**
```
/help-docs ui    (if UI changed)
/help-docs api   (if API changed)
```

**Step 3 — Update demo gallery:**
Update `help-docs/demos/index.html` to include the new demo card.

## Brand compliance check

Before finalizing any user-facing content in the docs or demo phases, verify:
- `meta/BRAND_VOICE.md` exists
- All copy matches the voice attributes in `meta/BRAND_VOICE.md`
- Product name, tagline, and terminology are consistent
