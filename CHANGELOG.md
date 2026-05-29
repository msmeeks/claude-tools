# Changelog

## [Unreleased]

## [2026-05-29] — custom-llm subproject

- Added `custom-llm/` subproject: route Claude Code to Ollama (LAN or cloud VM), Gemini, or OpenAI via the `claude-code-router` proxy
- Includes install/launcher/verify scripts, four backend config templates, three networking options (Tailscale, SSH tunnel, Caddy+TLS), and cloud deploy recipes for fly.io and AWS EC2
- Added `docs/features/custom-llm.md`; updated `docs/llms.md`

## [2026-05-29] — Initial docs structure

- Created `docs/` directory with `llms.md` index, `overview.md`, and feature docs for agents, skills, and setup
- No code changes; documentation only

## [2026-05-29] — test-reviewer agent

- Added `agents/test-reviewer.md`: reviews test quality, edge cases, branch coverage (90%+ target), FE+BE parity, and boundary cases
- Wired into `/sdlc` Phase 3 alongside the other six review agents

## [2026-05-29] — Initial commit

- `agents/`: code-reviewer, style-reviewer, security-reviewer, privacy-reviewer, accessibility-reviewer, design-reviewer, doc-writer, qa-engineer
- `skills/`: sdlc, demo, help-docs, pr-image-upload, rank-backlog
- `global/CLAUDE.md`: global development standards
- `setup-symlinks.sh`: one-time bootstrap script
- `sample-projects/hospitality-schedule/CLAUDE.md`: example project-level config
