# claude-tools — Ralph Loop Implementation Plans

6 workstreams across issues #2–#6 plus the SDLC gate. Start with `ralph-prd-json-data-layer` — it unblocks all other plans. The two skill-update plans (#5, #6) can run in parallel with the loop rewrite (#3) since they touch separate files.

| Plan | Branch | Issues | Size | Status |
|------|--------|--------|------|--------|
| [ralph-prd-json-data-layer.md](ralph-prd-json-data-layer.md) | `feat/ralph-prd-json-data-layer` | #2 | M | done |
| [ralph-orchestration-loop.md](ralph-orchestration-loop.md) | `feat/ralph-orchestration-loop` | #3 | L | done |
| [ralph-plan-iteration-prd-json.md](ralph-plan-iteration-prd-json.md) | `feat/ralph-plan-iteration-prd-json` | #5 | M | done |
| [ralph-docker-sandbox.md](ralph-docker-sandbox.md) | `feat/ralph-docker-sandbox` | #4 | M | done |
| [ralph-triage-pr-comments-prd-json.md](ralph-triage-pr-comments-prd-json.md) | `feat/ralph-triage-pr-comments-prd-json` | #6 | M | done |
| [ralph-sdlc-review-gate.md](ralph-sdlc-review-gate.md) | `feat/ralph-sdlc-review-gate` | — | M | done |

## Suggested Order

1. **`feat/ralph-prd-json-data-layer`** (#2) — foundation; all other plans depend on the prd.json schema and data layer it defines
2. **`feat/ralph-orchestration-loop`** (#3) + **`feat/ralph-plan-iteration-prd-json`** (#5) — can run in parallel; #3 touches only `scripts/run-next-plan.py`, #5 touches only `skills/plan-iteration/SKILL.md`
3. **`feat/ralph-docker-sandbox`** (#4) — depends on #3 merging first (slots into the run-command structure)
4. **`feat/ralph-triage-pr-comments-prd-json`** (#6) — depends on #5 merging first (follows the prd.json merge pattern #5 establishes)
5. **`feat/ralph-sdlc-review-gate`** — depends on #3 merging first (extends the orchestration loop)

## Cross-cutting Notes

- `scripts/run-next-plan.py` is modified by #2, #3, and #4 — execute strictly in that order; #3 and #4 must each rebase onto the previous merge before starting.
- `scripts/tests/` is created by #2 and extended by #3 and #4 — same ordering constraint.
- `skills/plan-iteration/SKILL.md` is modified only by #5 — no conflict with #3 or #4.
- `skills/triage-pr-comments/SKILL.md` is modified only by #6 — no conflict with any other plan.
- Both #5 and #6 reference the `prd.json` schema defined in #2. If the schema changes during #2 implementation, update both skill templates before merging #5/#6.
