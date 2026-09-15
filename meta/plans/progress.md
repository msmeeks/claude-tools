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
