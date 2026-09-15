# docs/agents

This repo's project-scoped agent config. Despite living under `docs/`, **most of it is not
documentation and none of that part is publishable.**

## Not publishable, ever

These are gitignored by name pattern in `.gitignore` (and `.claudeignore`), and must be
excluded from any future docs-publishing or GitHub Pages pipeline:

| Path | Contents |
|---|---|
| `plans/` | the current iteration's plan files and `prd.json` |
| `plans/implementation-logs/` | raw Claude session transcripts — full stdout/stderr, best-effort credential scrubbing only |
| `plans/prd.json.lock` | the prd mutex |
| `sdlc-review-findings.md` | review findings before they are filed as issues |
| `pr-summary.md` | the generated two-audience PR body |

`PRIVACY.md` is the authoritative statement of what these hold, how long they are kept, and
what scrubbing does and does not guarantee. Read it before adding anything that writes here.

The ignore rules are name patterns (`**/implementation-logs/`, not
`docs/agents/plans/implementation-logs/`) so they survive this reorganisation and the next
one. Two separate incidents came from an exact-path rule drifting out of lockstep with a file
move; do not convert them back.

## Actual documentation

`issue-tracker.md`, `triage-labels.md`, and `domain.md` configure the upstream engineering
skills for this repo, and are safe to read and publish. `PRIVACY.md` is also safe.

## Both layouts exist

Repos on this machine use one of two config roots: `docs/agents/` (this layout) or `meta/`
(the original). Everything above applies identically to `meta/` in an un-migrated repo — same
artifacts, same sensitivity, same retention. See
[ADR 0001](../adr/0001-scaffolding-layout-with-dual-read-fallback.md).
