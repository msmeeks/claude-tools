# claude-tools

Personal Claude Code configuration. Read [CONTEXT-MAP.md](./CONTEXT-MAP.md) first, then the
per-area `CONTEXT.md` and the `docs/features/<name>.md` files relevant to the task.

The machine-wide standards in `~/.claude/CLAUDE.md` also apply here — that file *is*
`global/CLAUDE.md` in this repo, symlinked outward. Editing it changes every project on this
machine, so treat it as the highest-blast-radius file in the tree.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues, via the `gh` CLI. External PRs are not a triage
surface. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, each label string equal to its name: `needs-triage`, `needs-info`,
`ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `CONTEXT-MAP.md` at the root points at one `CONTEXT.md` per area. ADRs in
`docs/adr/`. See `docs/agents/domain.md`.

## Working here

- `scripts/` and `demo-gen/` are real code — tests and linter apply. Everything else is prose
  the CLI reads; changing it changes behaviour with no build step in between.
- `cd scripts && python3 -m pytest` and `python3 -m ruff check .` before calling work done.
- Nothing under `docs/agents/plans/` is publishable. See `docs/agents/README.md`.
