# Global Development Standards

Detailed checklists live in `~/.claude/agents/sdlc-*.md`. Read the relevant one rather than working from memory.

## Communication Style

Concise, low-fluff. Optimize for clarity per token, not brevity for its own sake — a real tradeoff deserves a real explanation.

- No filler: no "Great question!", no restating the ask, no "Let me...", no needless closing summary.
- Sentence fragments are fine. Bullets and tables over prose when they scan better.
- Applies to everything Claude writes: chat, commits, PR descriptions, code comments.

## TDD Workflow

**MANDATORY:** Before writing, editing, or creating any code file, invoke the Skill tool with `skill='tdd'`. Not optional. No implementation code until `/tdd` has run for the current task — failing test first, then implement, then refactor.

## Before touching the codebase

Read `docs/llms.md`, then only the relevant `docs/features/<name>.md`. The docs identify likely source files, key patterns, and architectural boundaries — use them to narrow the search before reading code. Code is authoritative; docs cut the search space.

## While writing code

Apply these inline — don't defer them to review. Full checklist in the linked agent.

| Concern | Rule | Detail |
|---|---|---|
| Code quality | DRY, SOLID, minimal deps — justify every new package | `sdlc-code-reviewer` |
| Tests | Edge cases, branch coverage, boundary values; delete tests that assert only implementation details | `sdlc-test-reviewer` |
| Style | Idiomatic for the language, descriptive names, comments explain WHY only | `sdlc-style-reviewer` |
| Security | Threat-model new endpoints and data flows; OWASP Top 10; validate at boundaries; parameterized queries | `sdlc-security-reviewer` |
| Privacy | GDPR defaults; no PII in logs, URLs, analytics, or errors | `sdlc-privacy-reviewer` |
| Accessibility | WCAG 2.2 AA: keyboard, contrast, semantic HTML, focus management | `sdlc-accessibility-reviewer` |
| UI design | Follow `meta/DESIGN_BRIEF.md`; reuse components; tokens only, never raw hex/px | `sdlc-design-reviewer` |

Linters: ESLint (`eslint.config.js`) for TS/JS, ruff for Python via `python3 -m ruff check .` — the `ruff` binary may not be on PATH. Run and fix before marking work done.

## Before marking work done

1. Tests, linter, smoke test, boundary inputs — see `sdlc-qa-engineer`.
2. Run `sdlc-doc-writer` after any non-trivial change to update the feature doc and `docs/llms.md`.
3. Never leave a PR conflicted: fetch base, merge or rebase, resolve, push.

## Project layout

Every project under `~/Code/` has these. If one is missing, create it during the first planning operation.

| Path | Contents | Skill |
|---|---|---|
| `docs/` | `llms.md` index, `overview.md`, `features/<name>.md` | `sdlc-doc-writer` |
| `meta/` | `DESIGN_BRIEF.md`, `BRAND_VOICE.md`, `PRIVACY.md`, `plans/` | — |
| `help-docs/` | Customer-facing docs | `/help-docs` on setup + each major feature |
| `.claudeignore` | `node_modules/`, `dist/`, `.venv/`, `__pycache__/`, build artifacts, coverage, lock files, large media, logs, uploads | — |

Read `meta/BRAND_VOICE.md` before writing user-facing copy (demo scripts, help docs, UI text). Run `/demo <feature>` when creating or significantly changing a feature. Release history lives in GitHub Releases, generated from merged PR titles by `deploy-prod.yml`.

Keep this file under 100 lines. Brief rules here, detail in files referenced by path.

## Skill disambiguation

- `/qa` *during a conversation about bugs/features* → conversational QA session that files GitHub issues
- `/qa` *after code changes are written* → run automated tests/lint/smoke checks
- `/triage` → evaluates one issue/PR, marks it `ready-for-agent` / `ready-for-human` / etc.
- `/plan-iteration` → backlog grooming: `/triage` each issue, cluster the `ready-for-agent` ones, write plans to `meta/plans/`
