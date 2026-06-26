# Global Development Standards

## TDD Workflow

**MANDATORY:** Before writing, editing, or creating any code file, you MUST invoke the Skill tool with `skill='tdd'`. This is not optional. Do not write a single line of implementation code until `/tdd` has been run for the current task — write the failing test first, then implement, then refactor.

## Skill disambiguation

- `/qa` invoked *during a conversation about bugs/features* → conversational QA session that files GitHub issues
- `/qa` invoked *after code changes are written* → run automated tests/lint/smoke checks
- `/triage` → evaluates a single issue/PR and marks it `ready-for-agent`/`ready-for-human`/etc.
- `/plan-iteration` → backlog grooming entry point: triages each issue via `/triage`, groups `ready-for-agent` issues into logical clusters, writes plan files to `meta/plans/`

## Context & Token Efficiency

Every project must have a `.claudeignore` at its root. If one is absent, create it as part of the first planning operation. It should block:
- `node_modules/`, `dist/`, `.venv/`, `__pycache__/`, `*.pyc`
- Build artifacts, compiled outputs, coverage reports
- Lock files (`package-lock.json`, `poetry.lock`) — they are read-only noise
- Large media files (`*.mp4`, `*.png` in demo/asset dirs)
- Logs and upload directories

Keep `CLAUDE.md` under 100 lines. Use a pointer strategy: brief rules here, details in separate files referenced by path.

## Code Quality

- Follow DRY and SOLID principles strictly
- Minimize third-party dependencies — prefer stdlib/language built-ins; justify every new package
- Test coverage must include edge cases and branch coverage, not just happy paths
- Tests must add genuine value — delete tests that only assert implementation details

## Style & Formatting

- Use idiomatic constructs for the language in use (e.g., list comprehensions in Python, optional chaining in TS)
- Naming: descriptive, consistent with existing codebase patterns; no abbreviations unless universal
- Comments: only when the WHY is non-obvious; no docstring walls; max one short line
- Run the project linter and fix all issues before marking work done

## Linting

| Language | Linter | Config |
|---|---|---|
| TypeScript/JS | ESLint with `@typescript-eslint`, `react-hooks`, `react-refresh` | `eslint.config.js` |
| Python | `ruff` (already in `pyproject.toml` dev deps) | `pyproject.toml` `[tool.ruff]` section |

Run via `python3 -m ruff check .` (the `ruff` binary may not be on PATH). Run linters as part of every code change and in review.

## Security

- Perform threat analysis for every new endpoint or data flow
- Screen for OWASP Top 10 patterns in all code (including first-party)
- No sensitive data in logs, URLs, error messages, or local storage
- Authentication: verify token validation, expiry, and refresh on every auth-adjacent change
- Authorization: verify every endpoint enforces appropriate role/ownership checks
- Input validation at all system boundaries; parameterized queries always
- Keep third-party libraries minimal and audited; prefer well-maintained packages with few transitive deps
- Check CVEs for any new or updated dependency

## Privacy

- GDPR-level defaults: data minimization, purpose limitation, retention limits
- PII must never appear in logs, analytics events, error messages, or URLs
- Consent must be explicit and granular; default to opt-out
- Data access must be scoped to minimum necessary
- Document what PII is collected and why in design briefs

## Accessibility (WCAG 2.2 AA)

- All interactive elements must be keyboard navigable and focusable
- Sufficient color contrast ratios (4.5:1 text, 3:1 large text/UI)
- Semantic HTML: use correct elements (`<button>`, `<nav>`, `<main>`, `<label>`, etc.)
- ARIA labels on icons, icon-only buttons, and non-obvious controls
- Screen reader support: no information conveyed by color alone
- Form fields: visible labels, error messages linked via `aria-describedby`
- Focus management on modal open/close and dynamic content changes

## UI Design

- Use the project's design brief (see `~/Code/<project>/meta/DESIGN_BRIEF.md`) for all UI work
- Reuse existing components before creating new ones
- Consistent spacing, color, and typography tokens — never hard-code raw hex or px values outside Tailwind config
- All pages share the same layout shell, navigation, and header patterns
- Responsive: mobile-first, test at 375px, 768px, 1280px breakpoints

## Documentation

Every project under `~/Code/` must have a `docs/` directory. If it doesn't exist, create it during the first planning operation.

- `docs/llms.md` — index of all doc files; **always read this first during planning**
- `docs/overview.md` — project purpose, users, roles, architecture, tech stack
- `docs/features/<name>.md` — one file per major feature area
- Release-level history lives in GitHub Releases, auto-generated from merged PR titles by `deploy-prod.yml`.

**Before planning, reviewing code, or responding to any prompt about the codebase:** read `docs/llms.md` first, then the relevant feature doc(s). The docs are a maintained reference that identifies likely source files, key patterns, and architectural boundaries — use them to narrow your code search before reading code directly. Code is always the authoritative source of truth, but docs dramatically reduce the search space.

At the start of every planning operation: read `docs/llms.md`, then only the relevant feature doc(s). After every non-trivial change, run `sdlc-doc-writer` to update the feature doc and `docs/llms.md`.

## QA

Run tests, linter, smoke test, and boundary inputs before marking work done. Update docs (feature doc + llms.md index if new files added).

## PR Conflicts

When a PR has merge conflicts, always resolve them before pushing. Fetch the base branch, merge or rebase, resolve all conflicts, then push the updated branch. Never leave a PR in a conflicted state.

## Design Briefs & Brand Voice

Every project must have a `meta/` directory containing `DESIGN_BRIEF.md`, `BRAND_VOICE.md`, and `PRIVACY.md`. Create `meta/` and all three files during initial setup or first UI work. Read `meta/BRAND_VOICE.md` before writing any user-facing content (demo scripts, help docs, UI copy).

## Public Documentation (help-docs)

Every project must have a `help-docs/` directory with customer-facing docs. Structure is managed by the `/help-docs` skill. Run `/help-docs` when a new project is set up or a major feature is added. Run `/demo <feature>` when creating or significantly changing a feature.
