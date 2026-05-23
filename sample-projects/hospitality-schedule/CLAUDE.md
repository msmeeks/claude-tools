# hospitality-scheduled — Project Instructions

## Planning & SDLC

**MANDATORY:** Before writing, editing, or creating any code file, you MUST invoke the Skill tool
with `skill='sdlc'`. Do not write a single line of implementation code until `/sdlc` has been run
for the current task. Run it before implementation starts (planning phase) and again after code is
written for post-implementation review.

For documentation: read `docs/llms.md` first, then only the relevant feature doc(s).
After every non-trivial change run `doc-writer` to update the feature doc, `CHANGELOG.md`, and
`docs/llms.md`.

## Branching & Promotion

All feature/fix/infra branches must target **`staging`** — never `main`.
Promotion to `main` is done exclusively via a `staging → main` PR.

- Default PR base: `staging`
- `main` receives merges only from `staging`; CI blocks any other source

## Parallel Workstreams (Git Worktrees)

Use git worktrees + per-PR Fly.io dev environments for all multi-issue or multi-feature work so
local resources are never shared between workstreams.

Workflow:
1. `git worktree add ../hospitality-<feature> -b <branch>` — isolated checkout per feature/issue
2. Push branch and apply the `deploy` label on the PR → CI spins up a dedicated dev env
   (`hospitality-api-dev-<slug>` / `hospitality-app-dev-<slug>`)
3. Work, test, and review each workstream independently
4. Remove the worktree when the PR merges: `git worktree remove ../hospitality-<feature>`

See `docs/features/deployment.md` for Fly.io dev-env details (slug naming, secrets, seeding).

## PR Descriptions & Comments

Every PR must include:
- **Actual embedded screenshots** of visible UI changes — real `![caption](url)` markdown, not placeholder text
- **Text summary** of what changed and why (link to the issue)
- **Demo links** for significant features (see Demo section below)

**How to embed screenshots in PRs:**
1. Use browser MCP (`browser_screenshot`) to capture the running app (dev env URL or `localhost`)
2. Save the screenshot file locally (e.g. `/tmp/screenshot-<feature>.png`)
3. Upload via GitHub's asset API: `gh api --method POST /repos/{owner}/{repo}/issues/{number}/assets -F file=@/tmp/screenshot.png`
4. Use the returned `browser_download_url` in `![caption](url)` markdown in the PR body or comment

Never write a screenshot caption line without an actual image tag below it.

Add screenshots as follow-up PR comments when iterating mid-review to keep the description clean.

## Demos & Help Docs

- **New feature**: run `/demo <feature>` → produces `help-docs/demos/features/<feature>.html` +
  `.mp4`; add the link to the PR description.
- **Significantly changed feature**: re-run `/demo <feature>` to replace the existing demo;
  note the update in the PR description.
- **Major feature milestone**: run `/help-docs` to regenerate the full help-docs site and demo
  gallery (`help-docs/demos/index.html`).

Demo links in PRs: link to `help-docs/demos/features/<feature>.html` (relative path or GitHub
Pages URL once published).

## Tech Stack Quick-Ref

| Layer | Stack |
|---|---|
| Backend | Python / FastAPI, SQLAlchemy async, Alembic, PostgreSQL |
| Frontend | React + TypeScript, Vite, Tailwind CSS |
| Hosting | Fly.io — prod + per-PR dev envs via GitHub Actions |
| Storage | Fly Tigris (S3-compatible) |

See `docs/overview.md` for full architecture and `DEVELOPMENT.md` for local setup.

## Linting

- **Backend**: `python3 -m ruff check .` (run from `backend/`)
- **Frontend**: `npm run lint` (run from `frontend/`)

Fix all lint issues before marking work done.

## Key File Locations

- Design system: `DESIGN_BRIEF.md`
- Brand voice (UI copy, demo scripts): `BRAND_VOICE.md`
- Deployment feature doc: `docs/features/deployment.md`
- Health endpoint: `/api/v1/health`
